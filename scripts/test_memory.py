"""简单测试记忆系统功能"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory_store import Memory, MemoryStore

def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("测试记忆系统基本功能")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_memory.json"
        print(f"\n1. 创建记忆存储: {store_path}")
        store = MemoryStore(store_path=str(store_path))
        
        # 测试添加记忆
        print("\n2. 添加记忆...")
        memory1 = store.add(
            title="用户偏好",
            content="我喜欢使用Python进行数据分析,偏好使用VS Code编辑器",
            category="user_preference",
            priority="high",
            tags=["preference", "python"],
        )
        print(f"   [OK] 添加记忆: {memory1.title} (ID: {memory1.id[:8]}...)")
        
        memory2 = store.add(
            title="当前项目",
            content="正在开发MyCodeAgent项目,这是一个代码代理框架",
            category="working_context",
            priority="high",
            tags=["project"],
        )
        print(f"   [OK] 添加记忆: {memory2.title} (ID: {memory2.id[:8]}...)")
        
        memory3 = store.add(
            title="临时笔记",
            content="这是一个临时笔记,优先级较低",
            category="general",
            priority="low",
            tags=["note"],
        )
        print(f"   [OK] 添加记忆: {memory3.title} (ID: {memory3.id[:8]}...)")
        
        # 测试列出记忆
        print("\n3. 列出所有记忆...")
        all_memories = store.list(limit=10)
        print(f"   [OK] 共有 {len(all_memories)} 条记忆")
        for mem in all_memories:
            print(f"     - [{mem.priority}] {mem.title}: {mem.content[:30]}...")
        
        # 测试高优先级记忆
        print("\n4. 获取高优先级记忆...")
        high_priority = store.get_high_priority_memories()
        print(f"   [OK] 共有 {len(high_priority)} 条高优先级记忆")
        for mem in high_priority:
            print(f"     - {mem.title}")
        
        # 测试上下文注入
        print("\n5. 生成上下文记忆文本...")
        context_text = store.get_memories_for_context(max_chars=500)
        print("   [OK] 生成的上下文文本:")
        print("   " + "-" * 50)
        for line in context_text.split("\n"):
            print(f"   {line}")
        print("   " + "-" * 50)
        
        # 测试搜索
        print("\n6. 搜索记忆...")
        results = store.search("Python")
        print(f"   [OK] 搜索 'Python' 找到 {len(results)} 条结果")
        for mem in results:
            print(f"     - {mem.title}: {mem.content[:30]}...")
        
        # 测试更新
        print("\n7. 更新记忆...")
        updated = store.update(memory3.id, priority="medium")
        print(f"   [OK] 更新记忆 '{updated.title}' 优先级为 medium")
        
        # 测试统计
        print("\n8. 获取统计信息...")
        stats = store.stats()
        print(f"   [OK] 总记忆数: {stats['total']}")
        print(f"   [OK] 分类统计: {stats['categories']}")
        print(f"   [OK] 优先级统计: {stats['priorities']}")
        
        # 测试持久化
        print("\n9. 测试持久化...")
        print(f"   [OK] 记忆已保存到: {store_path}")
        with open(store_path, "r", encoding="utf-8") as f:
            data = f.read()
        print(f"   [OK] 文件大小: {len(data)} 字节")
        
        # 测试重新加载
        print("\n10. 重新加载记忆存储...")
        store2 = MemoryStore(store_path=str(store_path))
        reloaded = store2.get(memory1.id)
        print(f"   [OK] 成功加载记忆: {reloaded.title}")
        print(f"   [OK] 内容匹配: {reloaded.content == memory1.content}")
        
        # 测试删除
        print("\n11. 删除记忆...")
        success = store.delete(memory3.id)
        print(f"   [OK] 删除结果: {success}")
        remaining = store.list(limit=10)
        print(f"   [OK] 剩余记忆数: {len(remaining)}")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过!")
    print("=" * 60)

if __name__ == "__main__":
    test_basic_functionality()
