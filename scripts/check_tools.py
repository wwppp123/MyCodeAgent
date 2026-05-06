"""Check registered tools"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.registry import ToolRegistry
from tools.builtin.weather import WeatherTool

# Create registry
registry = ToolRegistry()

# Register weather tool
registry.register_tool(WeatherTool('.'))

# List tools
print("=== Registered Tools ===")
tools = registry.list_tools()
print(f"Type: {type(tools)}")
print(f"Content: {tools}")

for tool_name in tools:
    print(f"\nTool: {tool_name}")
    tool = registry.get_tool(tool_name)
    if tool:
        print(f"  Description: {tool.description}")
        print(f"  Parameters: {tool.get_parameters()}")

# Get tool schema for LLM
print("\n=== Tool Schema for LLM ===")
schema = registry.get_tools_schema()
import json
print(json.dumps(schema, ensure_ascii=False, indent=2))
