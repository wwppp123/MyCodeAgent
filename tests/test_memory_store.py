"""测试持久化记忆系统"""

import json
import pytest
import tempfile
from pathlib import Path

from core.memory_store import Memory, MemoryStore
from tools.builtin.memory import MemoryTool


class TestMemory:
    """测试 Memory 类"""
    
    def test_create_memory(self):
        """测试创建记忆"""
        memory = Memory(
            title="测试记忆",
            content="这是测试内容",
            category="test",
            priority="high",
            tags=["tag1", "tag2"],
        )
        
        assert memory.title == "测试记忆"
        assert memory.content == "这是测试内容"
        assert memory.category == "test"
        assert memory.priority == "high"
        assert memory.tags == ["tag1", "tag2"]
        assert memory.id is not None
        assert memory.created_at is not None
        assert memory.updated_at is not None
    
    def test_memory_to_dict(self):
        """测试记忆序列化"""
        memory = Memory(
            title="测试",
            content="内容",
            category="general",
            priority="medium",
        )
        
        data = memory.to_dict()
        assert data["title"] == "测试"
        assert data["content"] == "内容"
        assert data["category"] == "general"
        assert data["priority"] == "medium"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_memory_from_dict(self):
        """测试记忆反序列化"""
        data = {
            "id": "test-id-123",
            "title": "测试标题",
            "content": "测试内容",
            "category": "user_preference",
            "priority": "high",
            "tags": ["important"],
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        
        memory = Memory.from_dict(data)
        assert memory.id == "test-id-123"
        assert memory.title == "测试标题"
        assert memory.content == "测试内容"
        assert memory.category == "user_preference"
        assert memory.priority == "high"
        assert memory.tags == ["important"]
    
    def test_memory_update(self):
        """测试记忆更新"""
        memory = Memory(
            title="原标题",
            content="原内容",
            priority="low",
        )
        
        old_updated_at = memory.updated_at
        memory.update(
            title="新标题",
            content="新内容",
            priority="high",
            tags=["new-tag"],
        )
        
        assert memory.title == "新标题"
        assert memory.content == "新内容"
        assert memory.priority == "high"
        assert memory.tags == ["new-tag"]
        assert memory.updated_at != old_updated_at


class TestMemoryStore:
    """测试 MemoryStore 类"""
    
    @pytest.fixture
    def temp_store(self):
        """创建临时记忆存储"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_memory.json"
            store = MemoryStore(store_path=str(store_path))
            yield store
    
    def test_add_memory(self, temp_store):
        """测试添加记忆"""
        memory = temp_store.add(
            title="测试添加",
            content="测试内容",
            category="test",
            priority="high",
            tags=["test"],
        )
        
        assert memory.id is not None
        assert memory.title == "测试添加"
        assert memory.content == "测试内容"
        
        # 验证持久化
        assert temp_store.store_path.exists()
        with open(temp_store.store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert memory.id in data["memories"]
    
    def test_update_memory(self, temp_store):
        """测试更新记忆"""
        memory = temp_store.add(
            title="原标题",
            content="原内容",
        )
        
        updated = temp_store.update(
            memory_id=memory.id,
            title="新标题",
            content="新内容",
            priority="high",
        )
        
        assert updated is not None
        assert updated.title == "新标题"
        assert updated.content == "新内容"
        assert updated.priority == "high"
    
    def test_delete_memory(self, temp_store):
        """测试删除记忆"""
        memory = temp_store.add(
            title="待删除",
            content="内容",
        )
        
        success = temp_store.delete(memory.id)
        assert success is True
        
        deleted = temp_store.get(memory.id)
        assert deleted is None
    
    def test_list_memories(self, temp_store):
        """测试列出记忆"""
        temp_store.add("记忆1", "内容1", category="cat1", priority="high")
        temp_store.add("记忆2", "内容2", category="cat1", priority="medium")
        temp_store.add("记忆3", "内容3", category="cat2", priority="high")
        
        # 列出所有
        all_memories = temp_store.list(limit=10)
        assert len(all_memories) == 3
        
        # 按分类过滤
        cat1_memories = temp_store.list(category="cat1")
        assert len(cat1_memories) == 2
        
        # 按优先级过滤
        high_memories = temp_store.list(priority="high")
        assert len(high_memories) == 2
        
        # 按优先级排序验证
        assert high_memories[0].priority == "high"
        assert high_memories[1].priority == "high"
    
    def test_search_memories(self, temp_store):
        """测试搜索记忆"""
        temp_store.add("Python编程", "学习Python的基础知识")
        temp_store.add("JavaScript笔记", "前端开发相关")
        temp_store.add("Python进阶", "高级Python技巧")
        
        results = temp_store.search("Python", limit=10)
        assert len(results) == 2
        
        results = temp_store.search("前端", limit=10)
        assert len(results) == 1
        assert results[0].title == "JavaScript笔记"
    
    def test_get_memories_for_context(self, temp_store):
        """测试获取上下文记忆"""
        temp_store.add(
            "用户偏好",
            "喜欢使用Python进行数据分析",
            priority="high",
        )
        temp_store.add(
            "重要项目",
            "正在开发MyCodeAgent项目",
            priority="high",
        )
        temp_store.add(
            "临时笔记",
            "这是一个临时笔记",
            priority="low",
        )
        
        context = temp_store.get_memories_for_context(max_chars=1000)
        assert "长期记忆" in context
        assert "用户偏好" in context
        assert "重要项目" in context
        assert "临时笔记" not in context  # 低优先级不注入
    
    def test_stats(self, temp_store):
        """测试统计功能"""
        temp_store.add("记忆1", "内容1", category="cat1", priority="high")
        temp_store.add("记忆2", "内容2", category="cat1", priority="medium")
        temp_store.add("记忆3", "内容3", category="cat2", priority="low")
        
        stats = temp_store.stats()
        assert stats["total"] == 3
        assert stats["categories"]["cat1"] == 2
        assert stats["categories"]["cat2"] == 1
        assert stats["priorities"]["high"] == 1
        assert stats["priorities"]["medium"] == 1
        assert stats["priorities"]["low"] == 1
    
    def test_persistence(self):
        """测试持久化功能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_memory.json"
            
            # 创建并添加记忆
            store1 = MemoryStore(store_path=str(store_path))
            memory = store1.add("测试持久化", "内容")
            
            # 重新加载
            store2 = MemoryStore(store_path=str(store_path))
            loaded = store2.get(memory.id)
            
            assert loaded is not None
            assert loaded.title == "测试持久化"
            assert loaded.content == "内容"


class TestMemoryTool:
    """测试 MemoryTool 类"""
    
    @pytest.fixture
    def memory_tool(self):
        """创建记忆工具"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_memory.json"
            store = MemoryStore(store_path=str(store_path))
            tool = MemoryTool(project_root=tmpdir, memory_store=store)
            yield tool
    
    def test_add_memory(self, memory_tool):
        """测试工具添加记忆"""
        result = memory_tool.execute({
            "action": "add",
            "title": "测试记忆",
            "content": "这是测试内容",
            "category": "user_preference",
            "priority": "high",
            "tags": ["test"],
        })
        
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["data"]["title"] == "测试记忆"
        assert "id" in result_dict["data"]
    
    def test_list_memories(self, memory_tool):
        """测试工具列出记忆"""
        memory_tool.execute({
            "action": "add",
            "title": "记忆1",
            "content": "内容1",
        })
        memory_tool.execute({
            "action": "add",
            "title": "记忆2",
            "content": "内容2",
        })
        
        result = memory_tool.execute({
            "action": "list",
            "limit": 10,
        })
        
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["data"]["total"] == 2
    
    def test_search_memories(self, memory_tool):
        """测试工具搜索记忆"""
        memory_tool.execute({
            "action": "add",
            "title": "Python教程",
            "content": "学习Python编程",
        })
        memory_tool.execute({
            "action": "add",
            "title": "JavaScript教程",
            "content": "学习JavaScript",
        })
        
        result = memory_tool.execute({
            "action": "search",
            "query": "Python",
        })
        
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["data"]["total"] == 1
        assert "Python" in result_dict["data"]["memories"][0]["title"]
    
    def test_update_memory(self, memory_tool):
        """测试工具更新记忆"""
        add_result = memory_tool.execute({
            "action": "add",
            "title": "原标题",
            "content": "原内容",
        })
        memory_id = json.loads(add_result)["data"]["id"]
        
        update_result = memory_tool.execute({
            "action": "update",
            "id": memory_id,
            "title": "新标题",
            "content": "新内容",
        })
        
        result_dict = json.loads(update_result)
        assert result_dict["status"] == "success"
        assert result_dict["data"]["title"] == "新标题"
    
    def test_delete_memory(self, memory_tool):
        """测试工具删除记忆"""
        add_result = memory_tool.execute({
            "action": "add",
            "title": "待删除",
            "content": "内容",
        })
        memory_id = json.loads(add_result)["data"]["id"]
        
        delete_result = memory_tool.execute({
            "action": "delete",
            "id": memory_id,
        })
        
        result_dict = json.loads(delete_result)
        assert result_dict["status"] == "success"
        
        # 验证已删除
        get_result = memory_tool.execute({
            "action": "get",
            "id": memory_id,
        })
        get_dict = json.loads(get_result)
        assert get_dict["status"] == "error"
    
    def test_stats(self, memory_tool):
        """测试工具统计功能"""
        memory_tool.execute({
            "action": "add",
            "title": "记忆1",
            "content": "内容1",
            "category": "cat1",
            "priority": "high",
        })
        memory_tool.execute({
            "action": "add",
            "title": "记忆2",
            "content": "内容2",
            "category": "cat2",
            "priority": "medium",
        })
        
        result = memory_tool.execute({"action": "stats"})
        result_dict = json.loads(result)
        
        assert result_dict["status"] == "success"
        assert result_dict["data"]["total"] == 2
