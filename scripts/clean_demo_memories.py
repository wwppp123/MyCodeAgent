"""清理示例记忆数据，保留用户真实信息"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory_store import MemoryStore

def clean_demo_memories():
    """清理演示脚本创建的示例数据"""
    
    memory_file = project_root / ".agent_memory" / "memory.json"
    store = MemoryStore(store_path=str(memory_file))
    
    print("=" * 70)
    print("清理示例记忆数据")
    print("=" * 70)
    
    # 查找示例数据（标题包含特定关键词）
    all_memories = store.list(limit=100)
    
    demo_keywords = ["张三", "VS Code", "scikit-learn", "机器学习项目"]
    
    deleted_count = 0
    for memory in all_memories:
        # 检查是否是演示数据
        is_demo = any(keyword in memory.content for keyword in demo_keywords)
        
        if is_demo:
            print(f"\n[删除示例数据] {memory.title}")
            print(f"  内容: {memory.content}")
            store.delete(memory.id)
            deleted_count += 1
    
    print("\n" + "=" * 70)
    print(f"清理完成: 删除了 {deleted_count} 条示例数据")
    print("=" * 70)
    
    # 显示剩余的真实数据
    remaining = store.list(limit=10)
    if remaining:
        print("\n保留的真实记忆:")
        for mem in remaining:
            print(f"\n  [{mem.category}] {mem.title}")
            print(f"  内容: {mem.content}")
            print(f"  优先级: {mem.priority}")
    else:
        print("\n当前没有记忆数据")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    clean_demo_memories()
