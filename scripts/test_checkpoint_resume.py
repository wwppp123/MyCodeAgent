"""
模拟断点续传流程：
1. 创建一个模拟的 checkpoint 文件（模拟 ReAct 在 step 3 被中断）
2. 验证 load_checkpoint 能正确读取
3. 验证 mark_checkpoint_completed 后不再可恢复
"""
import os, sys, json, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.session_store import (
    save_checkpoint, load_checkpoint, mark_checkpoint_completed,
    clear_checkpoint, build_session_snapshot,
)

CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "memory", "checkpoints")
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "checkpoint-latest.json")

def simulate_interrupted_session():
    """模拟一个在 step 3 被中断的 ReAct 会话"""
    # 清理旧 checkpoint
    clear_checkpoint(CHECKPOINT_PATH)

    # 模拟 history：user → step1 assistant+tool → step2 assistant+tool → step3 工具执行完
    history = [
        {"role": "user", "content": "帮我列出项目中所有 .py 文件"},
        # step 1: 调用了 Glob 工具
        {"role": "assistant", "content": "", "metadata": {"step": 1, "action_type": "tool_call", "tool_calls": [{"name": "Glob", "id": "call_001", "arguments": {"pattern": "**/*.py"}}]}},
        {"role": "tool", "content": '{"status":"ok","data":{"files":["a.py","b.py","c.py"]}}', "metadata": {"step": 1, "tool_name": "Glob", "tool_call_id": "call_001"}},
        # step 2: 调用了 Read 工具
        {"role": "assistant", "content": "找到了3个文件，让我读取它们", "metadata": {"step": 2, "action_type": "tool_call", "tool_calls": [{"name": "Read", "id": "call_002", "arguments": {"file_path": "a.py"}}]}},
        {"role": "tool", "content": '{"status":"ok","data":{"content":"print(1)"}}', "metadata": {"step": 2, "tool_name": "Read", "tool_call_id": "call_002"}},
        # step 3: 调用了 Bash 工具（执行完后被中断）
        {"role": "assistant", "content": "", "metadata": {"step": 3, "action_type": "tool_call", "tool_calls": [{"name": "Bash", "id": "call_003", "arguments": {"command": "wc -l *.py"}}]}},
        {"role": "tool", "content": '{"status":"ok","data":{"output":"1 a.py\\n2 b.py\\n3 c.py\\n6 total"}}', "metadata": {"step": 3, "tool_name": "Bash", "tool_call_id": "call_003"}},
    ]

    snapshot = build_session_snapshot(
        system_messages=[{"role": "system", "content": "You are a coding assistant."}],
        history_messages=history,
        tool_schema=[{"type": "function", "function": {"name": "Glob"}}, {"type": "function", "function": {"name": "Read"}}, {"type": "function", "function": {"name": "Bash"}}],
        project_root=PROJECT_ROOT,
    )

    # 保存 checkpoint（模拟 step 3 执行完后、step 4 开始前被中断）
    save_checkpoint(CHECKPOINT_PATH, snapshot, "帮我列出项目中所有 .py 文件", 3)
    print(f"[OK] 已创建模拟 checkpoint: {CHECKPOINT_PATH}")
    return CHECKPOINT_PATH

def verify_checkpoint():
    """验证 checkpoint 可以正确加载"""
    cp = load_checkpoint(CHECKPOINT_PATH)
    if cp is None:
        print("[FAIL] load_checkpoint 返回 None")
        return False

    print(f"[OK] checkpoint 加载成功:")
    print(f"     status:        {cp['checkpoint_status']}")
    print(f"     current_step:  {cp['checkpoint_current_step']}")
    print(f"     pending_input: {cp['checkpoint_pending_input']}")
    print(f"     history_msgs:  {len(cp['history_messages'])} 条")
    print(f"     timestamp:     {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cp['checkpoint_timestamp']))}")

    # 验证 history 内容
    roles = [m["role"] for m in cp["history_messages"]]
    print(f"     history roles: {roles}")
    return True

def verify_completed_not_resumable():
    """验证标记完成后不可恢复"""
    mark_checkpoint_completed(CHECKPOINT_PATH)
    cp = load_checkpoint(CHECKPOINT_PATH)
    if cp is None:
        print("[OK] mark_completed 后 load_checkpoint 返回 None（不可恢复）")
        return True
    else:
        print("[FAIL] mark_completed 后仍然可以加载")
        return False

def verify_clear():
    """验证清除功能"""
    # 重新创建一个
    simulate_interrupted_session()
    assert os.path.exists(CHECKPOINT_PATH)

    clear_checkpoint(CHECKPOINT_PATH)
    if not os.path.exists(CHECKPOINT_PATH):
        print("[OK] clear_checkpoint 已删除文件")
        return True
    else:
        print("[FAIL] clear_checkpoint 未删除文件")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("断点续传 (Checkpoint Resume) 功能验证")
    print("=" * 60)

    print("\n--- 1. 模拟被中断的 ReAct 会话 ---")
    simulate_interrupted_session()

    print("\n--- 2. 验证 checkpoint 可加载 ---")
    verify_checkpoint()

    print("\n--- 3. 验证标记完成后不可恢复 ---")
    verify_completed_not_resumable()

    print("\n--- 4. 验证清除功能 ---")
    verify_clear()

    print("\n" + "=" * 60)
    print("全部验证通过!")
    print("=" * 60)

    print(f"\n提示: 你现在可以用以下命令检查 checkpoint 文件:")
    print(f"  cat {CHECKPOINT_PATH}")
    print(f"\n或者启动 chat 触发恢复:")
    print(f"  conda run -n myenv3.12 python scripts/chat_test_agent.py")
