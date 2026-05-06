"""Test tool response format in messages"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from core.context_engine.history_manager import HistoryManager
from core.config import Config

# Create history manager
hm = HistoryManager(Config())

# Simulate a conversation
hm.append_user("今天重庆天气怎么样？")
hm.append_assistant(
    content="",
    metadata={
        "action_type": "tool_call",
        "tool_calls": [{"id": "call_123", "name": "weather", "arguments": {"city": "重庆"}}],
    }
)

# Simulate tool result with standard response format
tool_result = {
    "status": "success",
    "data": {"temp": 25, "humidity": 60},
    "text": "重庆：25°C，晴朗，湿度 60%",
    "stats": {"time_ms": 500},
    "context": {"cwd": "."}
}

hm.append_tool(
    tool_name="weather",
    raw_result=json.dumps(tool_result, ensure_ascii=False),
    metadata={"step": 1, "tool_call_id": "call_123"}
)

# Convert to messages
messages = hm.to_messages()

print("=== Messages for LLM ===")
for i, msg in enumerate(messages):
    print(f"\nMessage {i}:")
    print(f"  role: {msg['role']}")
    content = msg.get('content', '')
    if len(content) > 100:
        content = content[:100] + '...'
    print(f"  content: {content}")
    if 'tool_call_id' in msg:
        print(f"  tool_call_id: {msg['tool_call_id']}")

# Check if tool message has simplified content
tool_msg = messages[-1]
if tool_msg['role'] == 'tool':
    print("\n=== Verification ===")
    if tool_msg['content'] == "重庆：25°C，晴朗，湿度 60%":
        print("SUCCESS: Tool message content is simplified text!")
    else:
        print(f"UNEXPECTED: Tool message content = {tool_msg['content'][:50]}...")
