"""Quick test for checkpoint mechanism."""
import tempfile, os, json, sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.session_store import (
    save_checkpoint, load_checkpoint, mark_checkpoint_completed,
    clear_checkpoint, build_session_snapshot,
)

# Build a test snapshot
snapshot = build_session_snapshot(
    system_messages=[{"role": "system", "content": "test"}],
    history_messages=[
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi", "metadata": {"step": 1, "action_type": "tool_call", "tool_calls": [{"name": "Bash", "id": "c1", "arguments": {}}]}},
        {"role": "tool", "content": "result", "metadata": {"step": 1, "tool_name": "Bash", "tool_call_id": "c1"}},
    ],
    tool_schema=[],
    project_root="/tmp/test",
)

# Test save
cp_path = os.path.join(tempfile.mkdtemp(), "test_checkpoint.json")
save_checkpoint(cp_path, snapshot, "hello", 1)
print("1. save_checkpoint OK")

# Test load
cp = load_checkpoint(cp_path)
assert cp is not None
assert cp["checkpoint_status"] == "running"
assert cp["checkpoint_pending_input"] == "hello"
assert cp["checkpoint_current_step"] == 1
assert len(cp["history_messages"]) == 3
print("2. load_checkpoint OK - status=running, step=1, history=3 msgs")

# Test mark completed
mark_checkpoint_completed(cp_path)
cp2 = load_checkpoint(cp_path)
assert cp2 is None  # should not be resumable
print("3. mark_checkpoint_completed OK - no longer resumable")

# Test clear
save_checkpoint(cp_path, snapshot, "test", 2)
assert os.path.exists(cp_path)
clear_checkpoint(cp_path)
assert not os.path.exists(cp_path)
print("4. clear_checkpoint OK")

# Test load nonexistent
cp3 = load_checkpoint("/nonexistent/path.json")
assert cp3 is None
print("5. load nonexistent OK - returns None")

print()
print("All checkpoint tests PASSED!")
