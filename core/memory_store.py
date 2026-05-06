"""持久化记忆存储系统

提供跨会话的长期记忆管理,支持:
- 用户偏好设置
- 重要信息记录
- 工作上下文保存
- 分类与标签管理

记忆会在每次会话启动时自动注入到上下文中。
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import threading


class Memory:
    """记忆条目"""
    
    def __init__(
        self,
        title: str,
        content: str,
        category: str = "general",
        priority: str = "medium",
        tags: Optional[List[str]] = None,
        memory_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.id = memory_id or str(uuid.uuid4())
        self.title = title
        self.content = content
        self.category = category
        self.priority = priority
        self.tags = tags or []
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "priority": self.priority,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """从字典创建"""
        return cls(
            memory_id=data.get("id"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            category=data.get("category", "general"),
            priority=data.get("priority", "medium"),
            tags=data.get("tags", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    def update(
        self,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """更新记忆"""
        if title is not None:
            self.title = title
        if content is not None:
            self.content = content
        if category is not None:
            self.category = category
        if priority is not None:
            self.priority = priority
        if tags is not None:
            self.tags = tags
        self.updated_at = datetime.now().isoformat()


class MemoryStore:
    """
    持久化记忆存储管理器
    
    使用 JSON 文件存储记忆,支持:
    - 添加/更新/删除/查询记忆
    - 按分类、标签、优先级过滤
    - 关键词搜索
    - 自动持久化
    
    线程安全: 使用锁保护文件操作
    """
    
    # 优先级权重(用于排序)
    PRIORITY_WEIGHTS = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }
    
    def __init__(self, store_path: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        初始化记忆存储
        
        Args:
            store_path: 存储文件路径,默认为 .agent_memory/memory.json
            logger: 日志记录器
        """
        self.store_path = Path(store_path or ".agent_memory/memory.json")
        self.logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._memories: Dict[str, Memory] = {}
        self._load()
    
    def _load(self):
        """从文件加载记忆"""
        if not self.store_path.exists():
            self.logger.info("Memory store not found, creating new store at %s", self.store_path)
            self._memories = {}
            self._save()
            return
        
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._memories = {
                mem_id: Memory.from_dict(mem_data)
                for mem_id, mem_data in data.get("memories", {}).items()
            }
            self.logger.info("Loaded %d memories from %s", len(self._memories), self.store_path)
        except Exception as e:
            self.logger.error("Failed to load memory store: %s", e)
            self._memories = {}
    
    def _save(self):
        """保存记忆到文件"""
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "memories": {
                    mem_id: mem.to_dict()
                    for mem_id, mem in self._memories.items()
                }
            }
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.debug("Saved %d memories to %s", len(self._memories), self.store_path)
        except Exception as e:
            self.logger.error("Failed to save memory store: %s", e)
    
    def add(
        self,
        title: str,
        content: str,
        category: str = "general",
        priority: str = "medium",
        tags: Optional[List[str]] = None,
    ) -> Memory:
        """
        添加新记忆
        
        Args:
            title: 记忆标题
            content: 记忆内容
            category: 分类(如 user_preference, important_info, working_context)
            priority: 优先级(high, medium, low)
            tags: 标签列表
        
        Returns:
            创建的记忆对象
        """
        with self._lock:
            memory = Memory(
                title=title,
                content=content,
                category=category,
                priority=priority,
                tags=tags,
            )
            self._memories[memory.id] = memory
            self._save()
            self.logger.info("Added memory: %s (category=%s, priority=%s)", title, category, priority)
            return memory
    
    def update(
        self,
        memory_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Memory]:
        """
        更新记忆
        
        Args:
            memory_id: 记忆ID
            title: 新标题(可选)
            content: 新内容(可选)
            category: 新分类(可选)
            priority: 新优先级(可选)
            tags: 新标签列表(可选)
        
        Returns:
            更新后的记忆对象,如果记忆不存在则返回 None
        """
        with self._lock:
            memory = self._memories.get(memory_id)
            if not memory:
                self.logger.warning("Memory not found: %s", memory_id)
                return None
            
            memory.update(title=title, content=content, category=category, priority=priority, tags=tags)
            self._save()
            self.logger.info("Updated memory: %s", memory.title)
            return memory
    
    def delete(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
        
        Returns:
            是否成功删除
        """
        with self._lock:
            if memory_id not in self._memories:
                self.logger.warning("Memory not found for deletion: %s", memory_id)
                return False
            
            del self._memories[memory_id]
            self._save()
            self.logger.info("Deleted memory: %s", memory_id)
            return True
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """
        获取单个记忆
        
        Args:
            memory_id: 记忆ID
        
        Returns:
            记忆对象,如果不存在则返回 None
        """
        return self._memories.get(memory_id)
    
    def list(
        self,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Memory]:
        """
        列出记忆
        
        Args:
            category: 按分类过滤(可选)
            priority: 按优先级过滤(可选)
            tags: 按标签过滤(可选,记忆需包含所有指定标签)
            limit: 返回数量限制
        
        Returns:
            记忆列表,按优先级和更新时间排序
        """
        memories = list(self._memories.values())
        
        # 过滤
        if category:
            memories = [m for m in memories if m.category == category]
        
        if priority:
            memories = [m for m in memories if m.priority == priority]
        
        if tags:
            memories = [m for m in memories if all(tag in m.tags for tag in tags)]
        
        # 排序: 按优先级降序,然后按更新时间降序
        memories.sort(
            key=lambda m: (
                self.PRIORITY_WEIGHTS.get(m.priority, 0),
                m.updated_at or ""
            ),
            reverse=True
        )
        
        return memories[:limit]
    
    def search(self, query: str, limit: int = 20) -> List[Memory]:
        """
        搜索记忆
        
        Args:
            query: 搜索关键词(在标题和内容中搜索)
            limit: 返回数量限制
        
        Returns:
            匹配的记忆列表
        """
        query_lower = query.lower()
        memories = [
            m for m in self._memories.values()
            if query_lower in m.title.lower() or query_lower in m.content.lower()
        ]
        
        # 排序
        memories.sort(
            key=lambda m: (
                self.PRIORITY_WEIGHTS.get(m.priority, 0),
                m.updated_at or ""
            ),
            reverse=True
        )
        
        return memories[:limit]
    
    def get_high_priority_memories(self) -> List[Memory]:
        """获取所有高优先级记忆(用于上下文注入)"""
        return self.list(priority="high", limit=100)
    
    def get_memories_for_context(self, max_chars: int = 2000) -> str:
        """
        生成用于注入上下文的记忆摘要
        
        Args:
            max_chars: 最大字符数限制
        
        Returns:
            格式化的记忆文本
        """
        memories = self.get_high_priority_memories()
        if not memories:
            return ""
        
        lines = ["## 长期记忆"]
        total_chars = len(lines[0])
        
        for mem in memories:
            entry = f"- [{mem.category}] {mem.title}: {mem.content}"
            if total_chars + len(entry) > max_chars:
                break
            lines.append(entry)
            total_chars += len(entry)
        
        if len(lines) > 1:
            return "\n".join(lines)
        return ""
    
    def clear(self):
        """清空所有记忆"""
        with self._lock:
            self._memories.clear()
            self._save()
            self.logger.warning("Cleared all memories")
    
    def stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        total = len(self._memories)
        categories = {}
        priorities = {}
        
        for mem in self._memories.values():
            categories[mem.category] = categories.get(mem.category, 0) + 1
            priorities[mem.priority] = priorities.get(mem.priority, 0) + 1
        
        return {
            "total": total,
            "categories": categories,
            "priorities": priorities,
        }
