"""OpenAI Provider Executor 兼容入口。

P21-B1 起，项目默认通过这个历史 import 路径使用 V2 SDK adapter。
保留本文件是为了兼容既有调用：
``from app.services.openai_provider_executor_service import OpenAIProviderExecutorService``。
"""

from __future__ import annotations

from app.domain.prompt_contract import ProviderUsageReceipt
from app.services.openai_provider_executor_service_v2 import (
    OpenAIProviderExecutionError,
    OpenAIProviderExecutionResponse,
    OpenAIProviderExecutorService,
)

__all__ = [
    "OpenAIProviderExecutionError",
    "OpenAIProviderExecutionResponse",
    "OpenAIProviderExecutorService",
    "ProviderUsageReceipt",
]
