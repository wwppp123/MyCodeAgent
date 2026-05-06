"""Memory Tool - 记忆管理工具

提供记忆的增删改查接口,让 Agent 能够:
- 记住用户偏好和重要信息
- 在后续会话中自动回忆这些信息
- 管理个人知识库
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import Tool, ToolParameter, ErrorCode
from core.memory_store import MemoryStore


class MemoryTool(Tool):
    """记忆管理工具"""
    
    def __init__(self, project_root: str, memory_store: Optional[MemoryStore] = None):
        """初始化记忆工具"""
        super().__init__(
            name="memory",
            description="管理长期记忆,用于保存和检索重要信息、用户偏好等。记忆会在所有会话中持久保存。",
            project_root=Path(project_root) if project_root else None
        )
        self.memory_store = memory_store or MemoryStore()
    
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description="操作类型: add(添加), update(更新), delete(删除), list(列出), search(搜索), get(获取), stats(统计)",
                required=True,
            ),
            ToolParameter(
                name="id",
                type="string",
                description="记忆ID(用于 update/delete/get 操作)",
                required=False,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="记忆标题(用于 add/update 操作)",
                required=False,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="记忆内容(用于 add/update 操作)",
                required=False,
            ),
            ToolParameter(
                name="category",
                type="string",
                description="记忆分类: user_preference(用户偏好), important_info(重要信息), working_context(工作上下文), general(一般信息)",
                required=False,
                default="general"
            ),
            ToolParameter(
                name="priority",
                type="string",
                description="优先级: high(高,会自动注入上下文), medium(中), low(低)",
                required=False,
                default="medium"
            ),
            ToolParameter(
                name="tags",
                type="array",
                description="标签列表(用于分类和检索)",
                required=False,
                default=[]
            ),
            ToolParameter(
                name="query",
                type="string",
                description="搜索关键词(用于 search 操作)",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="返回数量限制(用于 list/search 操作)",
                required=False,
                default=10
            ),
        ]
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """执行记忆操作"""
        start_time = time.time()
        action = parameters.get("action")
        
        try:
            if action == "add":
                result = self._handle_add(parameters)
            elif action == "update":
                result = self._handle_update(parameters)
            elif action == "delete":
                result = self._handle_delete(parameters)
            elif action == "list":
                result = self._handle_list(parameters)
            elif action == "search":
                result = self._handle_search(parameters)
            elif action == "get":
                result = self._handle_get(parameters)
            elif action == "stats":
                result = self._handle_stats()
            else:
                return self.create_error_response(
                    error_code=ErrorCode.INVALID_PARAM,
                    message=f"未知操作: {action}",
                    params_input=parameters,
                    time_ms=0,
                )
            
            # 计算执行时间
            time_ms = int((time.time() - start_time) * 1000)
            
            # 包装成标准响应格式
            result_dict = json.loads(result)
            if result_dict.get("status") == "success":
                data = result_dict.get("data", {})
                # 为不同操作生成合适的文本响应
                if action == "list":
                    total = data.get("total", 0)
                    memories = data.get("memories", [])
                    if not memories:
                        text = f"没有找到记忆（共 {total} 条）"
                    else:
                        text = f"找到 {total} 条记忆：\n" + "\n".join(
                            f"- {m.get('title')} (ID: {m.get('id')}, 分类: {m.get('category')}, 更新: {m.get('updated_at', '')[:19]})" 
                            for m in memories
                        )
                elif action == "stats":
                    total = data.get("total", 0)
                    categories = data.get("categories", {})
                    priorities = data.get("priorities", {})
                    text = f"记忆统计：共 {total} 条\n分类：{categories}\n优先级：{priorities}"
                else:
                    text = data.get("message", "操作成功")
                
                return self.create_success_response(
                    data=data,
                    text=text,
                    params_input=parameters,
                    time_ms=time_ms,
                )
            else:
                return self.create_error_response(
                    error_code=ErrorCode.INTERNAL_ERROR,
                    message=result_dict.get("error", {}).get("message", "操作失败"),
                    params_input=parameters,
                    time_ms=time_ms,
                )
        except Exception as e:
            time_ms = int((time.time() - start_time) * 1000)
            return self.create_error_response(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"操作失败: {str(e)}",
                params_input=parameters,
                time_ms=time_ms,
            )
    
    def _handle_add(self, args: Dict[str, Any]) -> str:
        """添加记忆"""
        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        
        if not title or not content:
            return self._error_response("title 和 content 不能为空")
        
        category = args.get("category", "general")
        priority = args.get("priority", "medium")
        tags = args.get("tags", [])
        
        memory = self.memory_store.add(
            title=title,
            content=content,
            category=category,
            priority=priority,
            tags=tags,
        )
        
        return self._success_response({
            "id": memory.id,
            "title": memory.title,
            "message": f"已成功添加记忆: {memory.title}",
            "note": "记忆已持久化保存,将在后续会话中自动回忆" if priority == "high" else "记忆已保存"
        })
    
    def _handle_update(self, args: Dict[str, Any]) -> str:
        """更新记忆"""
        memory_id = args.get("id", "").strip()
        if not memory_id:
            return self._error_response("id 不能为空")
        
        memory = self.memory_store.update(
            memory_id=memory_id,
            title=args.get("title"),
            content=args.get("content"),
            category=args.get("category"),
            priority=args.get("priority"),
            tags=args.get("tags"),
        )
        
        if not memory:
            return self._error_response(f"记忆不存在: {memory_id}")
        
        return self._success_response({
            "id": memory.id,
            "title": memory.title,
            "message": f"已成功更新记忆: {memory.title}"
        })
    
    def _handle_delete(self, args: Dict[str, Any]) -> str:
        """删除记忆"""
        memory_id = args.get("id", "").strip()
        if not memory_id:
            return self._error_response("id 不能为空")
        
        success = self.memory_store.delete(memory_id)
        if not success:
            return self._error_response(f"记忆不存在: {memory_id}")
        
        return self._success_response({
            "id": memory_id,
            "message": "已成功删除记忆"
        })
    
    def _handle_list(self, args: Dict[str, Any]) -> str:
        """列出记忆"""
        category = args.get("category")
        priority = args.get("priority")
        tags = args.get("tags")
        limit = args.get("limit", 10)
        
        memories = self.memory_store.list(
            category=category,
            priority=priority,
            tags=tags,
            limit=limit,
        )
        
        return self._success_response({
            "total": len(memories),
            "memories": [
                {
                    "id": m.id,
                    "title": m.title,
                    "content": m.content[:200] + ("..." if len(m.content) > 200 else ""),
                    "category": m.category,
                    "priority": m.priority,
                    "tags": m.tags,
                    "updated_at": m.updated_at,
                }
                for m in memories
            ]
        })
    
    def _handle_search(self, args: Dict[str, Any]) -> str:
        """搜索记忆"""
        query = args.get("query", "").strip()
        if not query:
            return self._error_response("query 不能为空")
        
        limit = args.get("limit", 10)
        memories = self.memory_store.search(query, limit=limit)
        
        return self._success_response({
            "query": query,
            "total": len(memories),
            "memories": [
                {
                    "id": m.id,
                    "title": m.title,
                    "content": m.content[:300] + ("..." if len(m.content) > 300 else ""),
                    "category": m.category,
                    "priority": m.priority,
                    "tags": m.tags,
                    "updated_at": m.updated_at,
                }
                for m in memories
            ]
        })
    
    def _handle_get(self, args: Dict[str, Any]) -> str:
        """获取单个记忆"""
        memory_id = args.get("id", "").strip()
        if not memory_id:
            return self._error_response("id 不能为空")
        
        memory = self.memory_store.get(memory_id)
        if not memory:
            return self._error_response(f"记忆不存在: {memory_id}")
        
        return self._success_response({
            "id": memory.id,
            "title": memory.title,
            "content": memory.content,
            "category": memory.category,
            "priority": memory.priority,
            "tags": memory.tags,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
        })
    
    def _handle_stats(self) -> str:
        """获取统计信息"""
        stats = self.memory_store.stats()
        return self._success_response(stats)
    
    def _success_response(self, data: Any) -> str:
        """成功响应"""
        return json.dumps({
            "status": "success",
            "data": data,
        }, ensure_ascii=False, indent=2)
    
    def _error_response(self, message: str) -> str:
        """错误响应"""
        return json.dumps({
            "status": "error",
            "error": {
                "code": "MEMORY_ERROR",
                "message": message,
            },
        }, ensure_ascii=False, indent=2)
