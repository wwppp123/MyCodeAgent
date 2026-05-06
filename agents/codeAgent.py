import json
import uuid
import os
import logging
import sys
import traceback as tb
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional, List, Tuple, Dict

from core.agent import Agent
from core.llm import HelloAgentsLLM
from core.message import Message
from core.config import Config
from core.context_engine.context_builder import ContextBuilder
from core.context_engine.trace_logger import create_trace_logger
from core.env import load_env

load_env()
from core.context_engine.history_manager import HistoryManager
from core.context_engine.input_preprocessor import preprocess_input
from core.context_engine.summary_compressor import create_summary_generator
from core.context_engine.token_estimator import TokenEstimator
from core.session_store import (
    build_session_snapshot, save_session_snapshot, load_session_snapshot,
    save_checkpoint, load_checkpoint, mark_checkpoint_completed, clear_checkpoint,
)
from core.team_engine.display_mode import resolve_teammate_mode
from core.memory_store import MemoryStore
from tools.registry import ToolRegistry
from tools.builtin.list_files import ListFilesTool
from tools.builtin.search_files_by_name import SearchFilesByNameTool
from tools.builtin.search_code import GrepTool
from tools.builtin.read_file import ReadTool
from tools.builtin.write_file import WriteTool
from tools.builtin.edit_file import EditTool
from tools.builtin.edit_file_multi import MultiEditTool
from tools.builtin.todo_write import TodoWriteTool
from tools.builtin.skill import SkillTool
from tools.builtin.bash import BashTool
from tools.builtin.ask_user import AskUserTool
from tools.builtin.task import TaskTool
from tools.builtin.memory import MemoryTool
from tools.builtin.weather import WeatherTool
from tools.mcp.loader import register_mcp_servers, format_mcp_tools_prompt
from utils import setup_logger
from core.skills.skill_loader import SkillLoader


class CodeAgent(Agent):
    """
    Code Agent - 基于 ReAct 的代码助手
    
    上下文工程改造（按方案 D3）：
    - 使用 HistoryManager 管理会话历史
    - ReAct 每一步同步写入 assistant/tool 消息到 history
    - 支持压缩触发和 Summary 生成
    """
    DELEGATION_ALLOWED_TOOLS = {
        "TeamCreate",
        "SendMessage",
        "TeamStatus",
        "TeamDelete",
        "TeamCleanup",
        "TeamApprovals",
        "TeamApprovePlan",
        "TeamFanout",
        "TeamCollect",
        "TeamTaskCreate",
        "TeamTaskGet",
        "TeamTaskUpdate",
        "TeamTaskList",
        "TodoWrite",
        "AskUser",
    }
    
    def __init__(
        self, 
        name: str, 
        llm: HelloAgentsLLM, 
        tool_registry: ToolRegistry,
        project_root: str,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        logger=None,
    ):
        super().__init__(name, llm, system_prompt=system_prompt, config=config)
        self.project_root = project_root
        self.tool_registry = tool_registry
        self.logger = logger or setup_logger(
            name=f"agent.{self.name}",
            level=self.config.log_level,
        )
        self.last_response_raw: Optional[Any] = None
        self.max_steps = 50
        self.verbose = bool(self.config.debug)
        self.console_verbose = bool(self.config.show_react_steps)
        self.console_progress = bool(self.config.show_progress)
        self.interactive = os.getenv("AGENT_INTERACTIVE", "true").lower() in {"1", "true", "yes", "y", "on"}
        self.enable_agent_teams = bool(getattr(self.config, "enable_agent_teams", False))
        self.team_store_dir = str(getattr(self.config, "agent_teams_store_dir", ".teams") or ".teams")
        self.task_store_dir = str(getattr(self.config, "agent_tasks_store_dir", ".tasks") or ".tasks")
        self.teammate_mode = str(getattr(self.config, "teammate_mode", "auto") or "auto")
        self.teammate_runtime_mode, self.teammate_mode_warning = resolve_teammate_mode(self.teammate_mode)
        self.delegate_mode = bool(getattr(self.config, "delegate_mode", False))
        if self.teammate_mode_warning:
            self.logger.warning(self.teammate_mode_warning)
        self.team_manager = None
        if self.enable_agent_teams:
            try:
                from core.team_engine.manager import TeamManager
                self.team_manager = TeamManager(
                    project_root=self.project_root,
                    team_store_dir=self.team_store_dir,
                    task_store_dir=self.task_store_dir,
                    llm=self.llm,
                    tool_registry=self.tool_registry,
                    teammate_runtime_mode=self.teammate_runtime_mode,
                )
            except Exception as exc:
                self.logger.warning("Failed to initialize TeamManager, AgentTeams disabled: %s", exc)
                self.enable_agent_teams = False
        self.logger.info(
            "AgentTeams enabled=%s, team_store_dir=%s, task_store_dir=%s, teammate_mode=%s, teammate_runtime_mode=%s, delegate_mode=%s",
            self.enable_agent_teams,
            self.team_store_dir,
            self.task_store_dir,
            self.teammate_mode,
            self.teammate_runtime_mode,
            self.delegate_mode,
        )
        
        # 创建 Summary 生成器（Phase 7）
        summary_generator = create_summary_generator(
            llm=self.llm,
            config=self.config,
            verbose=self.verbose,
        )

        # Token 估算器（使用 LLM 的模型和供应商信息）
        token_estimator = TokenEstimator(
            model=getattr(self.llm, "model", None),
            provider=getattr(self.llm, "provider", None),
        )

        # 历史管理器（替代 Agent._history）
        self.history_manager = HistoryManager(
            config=self.config,
            summary_generator=summary_generator,
            token_estimator=token_estimator,
        )
        
        # Skills
        self._skill_loader = SkillLoader(self.project_root)
        self._skills_prompt = ""
        self._refresh_skills_prompt()

        # Memory Store (持久化记忆)
        memory_store_path = str(getattr(self.config, "memory_store_path", ".agent_memory/memory.json") or ".agent_memory/memory.json")
        self.memory_store = MemoryStore(store_path=memory_store_path, logger=self.logger)

        # 注册工具
        self._register_builtin_tools()
        self._mcp_clients = [] # mcp服务客户端实例
        self._mcp_tools_prompt = "" # mcp工具提示词，包括name, description, parameters, returns
        self._register_mcp_tools()
        
        # 上下文构建器
        self.context_builder = ContextBuilder(
            tool_registry=self.tool_registry,
            project_root=self.project_root,
            system_prompt_override=self.system_prompt,
            mcp_tools_prompt=self._mcp_tools_prompt,
            skills_prompt=self._skills_prompt,
            memory_store=self.memory_store,
        )

        # Trace 日志（单实例贯穿 Agent 生命周期）
        self.trace_logger = create_trace_logger()
        self._system_messages_logged = False
        self._run_id = 0
        self._system_messages_override: Optional[List[dict]] = None

        # Checkpoint 目录（用于断点续传）
        self._checkpoint_dir = os.path.join(self.project_root, "memory", "checkpoints")
        os.makedirs(self._checkpoint_dir, exist_ok=True)
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        self.tool_registry.register_tool(
            ListFilesTool(project_root=self.project_root, working_dir=self.project_root)
        )
        self.tool_registry.register_tool(SearchFilesByNameTool(project_root=self.project_root))
        self.tool_registry.register_tool(GrepTool(project_root=self.project_root))
        self.tool_registry.register_tool(ReadTool(project_root=self.project_root))
        self.tool_registry.register_tool(WriteTool(project_root=self.project_root))
        self.tool_registry.register_tool(EditTool(project_root=self.project_root))
        self.tool_registry.register_tool(MultiEditTool(project_root=self.project_root))
        self.tool_registry.register_tool(TodoWriteTool(project_root=self.project_root))
        self.tool_registry.register_tool(
            SkillTool(project_root=self.project_root, skill_loader=self._skill_loader)
        )
        self.tool_registry.register_tool(BashTool(project_root=self.project_root))
        self.tool_registry.register_tool(
            AskUserTool(project_root=self.project_root, interactive=self.interactive)
        )
        # Task tool for subagent delegation
        self.tool_registry.register_tool(
            TaskTool(
                project_root=self.project_root,
                main_llm=self.llm,
                tool_registry=self.tool_registry,
                team_manager=self.team_manager,
            )
        )
        # Memory tool for persistent memory management
        self.tool_registry.register_tool(
            MemoryTool(project_root=self.project_root, memory_store=self.memory_store)
        )
        # Weather tool for querying weather information
        self.tool_registry.register_tool(WeatherTool(project_root=self.project_root))
        if self.enable_agent_teams:
            self._register_agent_teams_tools()

    def _register_agent_teams_tools(self) -> None:
        try:
            from tools.builtin.team_create import TeamCreateTool
            from tools.builtin.send_message import SendMessageTool
            from tools.builtin.team_status import TeamStatusTool
            from tools.builtin.team_delete import TeamDeleteTool
            from tools.builtin.team_cleanup import TeamCleanupTool
            from tools.builtin.team_approvals import TeamApprovalsTool
            from tools.builtin.team_approve_plan import TeamApprovePlanTool
            from tools.builtin.team_fanout import TeamFanoutTool
            from tools.builtin.team_collect import TeamCollectTool
            from tools.builtin.team_task_create import TeamTaskCreateTool
            from tools.builtin.team_task_get import TeamTaskGetTool
            from tools.builtin.team_task_update import TeamTaskUpdateTool
            from tools.builtin.team_task_list import TeamTaskListTool
        except Exception as exc:
            self.logger.warning("AgentTeams enabled but team tools unavailable: %s", exc)
            return

        self.tool_registry.register_tool(TeamCreateTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(SendMessageTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamStatusTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamDeleteTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamCleanupTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamApprovalsTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamApprovePlanTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamFanoutTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamCollectTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamTaskCreateTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamTaskGetTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamTaskUpdateTool(project_root=self.project_root, team_manager=self.team_manager))
        self.tool_registry.register_tool(TeamTaskListTool(project_root=self.project_root, team_manager=self.team_manager))

    def _refresh_skills_prompt(self) -> None:
        refresh = os.getenv("SKILLS_REFRESH_ON_CALL", "true").lower() in {"1", "true", "yes", "y", "on"}
        if refresh:
            self._skill_loader.refresh_if_stale()
        elif not self._skills_prompt:
            self._skill_loader.scan()
        budget = int(os.getenv("SKILLS_PROMPT_CHAR_BUDGET", "12000"))
        self._skills_prompt = self._skill_loader.format_skills_for_prompt(budget)

    def _register_mcp_tools(self) -> None:
        """可选：注册 MCP 工具（基于 MCP_SERVERS 配置）"""
        try:
            clients, tools_meta = register_mcp_servers(self.tool_registry, self.project_root)
            self._mcp_clients = clients
            self._mcp_tools_prompt = format_mcp_tools_prompt(tools_meta)
            if tools_meta:
                self.logger.info("MCP tools loaded: %d", len(tools_meta))
                if self.logger.isEnabledFor(logging.DEBUG):
                    for tool in tools_meta:
                        name = tool.get("name") or ""
                        description = (tool.get("description") or "").strip()
                        if description:
                            self.logger.debug("MCP tool: %s - %s", name, description)
                        else:
                            self.logger.debug("MCP tool: %s", name)
        except Exception as exc:
            if self.logger:
                self.logger.warning("MCP registration skipped: %s", exc)

    def run(self, input_text: str, **kwargs) -> str:
        """
        Code Agent 的入口（Message List 自然累积模式）
        
        流程：
        1. 预处理用户输入（@file 解析）
        2. 检查是否需要压缩历史
        3. 将用户消息写入 history（轮次开始）
        4. 运行 ReAct 循环（每步 assistant/tool 消息自然累积）
        5. 返回最终结果
        
        Message List 模式：
        - 不再使用 scratchpad 拼接
        - 每步的 messages 由 history 自然累积
        - L1/L2 作为 system messages
        - L3 是累积的 user/assistant/tool
        """
        show_raw = kwargs.pop("show_raw", False)
        if not show_raw:
            self.last_response_raw = None

        # 新的 run 开始，清除旧 checkpoint（避免残留的 running 状态干扰）
        self._clear_checkpoint()

        if self.console_progress:
            self._console("⏳ Agent 正在处理，请稍候...")

        # 动态注入当前时间
        # 在context_builder.py中

        # 1. 预处理用户输入（@file 解析）
        self._refresh_skills_prompt()
        self.context_builder.set_skills_prompt(self._skills_prompt)
        preprocess_result = preprocess_input(input_text)
        processed_input = preprocess_result.processed_input
        
        if preprocess_result.mentioned_files:
            mentioned = ", ".join(preprocess_result.mentioned_files)
            if self.console_verbose:
                self._console(f"\n📎 检测到文件引用: {mentioned}")
                if preprocess_result.truncated_count > 0:
                    self._console(f"   (另有 {preprocess_result.truncated_count} 个文件被省略)")
            elif self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("检测到文件引用: %s", mentioned)
                if preprocess_result.truncated_count > 0:
                    self.logger.debug("另有 %d 个文件被省略", preprocess_result.truncated_count)

        trace_logger = self.trace_logger
        self._run_id += 1
        run_id = self._run_id

        self._log_system_messages_if_needed(trace_logger)
        trace_logger.log_event(
            "run_start",
            {
                "run_id": run_id,
                "input": input_text,
                "processed": processed_input,
            },
            step=0,
        )
        
        # 2. 压缩检测改为每次 ReAct 之前（循环内）

        # 3. 将用户消息写入 history（轮次开始时写入）
        self.history_manager.append_user(processed_input)
        trace_logger.log_event("user_input", {"text": input_text, "processed": processed_input}, step=0)
        self._log_message_write(trace_logger, "user", processed_input, {}, step=0)

        if self.console_verbose:
            self._console(f"\n⚙️ Engine 启动: {input_text}")
        elif self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Engine 启动: %s", input_text)

        response_text = ""
        try:
            response_text = self._react_loop(
                pending_input=processed_input,
                show_raw=show_raw,
                trace_logger=trace_logger,
            )
        finally:
            trace_logger.log_event(
                "run_end",
                {"run_id": run_id, "final": response_text if "response_text" in locals() else ""},
                step=0,
            )
        if self.console_progress:
            self._console("✅ Agent 已完成")

        self.logger.debug("response=%s", response_text)
        self.logger.info("history_size=%d, rounds=%d", 
                        self.history_manager.get_message_count(),
                        self.history_manager.get_rounds_count())
        return response_text

    def close(self):
        """关闭 Agent 并写入 trace 总结"""
        if self.trace_logger:
            self.trace_logger.finalize()
            self.trace_logger = None
        for client in getattr(self, "_mcp_clients", []):
            try:
                client.close_sync()
            except Exception:
                pass

    # =========================================================================
    # ReAct Core（Message List 自然累积模式）
    # =========================================================================

    def _react_loop(
        self,
        pending_input: str,
        show_raw: bool,
        trace_logger,
        resume_from_step: int = 1,
    ) -> str:
        """
        ReAct 循环（Message List 模式）

        每步：
        1. 构建 messages = system(L1/L2) + history(user/assistant/tool)
        2. 调用 LLM
        3. 解析 Thought/Action
        4. 若为 Finish：返回结果
        5. 若为工具调用：执行工具，将 assistant + tool 消息追加到 history
        6. 自动保存 checkpoint（支持断点续传）
        """
        tool_choice = "auto"

        for step in range(resume_from_step, self.max_steps + 1):
            tools_schema = self._get_openai_tools_for_current_mode()
            if self.enable_agent_teams and self.team_manager and hasattr(self.context_builder, "set_runtime_system_blocks"):
                events = self.team_manager.drain_events()
                runtime_state = self.team_manager.export_state()
                runtime_blocks = self._format_runtime_system_blocks(events, runtime_state=runtime_state)
                self.context_builder.set_runtime_system_blocks(runtime_blocks)

            if self.console_verbose:
                self._console(f"\n--- Step {step}/{self.max_steps} ---")
            elif self.console_progress:
                self._console(f"… Step {step}/{self.max_steps}")
            elif self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("Step %d/%d", step, self.max_steps)

            # 每次 ReAct 前检查是否需要压缩
            if self.history_manager.should_compress(pending_input):
                estimated_tokens = self.history_manager.estimate_context_tokens(pending_input)
                threshold = int(self.config.context_window * self.config.compression_threshold)
                trace_logger.log_event("history_compression_triggered", {
                    "estimated_tokens": estimated_tokens,
                    "threshold": threshold,
                    "total_usage_tokens": self.history_manager.get_total_usage_tokens(),
                    "message_count": self.history_manager.get_message_count(),
                }, step=step)

                if self.console_verbose:
                    self._console("\n📦 触发历史压缩...")
                elif self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("触发历史压缩")

                rounds_before = self.history_manager.get_rounds_count()
                messages_before = self.history_manager.get_message_count()

                compress_info = self.history_manager.compact(
                    on_event=lambda ev, payload: trace_logger.log_event(ev, payload, step=step),
                    return_info=True,
                )
                compressed = bool(compress_info.get("compressed"))

                if compressed:
                    rounds_after = self.history_manager.get_rounds_count()
                    messages_after = self.history_manager.get_message_count()

                    trace_logger.log_event("history_compression_completed", {
                        "rounds_before": rounds_before,
                        "rounds_after": rounds_after,
                        "messages_compressed": messages_before - messages_after,
                        "summary_generated": compress_info.get("summary_generated", False),
                        "details": compress_info,
                    }, step=step)

                    # 记录压缩后的最终上下文（system + history）
                    compressed_history = self.history_manager.to_messages()
                    final_context = self.context_builder.build_messages(compressed_history)
                    trace_logger.log_event(
                        "history_compression_final_context",
                        {"message_count": len(final_context), "messages": final_context},
                        step=step,
                    )

                    if self.console_verbose:
                        self._console(f"✅ 压缩完成，当前轮次数: {rounds_after}")
                        self._print_context_preview(final_context)
                    elif self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("压缩完成，当前轮次数: %d", rounds_after)
                        self._print_context_preview(final_context)

            # 构建 messages 列表
            history_messages = self.history_manager.to_messages()
            messages = self._build_messages(history_messages)
            base_messages = messages
            
            trace_logger.log_event(
                "context_build",
                {"message_count": len(messages), "history_count": len(history_messages)},
                step=step,
            )

            usage = None
            empty_retry_used = False
            response_text = ""
            tool_calls: list[dict[str, Any]] = []

            while True:
                # 调用 LLM
                raw_response = self.llm.invoke_raw(messages, tools=tools_schema, tool_choice=tool_choice)
                if show_raw:
                    self.last_response_raw = (
                        raw_response.model_dump()
                        if hasattr(raw_response, "model_dump")
                        else raw_response
                    )

                response_text = self._extract_content(raw_response) or ""
                reasoning_content = self._extract_reasoning_content(raw_response)
                usage = self._extract_usage(raw_response)
                if usage and usage.get("total_tokens") is not None:
                    self.history_manager.update_last_usage(usage["total_tokens"])

                response_meta = self._extract_response_meta(raw_response)
                tool_calls = self._extract_tool_calls(raw_response)
                raw_dump = self._extract_raw_response(raw_response)
                trace_logger.log_event(
                    "model_output",
                    {
                        "raw": response_text,
                        "usage": usage,
                        "meta": response_meta,
                        "raw_response": raw_dump,
                        "tool_calls": tool_calls,
                    },
                    step=step,
                )

                if self.console_verbose and reasoning_content:
                    display_reasoning = reasoning_content
                    if len(display_reasoning) > 1200:
                        display_reasoning = display_reasoning[:1200] + "...(truncated)"
                    self._console(f"\n🧠 Reasoning: {display_reasoning}\n")

                if tool_calls or (response_text and str(response_text).strip()):
                    break

                # 重试一次并追加提示
                if not empty_retry_used:
                    empty_retry_used = True
                    hint = "上次 content 为空且未返回 tool_calls，请在 content 中回复最终答案，或使用工具调用。"
                    messages = base_messages + [{"role": "user", "content": hint}]
                    trace_logger.log_event(
                        "empty_response_retry",
                        {
                            "finish_reason": response_meta.get("finish_reason"),
                            "content_len": response_meta.get("content_len"),
                            "reasoning_len": response_meta.get("reasoning_len"),
                            "hint": hint,
                        },
                        step=step,
                    )
                    if self.console_verbose:
                        self._console("⚠️ LLM返回空响应，追加提示后重试一次")
                    else:
                        self.logger.warning("LLM返回空响应，追加提示后重试一次")
                    continue

                if self.console_verbose:
                    self._console("❌ LLM返回空响应")
                else:
                    self.logger.error("LLM返回空响应")
                trace_logger.log_event(
                    "error",
                    {
                        "stage": "llm_response",
                        "error_code": "INTERNAL_ERROR",
                        "message": "Empty response",
                        "meta": response_meta,
                    },
                    step=step,
                )
                break

            if not tool_calls and (not response_text or not str(response_text).strip()):
                break
            # 有工具调用：写入 assistant + 并行执行 tools
            if tool_calls:
                # ensure each tool_call has an id (OpenAI strict requirement)
                for call in tool_calls:
                    if not call.get("id"):
                        call["id"] = f"call_{uuid.uuid4().hex}"
                assistant_content = str(response_text or "")
                self.history_manager.append_assistant(
                    content=assistant_content,
                    metadata={
                        "step": step,
                        "action_type": "tool_call",
                        "tool_calls": tool_calls,
                    },
                    reasoning_content=reasoning_content,
                )
                self._log_message_write(
                    trace_logger,
                    "assistant",
                    assistant_content,
                    {"action_type": "tool_call", "tool_calls": tool_calls},
                    step,
                )

                # ---- 并行工具执行 ----
                # 多个工具调用时使用线程池并行执行，单个时直接调用避免开销
                if len(tool_calls) > 1:
                    trace_logger.log_event(
                        "parallel_tool_start",
                        {"count": len(tool_calls), "tools": [c.get("name") for c in tool_calls]},
                        step=step,
                    )
                    if self.console_verbose:
                        tool_names = [c.get("name", "?") for c in tool_calls]
                        self._console(f"\n⚡ 并行执行 {len(tool_calls)} 个工具: {', '.join(tool_names)}\n")

                    results: list[dict] = [None] * len(tool_calls)  # type: ignore[list-item]
                    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as pool:
                        future_to_idx = {
                            pool.submit(self._execute_tool_call, call): idx
                            for idx, call in enumerate(tool_calls)
                        }
                        for future in as_completed(future_to_idx):
                            idx = future_to_idx[future]
                            try:
                                results[idx] = future.result()
                            except Exception as exc:
                                call = tool_calls[idx]
                                results[idx] = {
                                    "tool_name": call.get("name") or "unknown_tool",
                                    "tool_call_id": call.get("id") or f"call_{uuid.uuid4().hex}",
                                    "tool_input": call.get("arguments") or {},
                                    "observation": json.dumps({
                                        "status": "error",
                                        "error": {"code": "EXECUTION_ERROR", "message": str(exc)},
                                        "data": {},
                                    }, ensure_ascii=False),
                                    "error": True,
                                    "error_stage": "tool_execution",
                                    "error_message": str(exc),
                                    "traceback": tb.format_exc(),
                                }

                    trace_logger.log_event(
                        "parallel_tool_end",
                        {"count": len(results), "tools": [r["tool_name"] for r in results]},
                        step=step,
                    )
                else:
                    # 单个工具调用，直接执行避免线程池开销
                    results = [self._execute_tool_call(tool_calls[0])]

                # ---- 将所有工具结果写入 history ----
                for result in results:
                    tool_name = result["tool_name"]
                    tool_call_id = result["tool_call_id"]
                    observation = result["observation"]
                    tool_input = result["tool_input"]

                    # trace 日志
                    if result.get("error"):
                        trace_logger.log_event(
                            "error",
                            {
                                "stage": result.get("error_stage", "tool_execution"),
                                "error_code": "EXECUTION_ERROR",
                                "message": result.get("error_message", ""),
                                "tool": tool_name,
                                "tool_call_id": tool_call_id,
                            },
                            step=step,
                        )
                    else:
                        trace_logger.log_event("tool_call", {"tool": tool_name, "args": tool_input, "tool_call_id": tool_call_id}, step=step)
                        try:
                            result_obj = json.loads(observation)
                            trace_logger.log_event("tool_result", {"tool": tool_name, "result": result_obj}, step=step)
                        except json.JSONDecodeError:
                            trace_logger.log_event("tool_result", {"tool": tool_name, "result": {"text": observation}}, step=step)

                    if self.console_verbose:
                        self._console(f"\n🎬 Action: {tool_name}[{tool_input}]\n")
                        display_obs = observation[:300] + "..." if len(observation) > 300 else observation
                        self._console(f"\n👀 Observation: {display_obs}\n")
                    elif self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("Action: %s %s", tool_name, tool_input)
                        display_obs = observation[:300] + "..." if len(observation) > 300 else observation
                        self.logger.debug("Observation: %s", display_obs)

                    self.history_manager.append_tool(
                        tool_name=tool_name,
                        raw_result=observation,
                        metadata={"step": step, "tool_call_id": tool_call_id},
                        project_root=self.project_root,
                    )
                    self._log_message_write(
                        trace_logger,
                        "tool",
                        observation,
                        {"tool_name": tool_name, "tool_call_id": tool_call_id},
                        step,
                    )

                # 工具执行完毕，保存 checkpoint 以支持断点续传
                self._save_checkpoint(step, pending_input)
                continue

            # 无工具调用：视为最终回答
            final_text = str(response_text).strip()
            self.history_manager.append_assistant(
                content=final_text,
                metadata={"step": step, "action_type": "final"},
                reasoning_content=reasoning_content,  # ⚠️ 传递 reasoning_content
            )
            self._log_message_write(trace_logger, "assistant", final_text, {"action_type": "final"}, step)
            trace_logger.log_event("finish", {"final": final_text}, step=step)
            self._mark_checkpoint_completed()
            return final_text

        self._mark_checkpoint_completed()
        return "抱歉，我无法在限定步数内完成这个任务。"

    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def _log_message_write(self, trace_logger, role: str, content: str, metadata: dict, step: int = 0):
        """辅助：记录消息写入到 trace"""
        trace_logger.log_event("message_written", {
            "role": role,
            "content": content,
            "metadata": metadata,
        }, step=step)

    def _log_system_messages_if_needed(self, trace_logger) -> None:
        if self._system_messages_logged or not trace_logger:
            return
        system_messages = self._get_system_messages_for_run()
        trace_logger.log_system_messages(system_messages)
        self._system_messages_logged = True

    def _get_system_messages_for_run(self) -> List[dict]:
        if self._system_messages_override:
            return [dict(m) for m in self._system_messages_override]
        return self.context_builder.get_system_messages()

    def _build_messages(self, history_messages: list[dict]) -> list[dict]:
        # system_messages = self._get_system_messages_for_run()
        # return list(system_messages) + list(history_messages)
        return self.context_builder.build_messages(history_messages)

    def save_session(self, path: str) -> None:
        """保存会话快照（含 system messages）。"""
        system_messages = self._get_system_messages_for_run()
        history_messages = self.history_manager.serialize_messages()
        tool_schema = self._get_openai_tools_for_current_mode()
        teams_snapshot = self.team_manager.export_state() if self.team_manager else {}
        snapshot = build_session_snapshot(
            system_messages=system_messages,
            history_messages=history_messages,
            tool_schema=tool_schema,
            project_root=self.project_root,
            cwd=".",
            code_law_text=self.context_builder._cached_code_law,
            skills_prompt=self._skills_prompt,
            mcp_tools_prompt=self._mcp_tools_prompt,
            read_cache=self.tool_registry.export_read_cache(),
            tool_output_dir="tool-output",
            schema_version=1,
            teams_snapshot=teams_snapshot,
            parallel_work_index=(teams_snapshot.get("work_items", {}) if isinstance(teams_snapshot, dict) else {}),
            team_store_dir=self.team_store_dir,
            task_store_dir=self.task_store_dir,
        )
        save_session_snapshot(path, snapshot)

    def load_session(self, path: str) -> None:
        """从快照恢复会话（scheme B）。"""
        snapshot = load_session_snapshot(path)
        self._system_messages_override = snapshot.get("system_messages") or []
        history_items = snapshot.get("history_messages") or []
        self.history_manager.load_messages(history_items)
        self.tool_registry.import_read_cache(snapshot.get("read_cache") or {})
        if self.team_manager:
            self.team_manager.import_state(snapshot.get("teams_snapshot") or {})
            if hasattr(self.context_builder, "set_runtime_system_blocks"):
                self.context_builder.set_runtime_system_blocks(
                    ["[Team Runtime]\n- Team state restored from session snapshot."]
                )

    # ------------------------------------------------------------------
    # Checkpoint (断点续传)
    # ------------------------------------------------------------------

    def _get_checkpoint_path(self) -> str:
        """Return the default checkpoint file path."""
        return os.path.join(self._checkpoint_dir, "checkpoint-latest.json")

    def _save_checkpoint(self, step: int, pending_input: str) -> None:
        """Save a checkpoint snapshot of the current ReAct state.

        Called after each successful tool execution so that an interrupted
        session can be resumed from this point.
        """
        try:
            system_messages = self._get_system_messages_for_run()
            history_messages = self.history_manager.serialize_messages()
            tool_schema = self._get_openai_tools_for_current_mode()
            teams_snapshot = self.team_manager.export_state() if self.team_manager else {}
            snapshot = build_session_snapshot(
                system_messages=system_messages,
                history_messages=history_messages,
                tool_schema=tool_schema,
                project_root=self.project_root,
                cwd=".",
                code_law_text=self.context_builder._cached_code_law,
                skills_prompt=self._skills_prompt,
                mcp_tools_prompt=self._mcp_tools_prompt,
                read_cache=self.tool_registry.export_read_cache(),
                tool_output_dir="tool-output",
                schema_version=1,
                teams_snapshot=teams_snapshot,
                parallel_work_index=(teams_snapshot.get("work_items", {}) if isinstance(teams_snapshot, dict) else {}),
                team_store_dir=self.team_store_dir,
                task_store_dir=self.task_store_dir,
            )
            save_checkpoint(self._get_checkpoint_path(), snapshot, pending_input, step)
            self.logger.debug("Checkpoint saved: step=%d", step)
        except Exception as exc:
            self.logger.warning("Failed to save checkpoint at step %d: %s", step, exc)

    def _mark_checkpoint_completed(self) -> None:
        """Mark the current checkpoint as completed (loop finished normally)."""
        try:
            mark_checkpoint_completed(self._get_checkpoint_path())
        except Exception:
            pass

    def _clear_checkpoint(self) -> None:
        """Remove the checkpoint file."""
        try:
            clear_checkpoint(self._get_checkpoint_path())
        except Exception:
            pass

    def load_checkpoint(self, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load a checkpoint if one is resumable.

        Returns the checkpoint dict (with checkpoint_pending_input,
        checkpoint_current_step, history_messages, etc.) or None.
        """
        cp_path = path or self._get_checkpoint_path()
        return load_checkpoint(cp_path)

    def resume_from_checkpoint(self, checkpoint: Dict[str, Any], show_raw: bool = False) -> str:
        """Resume a ReAct loop from a saved checkpoint.

        Restores history, then continues the loop from the saved step.
        """
        # Restore history from checkpoint
        history_items = checkpoint.get("history_messages") or []
        self.history_manager.load_messages(history_items)
        self._system_messages_override = checkpoint.get("system_messages") or []
        self.tool_registry.import_read_cache(checkpoint.get("read_cache") or {})
        if self.team_manager:
            self.team_manager.import_state(checkpoint.get("teams_snapshot") or {})

        pending_input = checkpoint["checkpoint_pending_input"]
        resume_step = checkpoint["checkpoint_current_step"]

        self.logger.info("Resuming from checkpoint: step=%d, pending_input=%s", resume_step, pending_input[:80])
        if self.console_verbose:
            self._console(f"\n🔄 从检查点恢复: step={resume_step}")

        trace_logger = self.trace_logger
        self._run_id += 1
        run_id = self._run_id
        self._log_system_messages_if_needed(trace_logger)
        trace_logger.log_event(
            "checkpoint_resume",
            {"run_id": run_id, "resume_step": resume_step, "pending_input": pending_input},
            step=resume_step,
        )

        try:
            response_text = self._react_loop(
                pending_input=pending_input,
                show_raw=show_raw,
                trace_logger=trace_logger,
                resume_from_step=resume_step + 1,
            )
        finally:
            trace_logger.log_event(
                "run_end",
                {"run_id": run_id, "final": response_text if "response_text" in locals() else "", "resumed": True},
                step=0,
            )
        return response_text

    def _print_context_preview(
        self,
        messages: list[dict],
        max_messages: int = 10,
        content_limit: int = 200,
    ) -> None:
        if not messages:
            if self.console_verbose:
                self._console("（当前上下文为空）")
            else:
                self.logger.debug("当前上下文为空")
            return
        total = len(messages)
        preview = messages[:max_messages]
        if self.console_verbose:
            self._console(f"\n📌 当前上下文（最多显示 {max_messages} 条）")
        else:
            self.logger.debug("当前上下文（最多显示 %d 条）", max_messages)
        for msg in preview:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            content = str(content).replace("\n", "\\n")
            if len(content) > content_limit:
                content = content[:content_limit] + "...(truncated)"
            if self.console_verbose:
                self._console(f'message({role}, "{content}")')
            else:
                self.logger.debug('message(%s, "%s")', role, content)
        if total > max_messages:
            if self.console_verbose:
                self._console(f"...（其余 {total - max_messages} 条已省略）")
            else:
                self.logger.debug("其余 %d 条已省略", total - max_messages)

    def _console(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    @staticmethod
    def _format_runtime_system_blocks(
        events: list[dict],
        runtime_state: Optional[dict] = None,
        max_lines: int = 16,
    ) -> list[str]:
        has_events = bool(events)
        state = runtime_state if isinstance(runtime_state, dict) else {}
        teams = state.get("teams") if isinstance(state.get("teams"), dict) else {}
        work_items = state.get("work_items") if isinstance(state.get("work_items"), dict) else {}
        approvals = state.get("approvals") if isinstance(state.get("approvals"), dict) else {}
        task_board = state.get("task_board") if isinstance(state.get("task_board"), dict) else {}
        if not has_events and not work_items:
            return []
        lines = ["[Team Runtime]"]

        for team_name in sorted(work_items.keys()):
            counts = work_items.get(team_name)
            if not isinstance(counts, dict):
                continue
            queued = int(counts.get("queued", 0) or 0)
            running = int(counts.get("running", 0) or 0)
            succeeded = int(counts.get("succeeded", 0) or 0)
            failed = int(counts.get("failed", 0) or 0)
            lines.append(
                f"- {team_name} work queued={queued} running={running} succeeded={succeeded} failed={failed}"
            )
            team_state = teams.get(team_name) if isinstance(teams, dict) else {}
            if isinstance(team_state, dict):
                idle_members = team_state.get("idle_teammates")
                active_members = team_state.get("active_teammates")
                if isinstance(idle_members, list) or isinstance(active_members, list):
                    idle_count = len(idle_members) if isinstance(idle_members, list) else 0
                    active_count = len(active_members) if isinstance(active_members, list) else 0
                    lines.append(f"- {team_name} teammates active={active_count} idle={idle_count}")
                last_error = str(team_state.get("last_error") or "").strip()
                if last_error:
                    compact_error = " ".join(last_error.split())
                    if len(compact_error) > 120:
                        compact_error = f"{compact_error[:117]}..."
                    lines.append(f"- {team_name} last_error={compact_error}")
            approval_counts = approvals.get(team_name) if isinstance(approvals, dict) else {}
            if isinstance(approval_counts, dict):
                pending = int(approval_counts.get("pending", 0) or 0)
                approved = int(approval_counts.get("approved", 0) or 0)
                rejected = int(approval_counts.get("rejected", 0) or 0)
                if pending or approved or rejected:
                    lines.append(
                        f"- {team_name} approvals pending={pending} approved={approved} rejected={rejected}"
                    )
            board_counts = task_board.get(team_name) if isinstance(task_board, dict) else {}
            if isinstance(board_counts, dict):
                blocked = int(board_counts.get("blocked", 0) or 0)
                pending_tasks = int(board_counts.get("pending", 0) or 0)
                in_progress = int(board_counts.get("in_progress", 0) or 0)
                if blocked or pending_tasks or in_progress:
                    lines.append(
                        f"- {team_name} tasks blocked={blocked} pending={pending_tasks} in_progress={in_progress}"
                    )

        deduped_events: list[dict] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for event in events:
            if not isinstance(event, dict):
                continue
            team = str(event.get("team", "unknown"))
            event_type = str(event.get("type", "event"))
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            signature = (
                team,
                event_type,
                str(payload.get("message_id") or ""),
                str(payload.get("work_id") or ""),
                str(payload.get("status") or ""),
            )
            if signature in seen:
                continue
            seen.add(signature)
            deduped_events.append(event)

        max_event_lines = 8
        for event in deduped_events[:max_event_lines]:
            team = event.get("team", "unknown")
            event_type = event.get("type", "event")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            status = payload.get("status")
            message_id = payload.get("message_id")
            work_id = payload.get("work_id")
            if work_id and status:
                lines.append(f"- event {team}:{event_type} work={work_id} status={status}")
            elif message_id and status:
                lines.append(f"- event {team}:{event_type} message={message_id} status={status}")
            elif message_id:
                lines.append(f"- event {team}:{event_type} message={message_id}")
            else:
                lines.append(f"- event {team}:{event_type}")
        if len(deduped_events) > max_event_lines:
            lines.append(f"- ... {len(deduped_events) - max_event_lines} more events")

        limit = max(2, int(max_lines or 0))
        if len(lines) > limit:
            hidden = len(lines) - (limit - 1)
            lines = lines[: limit - 1] + [f"- ... {hidden} more lines"]

        return ["\n".join(lines)]

    def _execute_tool(self, tool_name: str, tool_input: Any) -> str:
        if not self._is_tool_allowed_in_delegate_mode(tool_name):
            payload = {
                "status": "error",
                "data": {},
                "text": f"Tool '{tool_name}' is blocked in delegate mode.",
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": f"Tool '{tool_name}' is not allowed in delegate mode.",
                },
                "stats": {"time_ms": 0},
                "context": {"cwd": ".", "params_input": tool_input if isinstance(tool_input, dict) else {"input": tool_input}},
            }
            return json.dumps(payload, ensure_ascii=False, indent=2)
        res = self.tool_registry.execute_tool(tool_name, tool_input)
        return str(res)

    def _execute_tool_call(self, call: dict) -> dict:
        """Execute a single tool call and return a result dict.

        This is a self-contained unit suitable for parallel execution via
        ThreadPoolExecutor.  Returns::

            {
                "tool_name": str,
                "tool_call_id": str,
                "tool_input": dict | Any,
                "observation": str,
                "error": bool,
            }
        """
        tool_name = call.get("name") or "unknown_tool"
        tool_call_id = call.get("id") or f"call_{uuid.uuid4().hex}"
        raw_args = call.get("arguments") or {}
        tool_input, parse_err = self._ensure_json_input(raw_args)

        if parse_err:
            error_result = {
                "status": "error",
                "error": {"code": "INVALID_PARAM", "message": f"Tool arguments parse error: {parse_err}"},
                "data": {},
            }
            return {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "tool_input": raw_args,
                "observation": json.dumps(error_result, ensure_ascii=False),
                "error": True,
                "error_stage": "tool_call_parse",
                "error_message": str(parse_err),
            }

        try:
            observation = self._execute_tool(tool_name, tool_input)
            return {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "tool_input": tool_input,
                "observation": observation,
                "error": False,
            }
        except Exception as e:
            error_result = {
                "status": "error",
                "error": {"code": "EXECUTION_ERROR", "message": str(e)},
                "data": {},
            }
            return {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "tool_input": tool_input,
                "observation": json.dumps(error_result, ensure_ascii=False),
                "error": True,
                "error_stage": "tool_execution",
                "error_message": str(e),
                "traceback": tb.format_exc(),
            }

    def set_delegate_mode(self, enabled: bool) -> None:
        self.delegate_mode = bool(enabled)
        if hasattr(self.config, "delegate_mode"):
            self.config.delegate_mode = self.delegate_mode
        self.logger.info("Delegate mode set to %s", self.delegate_mode)

    def _is_tool_allowed_in_delegate_mode(self, tool_name: str) -> bool:
        if not self.delegate_mode:
            return True
        return str(tool_name or "") in self.DELEGATION_ALLOWED_TOOLS

    def _get_openai_tools_for_current_mode(self) -> list[dict[str, Any]]:
        tools = self.tool_registry.get_openai_tools()
        if not self.delegate_mode:
            return tools
        filtered: list[dict[str, Any]] = []
        for item in tools:
            function = item.get("function") if isinstance(item, dict) else None
            name = function.get("name") if isinstance(function, dict) else ""
            if self._is_tool_allowed_in_delegate_mode(str(name or "")):
                filtered.append(item)
        return filtered

    def _ensure_json_input(self, raw: str) -> Tuple[Any, Optional[str]]:
        if raw is None:
            return {}, None
        if isinstance(raw, (dict, list)):
            return raw, None
        s = str(raw).strip()
        if not s:
            return {}, None
        try:
            return json.loads(s), None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def _extract_content(raw_response: Any) -> Optional[str]:
        try:
            choices = None
            if hasattr(raw_response, "choices"):
                choices = raw_response.choices
            elif isinstance(raw_response, dict):
                choices = raw_response.get("choices")
            
            if not choices or len(choices) == 0:
                return None
            
            choice = choices[0]
            message = None
            if hasattr(choice, "message"):
                message = choice.message
            elif isinstance(choice, dict):
                message = choice.get("message")
            
            if not message:
                return None
            
            content = None
            if hasattr(message, "content"):
                content = message.content
            elif isinstance(message, dict):
                content = message.get("content")
            
            if isinstance(content, list):
                return "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return content
        except Exception:
            return str(raw_response)

    @staticmethod
    def _extract_reasoning_content(raw_response: Any) -> Optional[str]:
        def _get_attr(obj, key: str):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        try:
            choices = _get_attr(raw_response, "choices")
            if not choices:
                return None
            choice = choices[0]
            message = _get_attr(choice, "message")
            if not message:
                return None

            reasoning = _get_attr(message, "reasoning_content") or _get_attr(message, "reasoning")
            if reasoning:
                return reasoning

            model_extra = None
            if isinstance(message, dict):
                model_extra = message.get("model_extra") or message.get("additional_kwargs")
            else:
                model_extra = getattr(message, "model_extra", None) or getattr(message, "additional_kwargs", None)
            if isinstance(model_extra, dict):
                return model_extra.get("reasoning_content") or model_extra.get("reasoning")
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_usage(raw_response: Any) -> Optional[dict]:
        try:
            if hasattr(raw_response, "usage"):
                usage = raw_response.usage
                if not usage:
                    return None
                return {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                }
            if isinstance(raw_response, dict) and raw_response.get("usage"):
                usage = raw_response["usage"]
                return {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
        except Exception:
            return None

    @staticmethod
    def _extract_tool_calls(raw_response: Any) -> list[dict[str, Any]]:
        """
        从原始响应中提取 tool_calls，统一成 {id,name,arguments} 列表。
        """
        def _get_attr(obj, key: str):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        try:
            choices = _get_attr(raw_response, "choices")
            if not choices or len(choices) == 0:
                return []
            choice = choices[0]
            message = _get_attr(choice, "message")
            if not message:
                return []
            tool_calls = _get_attr(message, "tool_calls") or []
            calls: list[dict[str, Any]] = []
            if tool_calls:
                for call in tool_calls:
                    fn = _get_attr(call, "function") or {}
                    name = _get_attr(fn, "name") or _get_attr(call, "name") or "unknown_tool"
                    arguments = _get_attr(fn, "arguments") or _get_attr(call, "arguments") or {}
                    call_id = _get_attr(call, "id")
                    calls.append({
                        "id": call_id,
                        "name": name,
                        "arguments": arguments,
                    })
                return calls

            # 兼容旧 function_call
            function_call = _get_attr(message, "function_call")
            if function_call:
                name = _get_attr(function_call, "name") or "unknown_tool"
                arguments = _get_attr(function_call, "arguments") or {}
                return [{"id": None, "name": name, "arguments": arguments}]
        except Exception:
            return []

        return []

    @staticmethod
    def _extract_response_meta(raw_response: Any) -> dict:
        """提取响应元信息，辅助定位空响应原因"""
        def _get_attr(obj, key: str):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        meta: dict = {}
        try:
            choices = _get_attr(raw_response, "choices") or []
            if not choices:
                return meta
            choice = choices[0]
            meta["finish_reason"] = _get_attr(choice, "finish_reason")
            message = _get_attr(choice, "message")
            if not message:
                return meta
            meta["role"] = _get_attr(message, "role")

            content = _get_attr(message, "content")
            reasoning_content = _get_attr(message, "reasoning_content") or _get_attr(message, "reasoning")
            refusal = _get_attr(message, "refusal")
            tool_calls = _get_attr(message, "tool_calls")
            function_call = _get_attr(message, "function_call")

            meta["content_len"] = len(str(content)) if content is not None else 0
            meta["reasoning_len"] = len(str(reasoning_content)) if reasoning_content is not None else 0
            meta["refusal_present"] = refusal is not None
            meta["tool_calls_count"] = len(tool_calls) if isinstance(tool_calls, list) else (1 if tool_calls else 0)
            meta["function_call_present"] = function_call is not None
        except Exception:
            return meta
        return meta

    @staticmethod
    def _extract_raw_response(raw_response: Any) -> dict:
        """将原始响应转换为可序列化结构（用于 trace 记录）"""
        try:
            if hasattr(raw_response, "model_dump"):
                return raw_response.model_dump()
            if hasattr(raw_response, "dict"):
                return raw_response.dict()
            if isinstance(raw_response, dict):
                return raw_response
        except Exception:
            pass
        return {"raw": str(raw_response)}
    
    # =========================================================================
    # 兼容 Agent 基类接口（使用 HistoryManager）
    # =========================================================================
    
    def add_message(self, message: Message):
        """兼容旧接口：添加消息到历史"""
        if message.role == "user":
            self.history_manager.append_user(message.content, message.metadata)
        elif message.role == "assistant":
            self.history_manager.append_assistant(message.content, message.metadata)
        elif message.role == "tool":
            # 注意：旧接口没有 tool_name，使用 metadata 中的值
            tool_name = (message.metadata or {}).get("tool_name", "unknown")
            self.history_manager.append_tool(
                tool_name, 
                message.content, 
                message.metadata,
                project_root=self.project_root,
            )
        elif message.role == "summary":
            self.history_manager.append_summary(message.content)
    
    def clear_history(self):
        """兼容旧接口：清空历史"""
        self.history_manager.clear()
    
    def get_history(self) -> List[Message]:
        """兼容旧接口：获取历史"""
        return self.history_manager.get_messages()
