"""
演示持久化记忆功能的使用

⚠️ 注意: 此脚本会创建示例数据到真实的记忆文件中！
建议: 使用后运行清理脚本删除示例数据
清理命令: python scripts/clean_demo_memories.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory_store import MemoryStore

def demo_memory_usage():
    """演示记忆功能的使用"""
    
    print("=" * 70)
    print("持久化记忆系统演示")
    print("=" * 70)
    
    # 使用项目根目录下的记忆存储
    memory_file = project_root / ".agent_memory" / "memory.json"
    store = MemoryStore(store_path=str(memory_file))
    
    print(f"\n[File] 记忆存储位置: {memory_file}")
    print(f"[Stats] 当前记忆数量: {store.stats()['total']}")
    
    # 演示场景1: 用户介绍
    print("\n" + "=" * 70)
    print("场景 1: 用户介绍自己")
    print("=" * 70)
    
    print("\n[User] '你好,我叫张三,是一名Python开发工程师'")
    print("\n[Agent] 应该:")
    print("   -> 自动调用 memory 工具保存这个信息")
    
    memory1 = store.add(
        title="用户身份信息",
        content="用户姓名: 张三, 职业: Python开发工程师",
        category="user_preference",
        priority="high",
        tags=["identity", "personal", "python"]
    )
    print(f"\n[OK] 已保存记忆: {memory1.title} (ID: {memory1.id[:8]}...)")
    
    # 演示场景2: 用户偏好
    print("\n" + "=" * 70)
    print("场景 2: 用户表达偏好")
    print("=" * 70)
    
    print("\n[User] '我喜欢使用VS Code编辑器,偏好使用类型注解'")
    print("\n[Agent] 应该:")
    print("   -> 自动调用 memory 工具保存偏好")
    
    memory2 = store.add(
        title="开发工具偏好",
        content="偏好使用VS Code编辑器,喜欢在代码中使用类型注解",
        category="user_preference",
        priority="high",
        tags=["tools", "vscode", "coding-style"]
    )
    print(f"\n[OK] 已保存记忆: {memory2.title} (ID: {memory2.id[:8]}...)")
    
    # 演示场景3: 当前工作
    print("\n" + "=" * 70)
    print("场景 3: 用户描述当前工作")
    print("=" * 70)
    
    print("\n[User] '我正在开发一个机器学习项目,使用scikit-learn'")
    print("\n[Agent] 应该:")
    print("   -> 自动调用 memory 工具保存工作上下文")
    
    memory3 = store.add(
        title="当前项目",
        content="正在开发机器学习项目,使用scikit-learn框架",
        category="working_context",
        priority="high",
        tags=["project", "machine-learning", "scikit-learn"]
    )
    print(f"\n[OK] 已保存记忆: {memory3.title} (ID: {memory3.id[:8]}...)")
    
    # 演示自动注入
    print("\n" + "=" * 70)
    print("场景 4: 新会话自动回忆")
    print("=" * 70)
    
    print("\n[Agent] 在新的会话中,会自动回忆高优先级记忆:")
    context_text = store.get_memories_for_context(max_chars=500)
    print("\n" + context_text)
    
    # 演示搜索
    print("\n" + "=" * 70)
    print("场景 5: 搜索历史记忆")
    print("=" * 70)
    
    print("\n[User] '你还记得我用什么编辑器吗?'")
    print("\n[Agent] 搜索记忆:")
    results = store.search("编辑器")
    if results:
        print(f"\n   找到记忆: {results[0].title}")
        print(f"   内容: {results[0].content}")
    
    # 显示统计
    print("\n" + "=" * 70)
    print("[Stats] 记忆统计")
    print("=" * 70)
    
    stats = store.stats()
    print(f"\n总记忆数: {stats['total']}")
    print(f"分类统计: {stats['categories']}")
    print(f"优先级统计: {stats['priorities']}")
    
    print("\n" + "=" * 70)
    print("[SUCCESS] 演示完成!")
    print("=" * 70)
    
    print("\n[KEY POINTS] 关键要点:")
    print("   1. 当用户介绍自己时 -> 自动保存身份信息")
    print("   2. 当用户表达偏好时 -> 自动保存偏好设置")
    print("   3. 当用户描述工作时 -> 自动保存工作上下文")
    print("   4. 高优先级记忆会自动注入到后续对话中")
    print("   5. 无需用户明确要求,Agent应主动记住重要信息")
    print("\n[NEXT] 现在你可以在实际对话中测试这个功能了!")
    print("   启动Agent后,试着说: '你好,我叫XXX,是一名XXX'")
    print("   Agent应该会自动保存你的信息!")

if __name__ == "__main__":
    demo_memory_usage()
