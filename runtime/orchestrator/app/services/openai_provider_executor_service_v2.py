"""OpenAI Provider Executor V2：基于官方 SDK 的同步适配器。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from openai import APIConnectionError
from openai import APIError
from openai import APIStatusError
from openai import AuthenticationError
from openai import BadRequestError
from openai import OpenAI
from openai import RateLimitError

from app.domain.model_policy import ExecutorModelRoutingContract
from app.domain.prompt_contract import (
    BuiltPromptEnvelope,
    ProviderReceiptSource,
    ProviderUsageReceipt,
)
from app.domain.task import Task


_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_OPENAI_RESPONSES_PRICING_SOURCE = "openai.responses.usage"
_OPENAI_CHAT_COMPLETIONS_PRICING_SOURCE = "openai.chat_completions.usage"
_OUTPUT_SNIPPET_MAX_LENGTH = 500
_ERROR_DETAIL_MAX_LENGTH = 400
_OFFICIAL_OPENAI_HOST_MARKER = "api.openai.com"
_SUPPORTED_PROVIDER_KEYS = frozenset({"openai", "deepseek", "openai_compatible"})
_RESPONSES_API_FAMILY = "responses"
_CHAT_COMPLETIONS_API_FAMILY = "chat_completions"

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class OpenAIProviderExecutionResponse:
    """一次标准化的 OpenAI 提供者执行响应。"""

    success: bool
    mode: str
    summary: str
    prompt_key: str | None = None
    prompt_char_count: int = 0
    provider_usage_receipt: ProviderUsageReceipt | None = None
    output_text: str | None = None


class OpenAIProviderExecutionError(RuntimeError):
    """结构化提供者错误，用于上层服务做 fallback 和错误分类。"""

    def __init__(
        self,
        *,
        category: str,
        message: str,
        status_code: int | None = None,
        api_family: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code
        self.api_family = api_family
        self.endpoint = endpoint


@dataclass(slots=True, frozen=True)
class _OpenAIRequestAttempt:
    """一次 SDK 请求尝试：固定一个 base_url 和一个 API family。"""

    api_family: str
    api_base_url: str
    endpoint_label: str


class OpenAIProviderExecutorService:
    """通过 OpenAI 官方 Python SDK 执行 OpenAI / 兼容网关调用。"""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key.strip() if api_key is not None else None
        self.base_url = (base_url or _DEFAULT_BASE_URL).strip().rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def is_enabled(self) -> bool:
        """当前进程是否具备真实 Provider 调用条件。"""

        return bool(self.api_key)

    def test_connectivity(
        self,
        *,
        model_name: str = "gpt-4.1-mini",
    ) -> dict[str, object]:
        """运行一次最小连通性检查并返回 V1 兼容结构化结果。"""

        import time

        result: dict[str, object] = {
            "provider_key": "openai",
            "configured": bool(self.api_key),
            "base_url": self.base_url,
            "auth_valid": False,
            "endpoint_reachable": False,
            "api_family": "unknown",
            "model_name": model_name,
            "model_usable": False,
            "latency_ms": 0,
            "status": "failed",
            "error_category": None,
            "error_summary": None,
            "tested_at": None,
            "provider_receipt_id": None,
        }

        if not self.api_key:
            result["error_category"] = "not_configured"
            result["error_summary"] = "Provider API key 未配置，未发起连通性请求。"
            return result

        started_at = time.perf_counter()
        try:
            response_payload, api_family, endpoint = self._execute_compat_request(
                request_id="connectivity-check",
                model_name=model_name,
                prompt_text='Say "ok".',
                prompt_key="provider_connectivity_check",
                preferred_api_family=None,
                tools=None,
            )
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            self._extract_output_text(response_payload, api_family=api_family)
            result.update(
                {
                    "auth_valid": True,
                    "endpoint_reachable": True,
                    "api_family": api_family,
                    "model_usable": True,
                    "latency_ms": latency_ms,
                    "status": "passed",
                    "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "provider_receipt_id": self._read_text(response_payload, "id"),
                }
            )
            logger.info(
                "OpenAI Provider V2 连通性检查通过：模型=%s，API family=%s，端点=%s，延迟=%sms。",
                model_name,
                api_family,
                endpoint,
                latency_ms,
            )
            return result
        except OpenAIProviderExecutionError as exc:
            result.update(
                {
                    "error_category": exc.category,
                    "error_summary": exc.message,
                    "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
            if exc.category == "network_error":
                result["endpoint_reachable"] = False
            elif exc.category in {"auth_error", "bad_request", "rate_limited"}:
                result["endpoint_reachable"] = True
            logger.warning(
                "OpenAI Provider V2 连通性检查失败：模型=%s，错误分类=%s，摘要=%s。",
                model_name,
                exc.category,
                exc.message,
            )
            return result

    def generate_text(
        self,
        *,
        model_name: str,
        prompt_text: str,
        request_id: str,
        prompt_key: str = "run_ai_summary",
        provider_key: str = "openai",
    ) -> OpenAIProviderExecutionResponse:
        """按 V1 兼容签名生成纯文本结果。"""

        normalized_provider_key = self._normalize_provider_key(provider_key)
        response_payload, api_family, endpoint = self._execute_compat_request(
            request_id=request_id,
            model_name=model_name,
            prompt_text=prompt_text,
            prompt_key=prompt_key,
            preferred_api_family=None,
            tools=None,
        )
        return self._build_execution_response(
            response_payload=response_payload,
            api_family=api_family,
            endpoint=endpoint,
            provider_key=normalized_provider_key,
            model_name=model_name,
            request_id=request_id,
            prompt_key=prompt_key,
            prompt_text=prompt_text,
            prompt_char_count=len(prompt_text.encode("utf-8")),
        )

    def execute(
        self,
        *,
        task: Task,
        payload: str,
        routing_contract: ExecutorModelRoutingContract,
        prompt_envelope: BuiltPromptEnvelope,
    ) -> OpenAIProviderExecutionResponse:
        """执行一次 Provider 路由任务，继续消费内部 BuiltPromptEnvelope 契约。"""

        target = routing_contract.primary_target
        if target is None:
            raise OpenAIProviderExecutionError(
                category="invalid_routing_contract",
                message="Provider 路由合同缺少 primary_target，无法执行真实 Provider 调用。",
            )

        provider_key = self._normalize_provider_key(target.provider_key)
        if provider_key not in _SUPPORTED_PROVIDER_KEYS:
            raise OpenAIProviderExecutionError(
                category="provider_not_supported",
                message=f"Provider '{target.provider_key}' 暂不支持；当前仅支持 openai/deepseek/openai_compatible。",
            )

        logger.info(
            "OpenAI Provider V2 开始执行任务：task_id=%s，provider=%s，model=%s，首选 API family=%s，prompt_key=%s。",
            task.id,
            provider_key,
            target.model_name,
            target.api_family,
            prompt_envelope.template_ref.prompt_key,
        )
        response_payload, api_family, endpoint = self._execute_compat_request(
            request_id=str(task.id),
            model_name=target.model_name,
            prompt_text=prompt_envelope.prompt_text,
            prompt_key=prompt_envelope.template_ref.prompt_key,
            preferred_api_family=target.api_family,
            tools=None,
        )
        return self._build_execution_response(
            response_payload=response_payload,
            api_family=api_family,
            endpoint=endpoint,
            provider_key=provider_key,
            model_name=target.model_name,
            request_id=str(task.id),
            prompt_key=prompt_envelope.template_ref.prompt_key,
            prompt_text=prompt_envelope.prompt_text,
            prompt_char_count=prompt_envelope.prompt_char_count,
        )

    def _execute_compat_request(
        self,
        *,
        request_id: str,
        model_name: str,
        prompt_text: str,
        prompt_key: str,
        preferred_api_family: str | None,
        tools: list[dict[str, Any]] | None,
    ) -> tuple[object, str, str]:
        """按 API family 顺序尝试 SDK 调用，并保留 compatible gateway fallback。"""

        if not self.api_key:
            raise OpenAIProviderExecutionError(
                category="missing_api_key",
                message="Provider API key 未配置，无法发起 OpenAI SDK 请求。",
            )

        attempts = self._build_request_attempts(preferred_api_family=preferred_api_family)
        last_retriable_error: OpenAIProviderExecutionError | None = None
        for attempt in attempts:
            try:
                logger.info(
                    "OpenAI Provider V2 发起 SDK 请求：request_id=%s，prompt_key=%s，model=%s，API family=%s，base_url=%s。",
                    request_id,
                    prompt_key,
                    model_name,
                    attempt.api_family,
                    attempt.api_base_url,
                )
                response_payload = self._send_sdk_request(
                    attempt=attempt,
                    model_name=model_name,
                    prompt_text=prompt_text,
                    request_id=request_id,
                    prompt_key=prompt_key,
                    tools=tools,
                )
                self._extract_output_text(response_payload, api_family=attempt.api_family)
                logger.info(
                    "OpenAI Provider V2 SDK 请求成功：request_id=%s，API family=%s，端点=%s。",
                    request_id,
                    attempt.api_family,
                    attempt.endpoint_label,
                )
                return response_payload, attempt.api_family, attempt.endpoint_label
            except OpenAIProviderExecutionError as exc:
                logger.warning(
                    "OpenAI Provider V2 SDK 请求失败：request_id=%s，API family=%s，错误分类=%s，摘要=%s。",
                    request_id,
                    attempt.api_family,
                    exc.category,
                    exc.message,
                )
                if self._is_retriable_compat_error(exc):
                    last_retriable_error = exc
                    continue
                raise

        if last_retriable_error is not None:
            raise last_retriable_error

        raise OpenAIProviderExecutionError(
            category="request_error",
            message="OpenAI Provider V2 已尝试所有 SDK 请求路径，但没有得到可用响应。",
        )

    def _send_sdk_request(
        self,
        *,
        attempt: _OpenAIRequestAttempt,
        model_name: str,
        prompt_text: str,
        request_id: str,
        prompt_key: str,
        tools: list[dict[str, Any]] | None,
    ) -> object:
        """执行一次官方 SDK 调用；网络细节交给 SDK 处理。"""

        client = OpenAI(
            api_key=self.api_key,
            base_url=attempt.api_base_url,
            timeout=self.timeout_seconds,
        )
        try:
            if attempt.api_family == _CHAT_COMPLETIONS_API_FAMILY:
                kwargs = self._build_chat_completions_kwargs(
                    model_name=model_name,
                    prompt_text=prompt_text,
                    request_id=request_id,
                    prompt_key=prompt_key,
                    tools=tools,
                )
                return client.chat.completions.create(**kwargs)

            kwargs = self._build_responses_kwargs(
                model_name=model_name,
                prompt_text=prompt_text,
                request_id=request_id,
                prompt_key=prompt_key,
                tools=tools,
            )
            return client.responses.create(**kwargs)
        except OpenAIProviderExecutionError:
            raise
        except (
            AuthenticationError,
            RateLimitError,
            BadRequestError,
            APIConnectionError,
            APIStatusError,
            APIError,
        ) as exc:
            raise self._map_openai_error(
                exc,
                api_family=attempt.api_family,
                endpoint=attempt.endpoint_label,
            ) from exc
        except Exception as exc:
            detail = self._truncate(f"{type(exc).__name__}: {exc}", _ERROR_DETAIL_MAX_LENGTH)
            raise OpenAIProviderExecutionError(
                category="request_error",
                message=f"OpenAI Provider V2 SDK 请求出现未分类异常：{detail}",
                api_family=attempt.api_family,
                endpoint=attempt.endpoint_label,
            ) from exc

    def _build_execution_response(
        self,
        *,
        response_payload: object,
        api_family: str,
        endpoint: str,
        provider_key: str,
        model_name: str,
        request_id: str,
        prompt_key: str,
        prompt_text: str,
        prompt_char_count: int,
    ) -> OpenAIProviderExecutionResponse:
        """把 SDK 响应标准化为 V1 兼容的执行响应。"""

        output_text = self._extract_output_text(response_payload, api_family=api_family)
        output_snippet = self._truncate(output_text, _OUTPUT_SNIPPET_MAX_LENGTH)
        usage = self._extract_usage(response_payload, api_family=api_family)
        receipt_id = self._read_text(response_payload, "id") or f"openai-{api_family}-{request_id[:12]}"
        pricing_source = (
            _OPENAI_RESPONSES_PRICING_SOURCE
            if api_family == _RESPONSES_API_FAMILY
            else _OPENAI_CHAT_COMPLETIONS_PRICING_SOURCE
        )
        provider_usage_receipt = ProviderUsageReceipt(
            provider_key=provider_key,
            model_name=model_name,
            receipt_id=receipt_id,
            receipt_source=ProviderReceiptSource.REAL_PROVIDER,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            estimated_cost_usd=0.0,
            pricing_source=pricing_source,
            cache_read_tokens=usage["cache_read_tokens"],
            cache_write_tokens=usage["cache_write_tokens"],
            cache_hit=bool(usage["cache_hit"]),
            cache_source=(
                "provider_reported"
                if bool(usage["cache_provider_reported"])
                else "not_reported"
            ),
        )
        logger.info(
            "OpenAI Provider V2 响应已标准化：provider=%s，model=%s，API family=%s，receipt_id=%s，prompt_tokens=%s，completion_tokens=%s。",
            provider_key,
            model_name,
            api_family,
            receipt_id,
            provider_usage_receipt.prompt_tokens,
            provider_usage_receipt.completion_tokens,
        )
        summary = (
            "OpenAI Provider V2 调用成功。"
            f"provider={provider_key}，model={model_name}，API family={api_family}，端点={endpoint}，"
            f"receipt_id={receipt_id}，prompt_key={prompt_key}，"
            f"prompt_chars={len(prompt_text)}，输出摘要={output_snippet}"
        )
        return OpenAIProviderExecutionResponse(
            success=True,
            mode="provider_openai",
            summary=summary,
            prompt_key=prompt_key,
            prompt_char_count=prompt_char_count,
            provider_usage_receipt=provider_usage_receipt,
            output_text=output_text,
        )

    def _build_request_attempts(
        self,
        *,
        preferred_api_family: str | None,
    ) -> list[_OpenAIRequestAttempt]:
        """构建有限、有序的 API family/base_url 尝试列表。"""

        api_families = self._api_family_order(preferred_api_family)
        api_bases = self._build_api_base_candidates()
        attempts: list[_OpenAIRequestAttempt] = []
        seen: set[tuple[str, str]] = set()
        for api_family in api_families:
            path = "chat/completions" if api_family == _CHAT_COMPLETIONS_API_FAMILY else "responses"
            for api_base in api_bases:
                marker = (api_family, api_base)
                if marker in seen:
                    continue
                seen.add(marker)
                attempts.append(
                    _OpenAIRequestAttempt(
                        api_family=api_family,
                        api_base_url=api_base,
                        endpoint_label=f"{api_base.rstrip('/')}/{path}",
                    )
                )
        return attempts

    def _api_family_order(self, preferred_api_family: str | None) -> tuple[str, ...]:
        normalized = self._normalize_api_family(preferred_api_family)
        if normalized == _RESPONSES_API_FAMILY:
            return (_RESPONSES_API_FAMILY, _CHAT_COMPLETIONS_API_FAMILY)
        if normalized == _CHAT_COMPLETIONS_API_FAMILY:
            return (_CHAT_COMPLETIONS_API_FAMILY, _RESPONSES_API_FAMILY)
        if self._is_official_openai_host():
            return (_RESPONSES_API_FAMILY, _CHAT_COMPLETIONS_API_FAMILY)
        return (_CHAT_COMPLETIONS_API_FAMILY, _RESPONSES_API_FAMILY)

    @staticmethod
    def _normalize_api_family(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(".", "_").replace("-", "_")
        if normalized in {"chat_completions", "chat_completions_api"}:
            return _CHAT_COMPLETIONS_API_FAMILY
        if normalized in {"responses", "responses_api"}:
            return _RESPONSES_API_FAMILY
        return None

    def _build_api_base_candidates(self) -> list[str]:
        """构造 SDK base_url 候选，兼容带 /v1 和不带 /v1 的配置。"""

        normalized = (self.base_url or _DEFAULT_BASE_URL).strip().rstrip("/")
        if not normalized:
            normalized = _DEFAULT_BASE_URL
        candidates: list[str] = []

        def add(candidate: str) -> None:
            clean_candidate = candidate.strip().rstrip("/")
            if clean_candidate and clean_candidate not in candidates:
                candidates.append(clean_candidate)

        if normalized.lower().endswith("/v1"):
            add(normalized)
            return candidates

        add(f"{normalized}/v1")
        add(normalized)
        return candidates

    def _is_official_openai_host(self) -> bool:
        normalized = self.base_url.strip().lower()
        return _OFFICIAL_OPENAI_HOST_MARKER in normalized

    @staticmethod
    def _build_responses_kwargs(
        *,
        model_name: str,
        prompt_text: str,
        request_id: str,
        prompt_key: str,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """把内部 prompt 文本适配成 Responses API 输入。"""

        kwargs: dict[str, Any] = {
            "model": model_name,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt_text}],
                }
            ],
            "metadata": {
                "request_id": request_id,
                "prompt_key": prompt_key,
            },
        }
        if tools:
            kwargs["tools"] = tools
        return kwargs

    @staticmethod
    def _build_chat_completions_kwargs(
        *,
        model_name: str,
        prompt_text: str,
        request_id: str,
        prompt_key: str,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """把内部 prompt 文本适配成 Chat Completions messages。"""

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt_text}],
            "metadata": {
                "request_id": request_id,
                "prompt_key": prompt_key,
            },
        }
        if tools:
            kwargs["tools"] = tools
        return kwargs

    def _extract_output_text(self, payload: object, *, api_family: str) -> str:
        """从 Responses 或 Chat Completions SDK 对象中提取输出文本。"""

        if api_family == _CHAT_COMPLETIONS_API_FAMILY:
            return self._extract_chat_completions_output_text(payload)

        output_text = self._read_text(payload, "output_text")
        if output_text:
            return output_text

        collected_parts: list[str] = []
        output_items = self._read_value(payload, "output")
        if isinstance(output_items, list):
            for output_item in output_items:
                content_items = self._read_value(output_item, "content")
                if not isinstance(content_items, list):
                    continue
                for content_item in content_items:
                    text_value = self._read_text(content_item, "text")
                    if text_value:
                        collected_parts.append(text_value)

        if collected_parts:
            return "\n".join(collected_parts)

        tool_call_summary = self._extract_tool_call_summary(payload, api_family=api_family)
        if tool_call_summary:
            return tool_call_summary

        raise OpenAIProviderExecutionError(
            category="invalid_response",
            message="OpenAI Provider V2 响应中没有可用输出文本。",
            api_family=api_family,
        )

    def _extract_chat_completions_output_text(self, payload: object) -> str:
        choices = self._read_value(payload, "choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAIProviderExecutionError(
                category="invalid_response",
                message="Chat Completions 响应中没有 choices。",
                api_family=_CHAT_COMPLETIONS_API_FAMILY,
            )

        first_choice = choices[0]
        message_payload = self._read_value(first_choice, "message")
        content_value = self._read_value(message_payload, "content")
        if isinstance(content_value, str) and content_value.strip():
            return content_value.strip()

        if isinstance(content_value, list):
            collected: list[str] = []
            for content_item in content_value:
                text_value = self._read_text(content_item, "text")
                if text_value:
                    collected.append(text_value)
            if collected:
                return "\n".join(collected)

        tool_call_summary = self._extract_tool_call_summary(
            message_payload,
            api_family=_CHAT_COMPLETIONS_API_FAMILY,
        )
        if tool_call_summary:
            return tool_call_summary

        raise OpenAIProviderExecutionError(
            category="invalid_response",
            message="Chat Completions 响应中没有可用 content 文本。",
            api_family=_CHAT_COMPLETIONS_API_FAMILY,
        )

    def _extract_tool_call_summary(self, payload: object, *, api_family: str) -> str | None:
        """仅识别 tool calls，不执行工具闭环。"""

        if api_family == _CHAT_COMPLETIONS_API_FAMILY:
            tool_calls = self._read_value(payload, "tool_calls")
        else:
            output_items = self._read_value(payload, "output")
            tool_calls = []
            if isinstance(output_items, list):
                for output_item in output_items:
                    item_type = self._read_text(output_item, "type")
                    if item_type and "function" in item_type:
                        tool_calls.append(output_item)

        if isinstance(tool_calls, list) and tool_calls:
            return (
                "模型请求调用工具，但 P21-B1 阶段未启用 tool execution loop；"
                f"已识别 tool_call_count={len(tool_calls)}，本轮只记录意图不执行。"
            )
        return None

    def _extract_usage(self, payload: object, *, api_family: str) -> dict[str, int | bool]:
        """从 SDK usage 对象中提取 token 和缓存信息，字段缺失时降级为 0。"""

        usage_payload = self._read_value(payload, "usage")
        if usage_payload is None:
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "cache_hit": 0,
                "cache_provider_reported": False,
            }

        if api_family == _CHAT_COMPLETIONS_API_FAMILY:
            prompt_tokens = self._read_int(usage_payload, "prompt_tokens", "input_tokens")
            completion_tokens = self._read_int(usage_payload, "completion_tokens", "output_tokens")
        else:
            prompt_tokens = self._read_int(usage_payload, "input_tokens", "prompt_tokens")
            completion_tokens = self._read_int(usage_payload, "output_tokens", "completion_tokens")
        total_tokens = self._read_int(usage_payload, "total_tokens")
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens

        cache_read_tokens = 0
        cache_write_tokens = 0
        cache_provider_reported = False
        for detail_key in ("prompt_tokens_details", "input_tokens_details"):
            details = self._read_value(usage_payload, detail_key)
            if details is None:
                continue
            detail_read = self._read_int(
                details,
                "cached_tokens",
                "cache_read_input_tokens",
                "cache_read_tokens",
            )
            detail_write = self._read_int(
                details,
                "cache_write_input_tokens",
                "cache_write_tokens",
            )
            if detail_read or detail_write:
                cache_provider_reported = True
                cache_read_tokens = max(cache_read_tokens, detail_read)
                cache_write_tokens = max(cache_write_tokens, detail_write)

        top_level_read = self._read_int(
            usage_payload,
            "cached_tokens",
            "cache_read_input_tokens",
            "cache_read_tokens",
        )
        top_level_write = self._read_int(
            usage_payload,
            "cache_write_input_tokens",
            "cache_write_tokens",
        )
        if top_level_read or top_level_write:
            cache_provider_reported = True
            cache_read_tokens = max(cache_read_tokens, top_level_read)
            cache_write_tokens = max(cache_write_tokens, top_level_write)

        return {
            "prompt_tokens": max(0, prompt_tokens),
            "completion_tokens": max(0, completion_tokens),
            "total_tokens": max(0, total_tokens),
            "cache_read_tokens": max(0, cache_read_tokens),
            "cache_write_tokens": max(0, cache_write_tokens),
            "cache_hit": 1 if cache_read_tokens > 0 else 0,
            "cache_provider_reported": cache_provider_reported,
        }

    def _map_openai_error(
        self,
        exc: Exception,
        *,
        api_family: str,
        endpoint: str,
    ) -> OpenAIProviderExecutionError:
        """把官方 SDK 异常映射成项目内部稳定错误分类。"""

        status_code = self._read_status_code(exc)
        if isinstance(exc, AuthenticationError):
            category = "auth_error"
        elif isinstance(exc, RateLimitError):
            category = "rate_limited"
        elif isinstance(exc, BadRequestError):
            category = "bad_request"
        elif isinstance(exc, APIConnectionError):
            category = "network_error"
        elif isinstance(exc, APIStatusError):
            if status_code in (401, 403):
                category = "auth_error"
            elif status_code == 404:
                category = "endpoint_not_found"
            elif status_code in (408, 409, 429) or (status_code is not None and status_code >= 500):
                category = "upstream_retryable"
            else:
                category = "api_status_error"
        elif isinstance(exc, APIError):
            category = "api_error"
        else:
            category = "request_error"

        detail = self._truncate(f"{type(exc).__name__}: {exc}", _ERROR_DETAIL_MAX_LENGTH)
        return OpenAIProviderExecutionError(
            category=category,
            message=f"OpenAI Provider V2 SDK 请求失败：{detail}",
            status_code=status_code,
            api_family=api_family,
            endpoint=endpoint,
        )

    @staticmethod
    def _is_retriable_compat_error(exc: OpenAIProviderExecutionError) -> bool:
        if exc.status_code in (400, 404, 405, 408, 409, 415, 422, 429):
            return True
        if exc.status_code is not None and exc.status_code >= 500:
            return True
        return exc.category in {
            "bad_request",
            "endpoint_not_found",
            "endpoint_not_supported",
            "request_schema_error",
            "api_status_error",
            "upstream_retryable",
        }

    @staticmethod
    def _normalize_provider_key(provider_key: str) -> str:
        return provider_key.strip().lower()

    @staticmethod
    def _read_status_code(exc: object) -> int | None:
        value = getattr(exc, "status_code", None)
        if isinstance(value, int):
            return value
        return None

    @classmethod
    def _read_text(cls, payload: object, key: str) -> str | None:
        value = cls._read_value(payload, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def _read_int(cls, payload: object, *keys: str) -> int:
        for key in keys:
            value = cls._read_value(payload, key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return 0

    @staticmethod
    def _read_value(payload: object, key: str) -> object:
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload.get(key)
        value = getattr(payload, key, None)
        if value is not None:
            return value
        model_dump = getattr(payload, "model_dump", None)
        if callable(model_dump):
            try:
                dumped = model_dump()
            except Exception:
                return None
            if isinstance(dumped, dict):
                return dumped.get(key)
        return None

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."
