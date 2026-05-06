"""Token 估算器

提供精确的 token 计数，支持三级降级策略：
1. tiktoken 精确计算（最优）
2. 语言感知启发式估算（次优）
3. len(text) // 3（兜底）

使用方式：
    estimator = TokenEstimator(model="gpt-4o", provider="openai")
    tokens = estimator.estimate_text("你好世界")
    tokens = estimator.estimate_messages(messages)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# 模型-Tokenizer 映射表
# =============================================================================

# tiktoken 提供的编码器
# cl100k_base: GPT-3.5-turbo, GPT-4, GPT-4-turbo
# o200k_base:  GPT-4o, GPT-4o-mini, o1, o3

ENCODING_BY_MODEL_PREFIX: Dict[str, str] = {
    # OpenAI o200k_base 系列
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "o1-": "o200k_base",
    "o1": "o200k_base",
    "o3-": "o200k_base",
    "o3": "o200k_base",
    "o4-mini": "o200k_base",
    # OpenAI cl100k_base 系列
    "gpt-4-turbo": "cl100k_base",
    "gpt-4-": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    # DeepSeek: 使用 cl100k_base 作为近似
    "deepseek": "cl100k_base",
    # Qwen: 使用 o200k_base 作为近似
    "qwen": "o200k_base",
    # Kimi (Moonshot): 使用 cl100k_base
    "kimi": "cl100k_base",
    "moonshot": "cl100k_base",
    # 智谱 GLM: 使用 cl100k_base
    "glm": "cl100k_base",
    "zhipu": "cl100k_base",
}

PROVIDER_DEFAULT_ENCODING: Dict[str, str] = {
    "openai": "cl100k_base",
    "deepseek": "cl100k_base",
    "qwen": "o200k_base",
    "kimi": "cl100k_base",
    "zhipu": "cl100k_base",
    "siliconflow": "o200k_base",
    "modelscope": "o200k_base",
}

# 每条消息的结构开销（<|start|>, role, \n, <|end|>）
MESSAGE_OVERHEAD_TOKENS = 4

# tool_calls 的固定开销
TOOL_CALLS_OVERHEAD_TOKENS = 10


# =============================================================================
# TokenEstimator 类
# =============================================================================


class TokenEstimator:
    """
    Token 估算器

    优先使用 tiktoken 精确计算，不可用时降级到启发式估算。
    线程安全（encoder 实例不可变）。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        encoding_override: Optional[str] = None,
    ):
        """
        初始化 TokenEstimator

        Args:
            model: 模型名称（如 "gpt-4o", "deepseek-chat"）
            provider: 供应商名称（如 "openai", "deepseek"）
            encoding_override: 强制指定 tiktoken encoding 名称（如 "cl100k_base"）
        """
        self._model = model
        self._provider = provider
        self._encoding_override = encoding_override
        self._encoder: Any = None  # tiktoken.Encoding or None
        self._encoder_loaded: bool = False  # 防止重复尝试加载
        self._tiktoken_available: Optional[bool] = None  # 三态：None=未检测

    # =========================================================================
    # 公开接口
    # =========================================================================

    def estimate_text(self, text: str) -> int:
        """
        估算单段文本的 token 数

        Args:
            text: 要估算的文本

        Returns:
            估算的 token 数
        """
        if not text:
            return 0

        # 短文本快速路径：直接用启发式，避免 tiktoken encode 的开销
        if len(text) < 10:
            return self._heuristic_estimate(text)

        encoder = self._get_encoder()
        if encoder is not None:
            try:
                return len(encoder.encode(text))
            except Exception as e:
                logger.debug("tiktoken encode failed, falling back to heuristic: %s", e)

        return self._heuristic_estimate(text)

    def estimate_messages(self, messages: List[Dict[str, Any]]) -> int:
        """
        估算消息列表的 token 数（含结构开销）

        OpenAI 消息格式的结构开销：
        - 每条消息：约 4 token（<|start|>, role, \\n, <|end|>）
        - assistant with tool_calls: 额外约 10 token
        - 每个 tool_call: name + arguments 的 token

        Args:
            messages: OpenAI 格式的消息列表

        Returns:
            估算的总 token 数
        """
        encoder = self._get_encoder()
        total = 0

        for msg in messages:
            # 结构开销
            total += MESSAGE_OVERHEAD_TOKENS

            # role 的 token（约 1-2 token）
            role = msg.get("role", "")
            if encoder is not None:
                try:
                    total += len(encoder.encode(role))
                except Exception:
                    total += max(1, len(role) // 4)
            else:
                total += max(1, len(role) // 4)

            # content 的 token
            content = msg.get("content") or ""
            if isinstance(content, list):
                # 多模态消息，提取文本部分
                content = " ".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and "text" in part
                )

            if encoder is not None:
                try:
                    total += len(encoder.encode(str(content)))
                except Exception:
                    total += self._heuristic_estimate(str(content))
            else:
                total += self._heuristic_estimate(str(content))

            # tool_calls 的开销
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += TOOL_CALLS_OVERHEAD_TOKENS
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    arguments = func.get("arguments", "")
                    if encoder is not None:
                        try:
                            total += len(encoder.encode(name))
                            total += len(encoder.encode(str(arguments)))
                        except Exception:
                            total += self._heuristic_estimate(name + str(arguments))
                    else:
                        total += self._heuristic_estimate(name + str(arguments))

        return total

    def set_model(self, model: str) -> None:
        """
        切换模型（清空 encoder 缓存，下次估算时重新加载）

        Args:
            model: 新的模型名称
        """
        if model != self._model:
            self._model = model
            self._encoder = None
            self._encoder_loaded = False

    def set_provider(self, provider: str) -> None:
        """
        切换供应商

        Args:
            provider: 新的供应商名称
        """
        if provider != self._provider:
            self._provider = provider
            self._encoder = None
            self._encoder_loaded = False

    def get_model(self) -> Optional[str]:
        """获取当前模型名称"""
        return self._model

    def get_provider(self) -> Optional[str]:
        """获取当前供应商名称"""
        return self._provider

    # =========================================================================
    # 内部方法
    # =========================================================================

    def _get_encoder(self) -> Any:
        """
        获取 tiktoken 编码器（带缓存和懒加载）

        Returns:
            tiktoken.Encoding 实例，或 None（tiktoken 不可用时）
        """
        if self._encoder_loaded:
            return self._encoder

        self._encoder_loaded = True

        # 检查 tiktoken 是否可用
        if self._tiktoken_available is None:
            try:
                import tiktoken  # noqa: F401

                self._tiktoken_available = True
            except ImportError:
                self._tiktoken_available = False
                self._encoder = None
                logger.debug("tiktoken not installed, using heuristic estimation")
                return None

        if not self._tiktoken_available:
            return None

        # 确定 encoding 名称
        encoding_name = self._resolve_encoding_name()
        if encoding_name is None:
            return None

        try:
            import tiktoken

            self._encoder = tiktoken.get_encoding(encoding_name)
            logger.debug("Loaded tiktoken encoding: %s", encoding_name)
        except Exception as e:
            self._encoder = None
            logger.warning("Failed to load tiktoken encoding '%s': %s", encoding_name, e)

        return self._encoder

    def _resolve_encoding_name(self) -> Optional[str]:
        """
        根据 model/provider 解析 encoding 名称

        优先级链：
        1. encoding_override（强制指定）
        2. tiktoken.model.MODEL_TO_ENCODING（精确匹配）
        3. ENCODING_BY_MODEL_PREFIX（前缀匹配）
        4. PROVIDER_DEFAULT_ENCODING（供应商兜底）
        5. cl100k_base（全局默认）

        Returns:
            encoding 名称，或 None（无法解析时）
        """
        # 1. 强制指定
        if self._encoding_override:
            return self._encoding_override

        model = (self._model or "").strip().lower()

        # 2. 精确匹配 tiktoken 内置映射
        try:
            import tiktoken.model

            if model in tiktoken.model.MODEL_TO_ENCODING:
                return tiktoken.model.MODEL_TO_ENCODING[model]
        except Exception:
            pass

        # 3. 前缀匹配
        for prefix, encoding in ENCODING_BY_MODEL_PREFIX.items():
            if model.startswith(prefix) or model.endswith(prefix):
                return encoding

        # 4. 供应商兜底
        provider = (self._provider or "").strip().lower()
        if provider in PROVIDER_DEFAULT_ENCODING:
            return PROVIDER_DEFAULT_ENCODING[provider]

        # 5. 全局默认
        return "cl100k_base"

    def _heuristic_estimate(self, text: str) -> int:
        """
        语言感知的启发式估算（不依赖 tiktoken）

        策略：
        - CJK 字符：每个约 1.5 token
        - ASCII 字符：每 4 个约 1 token
        - 其他 Unicode 字符：每 2 个约 1 token

        Args:
            text: 要估算的文本

        Returns:
            估算的 token 数
        """
        if not text:
            return 0

        cjk_count = 0
        ascii_count = 0

        for c in text:
            cp = ord(c)
            # CJK 统一汉字基本区 + 扩展区 A
            if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
                cjk_count += 1
            elif cp < 128:
                ascii_count += 1

        other_count = len(text) - cjk_count - ascii_count
        tokens = int(cjk_count * 1.5 + ascii_count / 4 + other_count / 2)

        return max(tokens, 1)
