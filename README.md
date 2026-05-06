

# MyCodeAgent
<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg) ![License](https://img.shields.io/badge/License-MIT-green.svg) 


</div>

一个面向学习与实验的 **代码代理框架**，聚焦 **工具协议**、**上下文工程**、**子代理机制** 与 **可观测性** 的系统化实践。

> 目标：让“Agent 能做什么”与“Agent 为什么能做”都可追溯、可验证、可扩展。

---

## 适用场景

- 学习 function calling + 工具协议的真实落地
- 研究上下文工程（截断、压缩、持久化）
- 实验 Skills / Task 子代理协作
- 快速搭建可扩展的本地 Agent 试验场

---

## 核心特性

- **Function Calling 工具调用**（不依赖 Action 文本解析）
- **统一工具响应协议**：`status/data/text/stats/context/error`
- **内置工具**：LS / Glob / Grep / Read / Write / Edit / MultiEdit / Bash / TodoWrite / Skill / Task / AskUser / Memory / Weather
- **持久化记忆系统**：跨会话保存用户偏好、重要信息，自动注入上下文
- **AgentTeams MVP（实验性）**：TeamCreate / SendMessage / TeamStatus / TeamDelete / TeamFanout / TeamCollect / TeamApprovals + Task persistent teammate
- **上下文工程**：分层注入、历史压缩、@file 强制读取、Token 估算
- **工具输出截断与落盘**：超限结果写入 `tool-output/`
- **轻量熔断**：连续失败工具自动临时禁用
- **Trace 追踪**：JSONL + HTML 双轨日志 + 脱敏
- **会话持久化**：支持 `/save` 与 `/load`、Checkpoint 恢复
- **MCP 扩展**：通过 `mcp_servers.json` 接入外部工具
- **Enhanced CLI UI**：工具调用树、token 统计、进度显示、Rich 主题

---
已实现功能
✅ ReAct Agent: 50步链式推理,Function Calling原生支持
✅ 上下文工程: 分层构建、智能压缩、统一截断、Token估算
✅ 工具协议: 统一响应结构、乐观锁、熔断机制
✅ 多LLM支持: 10+提供商自动适配
✅ 子代理系统: 四种类型、权限隔离、会话独立
✅ 多代理协作: 团队管理、并行任务、消息路由、审批流程
✅ Trace追踪: JSONL+HTML双轨日志、敏感信息脱敏
✅ 会话持久化: /save /load完整状态恢复、Checkpoint机制
✅ 持久化记忆: 跨会话记忆、分类管理、自动注入
✅ 内置工具集: 15+原生工具、MCP扩展支持

## 快速开始

### 环境要求

- Python 3.8+
- pip 包管理器

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd MyCodeAgent

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置环境变量

创建 `.env` 文件或设置以下环境变量：

```bash
# LLM 配置
export OPENAI_API_KEY="your-api-key"
export DEFAULT_MODEL="gpt-4"
export TEMPERATURE="0.7"

# AgentTeams（可选，默认为关闭）
export ENABLE_AGENT_TEAMS="true"

# 上下文配置
export CONTEXT_WINDOW="128000"
export COMPRESSION_THRESHOLD="0.8"
```

### 运行交互式 CLI

```bash
python scripts/chat_test_agent.py
```

### 指定模型与供应商

```bash
python scripts/chat_test_agent.py \
  --provider zhipu \
  --model GLM-4.7 \
  --api-key YOUR_API_KEY \
  --base-url https://open.bigmodel.cn/api/coding/paas/v4
```

### 开启原始输出（调试）

```bash
python scripts/chat_test_agent.py --show-raw
```

---

## 项目结构（概要）

```
agents/               主代理实现
core/                 核心运行时与上下文工程
tools/                工具系统与注册表
prompts/              系统提示词与工具提示词
docs/                 设计与协议文档
scripts/              CLI 入口
tests/                测试集
skills/               技能目录
memory/               trace/session 输出（本地）
tool-output/          长输出落盘目录
mcp_servers.json      MCP 工具配置
```

```
MyCodeAgent/
├── agents/           # Agent 实现
│   └── codeAgent.py  # 主 Agent（基于 ReAct 模式）
│
├── core/             # 核心模块
│   ├── agent.py      # Agent 基类
│   ├── config.py     # 配置管理
│   ├── llm.py        # LLM 调用封装
│   ├── message.py    # 消息结构
│   ├── env.py        # 环境变量加载
│   ├── memory_store.py # 持久化记忆存储
│   ├── session_store.py # 会话持久化与 Checkpoint
│   │
│   ├── context_engine/   # 上下文工程（重点！）
│   │   ├── context_builder.py     # 上下文构建
│   │   ├── history_manager.py     # 历史记录管理
│   │   ├── summary_compressor.py  # 摘要压缩
│   │   ├── input_preprocessor.py  # 输入预处理
│   │   ├── observation_truncator.py # 观察截断
│   │   ├── token_estimator.py     # Token 估算器
│   │   └── trace_logger.py        # 追踪日志
│   │
│   ├── team_engine/     # AgentTeams 多代理协作
│   │   ├── manager.py   # 团队管理器
│   │   ├── worker.py    # 工作节点
│   │   ├── supervisor.py # 监督者
│   │   └── ...
│   │
│   └── skills/          # 技能加载器
│       └── skill_loader.py
│
├── tools/            # 工具系统
│   ├── registry.py   # 工具注册表（含乐观锁）
│   ├── base.py       # 工具基类
│   ├── circuit_breaker.py # 熔断器
│   ├── builtin/      # 内置工具
│   │   ├── read_file.py, write_file.py, edit_file.py
│   │   ├── bash.py, search_code.py, search_files_by_name.py
│   │   ├── task.py, skill.py, todo_write.py
│   │   ├── memory.py, weather.py, ask_user.py
│   │   └── team_*.py  # 团队协作工具（12个）
│   └── mcp/          # MCP 协议支持
│       └── loader.py
│
├── prompts/          # 提示词模板
│   ├── agents_prompts/  # Agent 系统提示词
│   └── tools_prompts/   # 工具描述提示词
│
├── scripts/          # 入口脚本
│   └── chat_test_agent.py
│
├── utils/            # 工具函数
│   └── ui_components.py # UI 组件
│
└── tests/            # 测试用例
```

```
### 🔑 核心流程
1. 启动入口 → scripts/chat_test_agent.py

2. 初始化 Agent → agents/codeAgent.py

- 创建 LLM 实例
- 注册工具（内置 + MCP）
- 加载配置和提示词
3. ReAct 循环 （在 CodeAgent 中）:
-  用户输入 → 预处理 → 构建上下文 
    → 调用 LLM（决定是否调用工具）
    → 执行工具 → 观察结果 → 写回历史
    → 压缩/截断（如需要）→ 继续循环
```


---

## 技术栈

- Python 3.8+
- openai / pydantic / mcp / anyio
- rich / prompt_toolkit
- tiktoken（可选，用于精确 Token 估算）

---

## Skills（技能）

目录约定：

```
skills/
  <skill-name>/
    SKILL.md
```

`SKILL.md` 示例：

```markdown
---
name: code-review
description: Review code quality and risks
---
# Code Review

Use this checklist:
- ...

$ARGUMENTS
```

`$ARGUMENTS` 会被 Skill 工具传入的 `args` 替换。

### 内置技能

系统内置了以下技能，位于 `skills/` 目录：

- **code-review**: 代码质量审查
- **security-audit**: 安全审计
- **api-design**: API 设计规范
- **test-generation**: 测试用例生成
- **ui-ux-design**: UI/UX 设计指南

技能可以通过 `/skill-name` 或 `Skill(name="skill-name")` 调用。

---

## Task 子代理（MVP）

- 子代理类型：`general / explore / plan / summary`
- 主代理按复杂度选择模型：`main | light`
- 子代理工具权限隔离（只读/受限）
- 最大步数限制：`SUBAGENT_MAX_STEPS`（默认 50）

## TodoWrite 任务管理

TodoWrite 工具提供声明式任务列表管理：

- **决策留给模型**：拆解/调整/取消任务由模型决定
- **低心智负担**：模型只提交"当前完整列表"，不做 diff 或 id 维护
- **工具兜底**：参数校验、统计、recap 生成与持久化由工具完成
- **展示分离**：data 面向模型（结构化），text 面向用户（简洁 UI 展示）

任务状态：`pending` / `in_progress` / `completed` / `cancelled`

示例：
```json
{
  "summary": "实现用户认证功能",
  "todos": [
    {"content": "设计数据库模型", "status": "completed"},
    {"content": "实现 JWT 认证", "status": "in_progress"},
    {"content": "添加单元测试", "status": "pending"}
  ]
}
```

## Weather 天气查询

Weather 工具基于 Open-Meteo API，无需 API Key：

- 支持中国主要城市和全球城市查询
- 返回当前天气、温度、湿度、风速等信息
- 支持中英文城市名称

示例：
```json
{"city": "北京"}
{"city": "Shanghai"}
```

## AgentTeams（MVP）

> ⚠️ `AgentTeams` 已加入当前版本，但仍为**实验性功能**，默认关闭。
> 建议仅在开发/测试环境启用。

- Feature Flag：`ENABLE_AGENT_TEAMS=true` 启用（默认关闭，便于快速回滚）
- Claude 兼容开关：`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Team 工具：`TeamCreate` / `SendMessage` / `TeamStatus` / `TeamDelete` / `TeamCleanup`
- 并行分工工具：`TeamFanout` / `TeamCollect`
- 审批流程工具：`TeamApprovals` / `TeamApprovePlan`
- Task 管理工具：`TeamTaskCreate` / `TeamTaskGet` / `TeamTaskUpdate` / `TeamTaskList`
- Task 双模式：
  - `mode=oneshot`（默认，兼容旧行为）
  - `mode=persistent`（创建持久 teammate，参数：`team_name` + `teammate_name`）
  - `mode=parallel`（快捷 fanout，参数：`team_name` + `tasks`）
- 消息 ACK 三态：`pending / delivered / processed`
- work item 状态：`queued / running / succeeded / failed / canceled`
- runtime 通知通过 system block 注入，不污染 user 轮次
- Teammate 运行模式：`auto`（自动选择）/ `in-process`（进程内）/ `tmux`（tmux 会话）

最小示例（交互中由主代理触发工具调用）：
1. `TeamCreate(team_name="demo")`
2. `Task(mode="persistent", team_name="demo", teammate_name="dev", ...)`
3. `SendMessage(team_name="demo", from_member="lead", to_member="dev", text="...")`
4. `TeamStatus(team_name="demo")`
5. `TeamDelete(team_name="demo")`

并行分工示例：
1. `TeamCreate(team_name="demo")`
2. `Task(mode="persistent", team_name="demo", teammate_name="dev1", ...)`
3. `Task(mode="persistent", team_name="demo", teammate_name="dev2", ...)`
4. `Task(mode="parallel", team_name="demo", tasks=[{"owner":"dev1","title":"impl","instruction":"..."},{"owner":"dev2","title":"test","instruction":"..."}])`
5. `TeamCollect(team_name="demo")`（轮询直到 succeeded/failed 收敛）

快速回滚：将 `ENABLE_AGENT_TEAMS` 设为 `false`（或删除该环境变量）。

---

## MCP 工具集成

在项目根目录配置 `mcp_servers.json`（命令式启动）：

```json
{
  "mcpServers": {
    "example": {
      "command": "npx",
      "args": ["-y", "some-mcp-server", "--api-key", "${API_KEY}"]
    }
  }
}
```

---

## 关键环境变量

### Context / 历史

- `CONTEXT_WINDOW`（默认 10000）
- `COMPRESSION_THRESHOLD`（默认 0.8）
- `MIN_RETAIN_ROUNDS`（默认 10）
- `SUMMARY_TIMEOUT`（默认 120s）

### 工具输出截断

- `TOOL_OUTPUT_MAX_LINES`（默认 2000）
- `TOOL_OUTPUT_MAX_BYTES`（默认 51200）
- `TOOL_OUTPUT_TRUNCATE_DIRECTION`（head|tail|head_tail）
- `TOOL_OUTPUT_HEAD_TAIL_LINES`（默认 40，仅当 head_tail 生效）
- `TOOL_OUTPUT_DIR`（默认 tool-output）
- `TOOL_OUTPUT_RETENTION_DAYS`（默认 7）

### Skills

- `SKILLS_REFRESH_ON_CALL`（默认 true）
- `SKILLS_PROMPT_CHAR_BUDGET`（默认 12000）

### Circuit Breaker

- `CIRCUIT_FAILURE_THRESHOLD`（默认 3）
- `CIRCUIT_RECOVERY_TIMEOUT`（默认 300 秒）

### Subagent

- `SUBAGENT_MAX_STEPS`（默认 50）
- `LIGHT_LLM_MODEL_ID / LIGHT_LLM_API_KEY / LIGHT_LLM_BASE_URL`

### AgentTeams

- `ENABLE_AGENT_TEAMS`（默认 false）
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`（兼容 Claude Code 开关）
- `AGENT_TEAMS_STORE_DIR`（默认 `.teams`）
- `AGENT_TASKS_STORE_DIR`（默认 `.tasks`）
- `TEAMMATE_MODE`（默认 `auto`，可选 `in-process` / `tmux`）
- `TEAM_DELEGATE_MODE`（默认 false）

### Memory

- `MEMORY_STORE_PATH`（默认 `.agent_memory/memory.json`）

### Trace

- `TRACE_ENABLED`（默认 true）
- `TRACE_DIR`（默认 memory/traces）
- `TRACE_SANITIZE`（默认 true）
- `TRACE_HTML_INCLUDE_RAW_RESPONSE`（默认 false）

---

## 文档入口

- 工具协议：`docs/通用工具响应协议.md`
- 上下文工程：`docs/上下文工程设计文档.md`
- 工具输出截断：`docs/工具输出截断设计文档.md`
- Trace 设计：`docs/TraceLogging设计文档.md`
- Task 子代理：`docs/task(subagent)设计文档.md`
- Skill 机制：`docs/skillTool设计文档.md`
- 持久化记忆系统：`docs/持久化记忆系统使用指南.md`
- 记忆数据管理：`docs/记忆数据管理说明.md`
- 提示词设计：`docs/提示词设计最佳实践.md`
- AgentTeams 设计：`docs/agent_teams/AgentTeams功能设计文档.md`
- 工具设计文档：
  - `docs/BashTool设计文档.md`
  - `docs/EditTool设计文档.md`
  - `docs/ReadTool设计文档.md`
  - `docs/WriteTool设计文档.md`
  - `docs/GlobTool设计文档.md`
  - `docs/GrepTool设计文档.md`
  - `docs/LSTool设计文档.md`
  - `docs/MultiEditTool设计文档.md`
  - `docs/TodoWriteTool设计文档.md`
- 优化与改进：
  - `docs/提示词优化总结.md`
  - `docs/记忆功能改进总结.md`
  - `docs/记忆功能快速示例.md`
  - `docs/持久化记忆系统实现总结.md`
  - `docs/enhancement-plan.md`
- 测试指南：`docs/测试提示词.md`
- 交接说明：`docs/DEV_HANDOFF.md`

---

## 使用示例
测试提示词
```
  你需要分析自己的源代码，基于代码剖析的结果，创建一个面向用户的Agent自我介绍网页（以第一人称视角介绍自己）。
  - 请合理使用完成任务所需的所有工具，按照最优步骤执行
  - 内容与要求：
    - 可以使用mcp联网搜索获取同类竞品，分析优劣进行对比
    - 若你具备UI/UX相关技能（Skill），请调用并应用
    - 网页风格可自行选择（如玻璃拟态、拟物化、新拟态等均可）
    - 最终输出一个HTML文件，保存至demo/目录下（文件名可自定义
```
生成网页
[text](demo/agent-introduction.html)

![demo](/docs/assest/demo.png)

视频演示：
[MyCodeAgent 视频演示](https://www.bilibili.com/video/BV1vhkMBpEzq)

Todo List 能力
![todoList](/docs/assest/todoList.png)

MCP 能力
![mcp](/docs/assest/mcp.png)

Subagent 能力
![subagent](/docs/assest/subagent.png)

Skills 能力
![skill](/docs/assest/skill.png)


恢复会话能力
![load](/docs/assest/load.png)

---

## 参考资源（References）


> - 感谢 [Datawhale](https://github.com/datawhalechina) 提供的优秀开源教程 [HelloAgent](https://github.com/jjyaoao/HelloAgents.git)
> - 感谢 [shareAI-lab](https://github.com/shareAI-lab) 的[Kode-Cli](https://github.com/shareAI-lab/Kode-cli.git)项目
> - 感谢 [MiniMax-AI](https://github.com/MiniMax-AI)的[Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent)项目
> - 感谢[anomalyco](https://github.com/anomalyco)的**[opencode](https://github.com/anomalyco/opencode)**项目

---

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_message.py -v

# 运行测试并查看覆盖率
python -m pytest tests/ --cov=.
```

---

## 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 代码规范

- 使用 4 空格缩进（PEP 8）
- 类名使用 PascalCase
- 函数和变量使用 snake_case
- 常量使用 UPPER_SNAKE_CASE
- 函数必须添加类型注解
- 为新功能添加单元测试

---

## 常见问题

**Q: 如何启用 AgentTeams 功能？**

A: 设置环境变量 `ENABLE_AGENT_TEAMS=true`，然后重启 CLI。

**Q: 工具调用失败怎么办？**

A: 使用 `--show-raw` 参数运行，查看详细错误信息。常见原因包括 API Key 配置错误或网络问题。如果连续失败，系统会自动触发熔断机制，临时禁用该工具。

**Q: 如何调试上下文压缩问题？**

A: 设置 `TRACE_ENABLED=true` 并查看 `memory/traces/` 目录下的日志文件。

**Q: 支持哪些 LLM 提供商？**

A: 支持 OpenAI、Anthropic、Zhipu（智谱）等兼容 OpenAI API 格式的提供商。

**Q: 如何使用持久化记忆功能？**

A: 在对话中使用 `memory` 工具，支持添加、更新、删除、搜索记忆。高优先级记忆会自动注入到每次对话的上下文中。

**Q: 如何使用 Weather 工具？**

A: Weather 工具基于 Open-Meteo API，无需 API Key。支持查询中国主要城市和全球城市的天气信息。

**Q: 如何恢复会话？**

A: 使用 `/load` 命令恢复之前保存的会话。系统支持完整的状态恢复，包括历史记录和工具状态。

**Q: Token 估算不准确怎么办？**

A: 安装 `tiktoken` 库可以获得更精确的 Token 计数：`pip install tiktoken`

---

## License

本项目采用 MIT 许可证 授权。
