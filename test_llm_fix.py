#!/usr/bin/env python3
"""测试 LLM 修复效果"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import HelloAgentsLLM

# 测试 LLM 连接和响应
def test_llm_connection():
    print("=== 测试 LLM 连接 ===")
    try:
        llm = HelloAgentsLLM()
        print(f"LLM 初始化成功")
        print(f"Provider: {llm.provider}")
        print(f"Model: {llm.model}")
        print(f"Base URL: {llm.base_url}")
        
        # 测试简单请求
        messages = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "1+1=?"}
        ]
        
        print("\n=== 测试简单请求 ===")
        response = llm.invoke(messages)
        print(f"响应: {response}")
        print("测试成功!")
        
        # 测试带工具的请求
        print("\n=== 测试带工具的请求 ===")
        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "memory",
                    "description": "管理长期记忆",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "操作类型"
                            }
                        },
                        "required": ["action"]
                    }
                }
            }
        ]
        
        messages_with_tools = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "列出所有记忆"}
        ]
        
        response_raw = llm.invoke_raw(messages_with_tools, tools=tools_schema, tool_choice="auto")
        print(f"带工具的响应: {response_raw}")
        print("工具测试成功!")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_connection()
