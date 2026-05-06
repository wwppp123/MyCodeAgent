"""TokenEstimator 单元测试"""

import unittest
from unittest.mock import patch

from core.context_engine.token_estimator import TokenEstimator


class TestTokenEstimatorBasic(unittest.TestCase):
    """基本功能测试"""

    def test_empty_text(self):
        """空文本返回 0"""
        est = TokenEstimator()
        self.assertEqual(est.estimate_text(""), 0)
        self.assertEqual(est.estimate_text(None), 0)

    def test_english_text_reasonable_range(self):
        """英文文本估算应在合理范围内"""
        est = TokenEstimator()
        text = "Hello, how are you doing today?"
        tokens = est.estimate_text(text)
        # 约 8-10 tokens（cl100k_base）
        self.assertGreater(tokens, 3)
        self.assertLess(tokens, 30)

    def test_chinese_text_not_underestimated(self):
        """中文文本不应被严重低估（旧 //3 的问题）"""
        est = TokenEstimator()
        text = "你好，这是一段中文测试文本，用于验证 token 估算的准确性。"
        tokens = est.estimate_text(text)
        # 28 个中文字符，至少应估算为 28 token
        self.assertGreater(tokens, 20)

    def test_mixed_content(self):
        """混合中英文内容"""
        est = TokenEstimator()
        text = "function calculateSum(a, b) { return a + b; } // 计算求和"
        tokens = est.estimate_text(text)
        self.assertGreater(tokens, 10)

    def test_code_content(self):
        """代码内容（符号密集）"""
        est = TokenEstimator()
        code = '''
def hello():
    print("world")
    if x > 0:
        return [1, 2, 3]
'''
        tokens = est.estimate_text(code)
        self.assertGreater(tokens, 15)

    def test_short_text_fast_path(self):
        """短文本（<10字符）走快速路径"""
        est = TokenEstimator()
        tokens = est.estimate_text("hello")
        self.assertGreater(tokens, 0)


class TestTokenEstimatorModelSwitch(unittest.TestCase):
    """模型切换测试"""

    def test_set_model_changes_encoder(self):
        """切换模型应重置 encoder"""
        est = TokenEstimator(model="gpt-3.5-turbo")
        t1 = est.estimate_text("hello world")
        est.set_model("gpt-4o")
        # 不应崩溃，且可能返回不同值
        t2 = est.estimate_text("hello world")
        self.assertIsInstance(t2, int)
        self.assertGreater(t2, 0)

    def test_set_provider_changes_encoder(self):
        """切换供应商应重置 encoder"""
        est = TokenEstimator(provider="openai")
        t1 = est.estimate_text("hello world")
        est.set_provider("deepseek")
        t2 = est.estimate_text("hello world")
        self.assertIsInstance(t2, int)
        self.assertGreater(t2, 0)

    def test_same_model_no_reset(self):
        """相同模型不重置 encoder"""
        est = TokenEstimator(model="gpt-4o")
        est.estimate_text("hello")  # 触发 encoder 加载
        encoder1 = est._encoder
        est.set_model("gpt-4o")  # 相同模型
        self.assertIs(est._encoder, encoder1)

    def test_get_model_provider(self):
        """获取模型和供应商"""
        est = TokenEstimator(model="gpt-4o", provider="openai")
        self.assertEqual(est.get_model(), "gpt-4o")
        self.assertEqual(est.get_provider(), "openai")


class TestTokenEstimatorMessages(unittest.TestCase):
    """消息列表估算测试"""

    def test_empty_messages(self):
        """空消息列表"""
        est = TokenEstimator()
        tokens = est.estimate_messages([])
        self.assertEqual(tokens, 0)

    def test_single_user_message(self):
        """单条用户消息"""
        est = TokenEstimator()
        messages = [{"role": "user", "content": "hello"}]
        tokens = est.estimate_messages(messages)
        # 4 (overhead) + ~1 (role) + ~1 (content) = ~6
        self.assertGreater(tokens, 3)

    def test_messages_with_tool_calls(self):
        """消息列表含 tool_calls"""
        est = TokenEstimator()
        messages = [
            {"role": "user", "content": "list files"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "LS", "arguments": '{"path": "."}'}}
                ],
            },
            {"role": "tool", "content": "file1.py\nfile2.py"},
        ]
        tokens = est.estimate_messages(messages)
        self.assertGreater(tokens, 20)

    def test_messages_with_multimodal_content(self):
        """多模态消息（content 为列表）"""
        est = TokenEstimator()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe this image"},
                ],
            }
        ]
        tokens = est.estimate_messages(messages)
        self.assertGreater(tokens, 5)


class TestTokenEstimatorFallback(unittest.TestCase):
    """降级策略测试"""

    def test_heuristic_cjk_higher_than_slash_3(self):
        """启发式对中文的估算应显著高于 //3"""
        est = TokenEstimator()
        # 强制使用启发式
        est._tiktoken_available = False
        est._encoder_loaded = True
        est._encoder = None

        text = "你好世界" * 25  # 100 个中文字符
        heuristic = est.estimate_text(text)
        old_estimate = len(text) // 3  # = 33
        self.assertGreater(heuristic, old_estimate)

    def test_heuristic_english_reasonable(self):
        """启发式对英文的估算应合理"""
        est = TokenEstimator()
        est._tiktoken_available = False
        est._encoder_loaded = True
        est._encoder = None

        text = "Hello, how are you doing today?"  # ~30 chars
        tokens = est.estimate_text(text)
        # 30 chars / 4 = ~7.5, 应该在 5-15 范围
        self.assertGreater(tokens, 3)
        self.assertLess(tokens, 20)

    def test_heuristic_empty_text(self):
        """启发式处理空文本"""
        est = TokenEstimator()
        est._tiktoken_available = False
        est._encoder_loaded = True
        est._encoder = None

        self.assertEqual(est.estimate_text(""), 0)
        self.assertEqual(est.estimate_text(None), 0)

    @patch("core.context_engine.token_estimator.TokenEstimator._get_encoder")
    def test_fallback_when_encoder_fails(self, mock_get_encoder):
        """encoder 失败时降级到启发式"""
        mock_get_encoder.return_value = None
        est = TokenEstimator()
        tokens = est.estimate_text("hello world")
        self.assertGreater(tokens, 0)


class TestTokenEstimatorEncodingResolution(unittest.TestCase):
    """Encoding 解析测试"""

    def test_resolve_by_model_prefix(self):
        """通过模型前缀解析"""
        est = TokenEstimator(model="gpt-4o-2024-05-13")
        name = est._resolve_encoding_name()
        self.assertEqual(name, "o200k_base")

    def test_resolve_by_provider(self):
        """通过供应商解析"""
        est = TokenEstimator(provider="deepseek")
        name = est._resolve_encoding_name()
        self.assertEqual(name, "cl100k_base")

    def test_resolve_override(self):
        """强制指定 encoding"""
        est = TokenEstimator(encoding_override="p50k_base")
        name = est._resolve_encoding_name()
        self.assertEqual(name, "p50k_base")

    def test_resolve_default(self):
        """默认使用 cl100k_base"""
        est = TokenEstimator()
        name = est._resolve_encoding_name()
        self.assertEqual(name, "cl100k_base")


class TestTokenEstimatorAccuracy(unittest.TestCase):
    """准确性测试（与 tiktoken 精确值对比）"""

    def test_tiktoken_available(self):
        """检测 tiktoken 是否可用"""
        try:
            import tiktoken

            return True
        except ImportError:
            self.skipTest("tiktoken not installed")

    def test_english_accuracy(self):
        """英文文本准确性（如果有 tiktoken）"""
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")

        est = TokenEstimator(model="gpt-4o")
        text = "Hello, how are you doing today? This is a test message."
        estimated = est.estimate_text(text)

        # 使用 tiktoken 直接计算精确值
        encoder = tiktoken.get_encoding("o200k_base")
        exact = len(encoder.encode(text))

        # 误差应在 10% 以内
        self.assertLess(abs(estimated - exact) / exact, 0.1)

    def test_chinese_accuracy(self):
        """中文文本准确性（如果有 tiktoken）"""
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")

        est = TokenEstimator(model="gpt-4o")
        text = "你好，这是一段中文测试文本，用于验证 token 估算的准确性。"
        estimated = est.estimate_text(text)

        encoder = tiktoken.get_encoding("o200k_base")
        exact = len(encoder.encode(text))

        # 误差应在 15% 以内
        self.assertLess(abs(estimated - exact) / exact, 0.15)


if __name__ == "__main__":
    unittest.main()
