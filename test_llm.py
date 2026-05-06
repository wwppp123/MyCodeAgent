#!/usr/bin/env python3
"""测试 LLM 响应问题"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import HelloAgentsLLM

# 测试 LLM 连接
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
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_connection()
