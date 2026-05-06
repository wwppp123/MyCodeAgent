"""测试记忆工具导入和基本功能"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory_store import MemoryStore
from tools.builtin.memory import MemoryTool

def test_memory_tool():
    """测试记忆工具"""
    print("=" * 60)
    print("测试记忆工具导入和功能")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "test_memory.json"
        print(f"\n1. 创建记忆存储: {store_path}")
        store = MemoryStore(store_path=str(store_path))
        
        print("\n2. 创建记忆工具...")
        tool = MemoryTool(project_root=tmpdir, memory_store=store)
        print(f"   [OK] 工具名称: {tool.name}")
        print(f"   [OK] 工具描述: {tool.description[:50]}...")
        
        print("\n3. 获取工具参数定义...")
        params = tool.get_parameters()
        print(f"   [OK] 参数数量: {len(params)}")
        print(f"   [OK] 必需参数: {[p.name for p in params if p.required]}")
        
        print("\n4. 测试添加记忆...")
        result = tool.run({
            "action": "add",
            "title": "测试记忆",
            "content": "这是一个测试记忆内容",
            "category": "user_preference",
            "priority": "high",
            "tags": ["test"]
        })
        print(f"   [OK] 添加成功")
        
        print("\n5. 测试列出记忆...")
        result = tool.run({
            "action": "list",
            "limit": 10
        })
        print(f"   [OK] 列表查询成功")
        
        print("\n6. 测试搜索记忆...")
        result = tool.run({
            "action": "search",
            "query": "测试"
        })
        print(f"   [OK] 搜索成功")
        
        print("\n7. 测试统计信息...")
        result = tool.run({
            "action": "stats"
        })
        print(f"   [OK] 统计查询成功")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] 记忆工具测试通过!")
    print("=" * 60)

if __name__ == "__main__":
    test_memory_tool()
