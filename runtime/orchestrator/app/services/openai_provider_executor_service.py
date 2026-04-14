"""Minimal OpenAI provider executor for the Day05 real-call bridge."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

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
_OPENAI_OFFICIAL_HOSTS = frozenset({"api.openai.com"})
_DEFAULT_COMPAT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(slots=True, frozen=True)
class OpenAIProviderExecutionResponse:
    """One normalized OpenAI provider execution response."""

    success: bool
    mode: str
    summary: str
    prompt_key: str | None = None
    prompt_char_count: int = 0
    provider_usage_receipt: ProviderUsageReceipt | None = None


class OpenAIProviderExecutionError(RuntimeError):
    """Structured provider error used for fallback classification."""

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
class OpenAIRequestAttempt:
    """One outbound request attempt against one endpoint and API family."""

    api_family: str
    endpoint: str
    payload: dict[str, Any]


class OpenAIProviderExecutorService:
    """Execute one provider-routed task against OpenAI or compatible gateways."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key.strip() if api_key is not None else None
        self.base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def is_enabled(self) -> bool:
        """Whether OpenAI real calls are available in this process."""

        return bool(self.api_key)

    def execute(
        self,
        *,
        task: Task,
        payload: str,
        routing_contract: ExecutorModelRoutingContract,
        prompt_envelope: BuiltPromptEnvelope,
    ) -> OpenAIProviderExecutionResponse:
        """Run one OpenAI Responses request and normalize the result."""

        target = routing_contract.primary_target
        if target is None:
            raise OpenAIProviderExecutionError(
                category="invalid_routing_contract",
                message="Provider routing contract has no primary target.",
            )

        provider_key = target.provider_key.strip().lower()
        if provider_key != "openai":
            raise OpenAIProviderExecutionError(
                category="provider_not_supported",
                message=f"Provider '{target.provider_key}' is not supported by OpenAI executor.",
            )

        if not self.api_key:
            raise OpenAIProviderExecutionError(
                category="missing_api_key",
                message="OPENAI_API_KEY is not configured.",
            )

        response_payload, api_family, endpoint = self._execute_compat_request(
            task=task,
            model_name=target.model_name,
            prompt_text=prompt_envelope.prompt_text,
            prompt_key=prompt_envelope.template_ref.prompt_key,
        )
        output_text = self._extract_output_text(response_payload, api_family=api_family)
        output_snippet = self._truncate(output_text, _OUTPUT_SNIPPET_MAX_LENGTH)

        usage = self._extract_usage(response_payload, api_family=api_family)
        prompt_tokens = usage["prompt_tokens"]
        completion_tokens = usage["completion_tokens"]
        total_tokens = usage["total_tokens"]

        receipt_id = str(
            response_payload.get("id") or f"openai-{api_family}-{task.id.hex[:12]}"
        )
        pricing_source = (
            _OPENAI_RESPONSES_PRICING_SOURCE
            if api_family == "responses"
            else _OPENAI_CHAT_COMPLETIONS_PRICING_SOURCE
        )
        provider_usage_receipt = ProviderUsageReceipt(
            provider_key="openai",
            model_name=target.model_name,
            receipt_id=receipt_id,
            receipt_source=ProviderReceiptSource.REAL_PROVIDER,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=0.0,
            pricing_source=pricing_source,
        )

        summary = (
            "OpenAI provider execution succeeded. "
            f"Target openai/{target.model_name} via {api_family} at {endpoint}. "
            f"Receipt {receipt_id}. Output: {output_snippet}"
        )
        return OpenAIProviderExecutionResponse(
            success=True,
            mode="provider_openai",
            summary=summary,
            prompt_key=prompt_envelope.template_ref.prompt_key,
            prompt_char_count=prompt_envelope.prompt_char_count,
            provider_usage_receipt=provider_usage_receipt,
        )

    def _execute_compat_request(
        self,
        *,
        task: Task,
        model_name: str,
        prompt_text: str,
        prompt_key: str,
    ) -> tuple[dict[str, Any], str, str]:
        """Execute one request with minimal compatibility retry for gateway variants."""

        attempts = self._build_request_attempts(
            task=task,
            model_name=model_name,
            prompt_text=prompt_text,
            prompt_key=prompt_key,
        )
        if not attempts:
            raise OpenAIProviderExecutionError(
                category="invalid_endpoint",
                message=f"No valid OpenAI endpoint could be built from base_url={self.base_url}.",
            )

        last_retriable_error: OpenAIProviderExecutionError | None = None
        for attempt in attempts:
            try:
                payload = self._post_json_request(
                    endpoint=attempt.endpoint,
                    payload=attempt.payload,
                    api_family=attempt.api_family,
                )
                return payload, attempt.api_family, attempt.endpoint
            except OpenAIProviderExecutionError as exc:
                if self._is_retriable_compat_error(exc):
                    last_retriable_error = exc
                    continue
                raise

        if last_retriable_error is not None:
            raise last_retriable_error

        raise OpenAIProviderExecutionError(
            category="request_error",
            message="OpenAI request attempts exhausted without a usable response.",
        )

    def _build_request_attempts(
        self,
        *,
        task: Task,
        model_name: str,
        prompt_text: str,
        prompt_key: str,
    ) -> list[OpenAIRequestAttempt]:
        """Build ordered request attempts for official OpenAI and compat gateways."""

        api_families: tuple[str, ...]
        if self._is_official_openai_host():
            api_families = ("responses",)
        else:
            api_families = ("chat_completions", "responses")

        api_bases = self._build_api_base_candidates()
        attempts: list[OpenAIRequestAttempt] = []
        seen_endpoints: set[str] = set()

        for api_family in api_families:
            if api_family == "responses":
                path_suffix = "responses"
                request_payload = self._build_responses_payload(
                    model_name=model_name,
                    prompt_text=prompt_text,
                    task_id=str(task.id),
                    prompt_key=prompt_key,
                )
            else:
                path_suffix = "chat/completions"
                request_payload = self._build_chat_completions_payload(
                    model_name=model_name,
                    prompt_text=prompt_text,
                    task_id=str(task.id),
                    prompt_key=prompt_key,
                )

            for api_base in api_bases:
                endpoint = f"{api_base}/{path_suffix}"
                if endpoint in seen_endpoints:
                    continue
                seen_endpoints.add(endpoint)
                attempts.append(
                    OpenAIRequestAttempt(
                        api_family=api_family,
                        endpoint=endpoint,
                        payload=request_payload,
                    )
                )

        return attempts

    def _post_json_request(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        api_family: str,
    ) -> dict[str, Any]:
        """POST one JSON request and parse one JSON object response."""

        if not self.api_key:
            raise OpenAIProviderExecutionError(
                category="missing_api_key",
                message="OPENAI_API_KEY is not configured.",
            )

        payload_bytes = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=payload_bytes,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": _DEFAULT_COMPAT_USER_AGENT,
            },
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw_payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""
            category = self._categorize_http_error(
                status_code=exc.code,
                error_body=error_body,
                api_family=api_family,
            )
            detail = self._truncate(error_body or str(exc.reason), _ERROR_DETAIL_MAX_LENGTH)
            raise OpenAIProviderExecutionError(
                category=category,
                message=f"OpenAI HTTP {exc.code} [{api_family}] at {endpoint}: {detail}",
                status_code=exc.code,
                api_family=api_family,
                endpoint=endpoint,
            ) from exc
        except error.URLError as exc:
            reason = self._truncate(str(exc.reason), _ERROR_DETAIL_MAX_LENGTH)
            raise OpenAIProviderExecutionError(
                category="network_error",
                message=f"OpenAI network error [{api_family}] at {endpoint}: {reason}",
                api_family=api_family,
                endpoint=endpoint,
            ) from exc
        except TimeoutError as exc:
            raise OpenAIProviderExecutionError(
                category="timeout",
                message=(
                    "OpenAI request timed out after "
                    f"{self.timeout_seconds} seconds [{api_family}] at {endpoint}."
                ),
                api_family=api_family,
                endpoint=endpoint,
            ) from exc
        except socket.timeout as exc:
            raise OpenAIProviderExecutionError(
                category="timeout",
                message=(
                    "OpenAI request timed out after "
                    f"{self.timeout_seconds} seconds [{api_family}] at {endpoint}."
                ),
                api_family=api_family,
                endpoint=endpoint,
            ) from exc
        except Exception as exc:
            detail = self._truncate(f"{type(exc).__name__}: {exc}", _ERROR_DETAIL_MAX_LENGTH)
            raise OpenAIProviderExecutionError(
                category="request_error",
                message=f"OpenAI request failed [{api_family}] at {endpoint}: {detail}",
                api_family=api_family,
                endpoint=endpoint,
            ) from exc

        try:
            payload_json = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise OpenAIProviderExecutionError(
                category="invalid_response",
                message="OpenAI response body is not valid JSON.",
            ) from exc

        if not isinstance(payload_json, dict):
            raise OpenAIProviderExecutionError(
                category="invalid_response",
                message="OpenAI response payload is not a JSON object.",
            )
        return payload_json

    def _extract_output_text(self, payload: dict[str, Any], *, api_family: str) -> str:
        """Extract one normalized output text from a response payload."""

        if api_family == "chat_completions":
            return self._extract_chat_completions_output_text(payload)

        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        collected_parts: list[str] = []
        output_items = payload.get("output")
        if isinstance(output_items, list):
            for output_item in output_items:
                if not isinstance(output_item, dict):
                    continue
                content_items = output_item.get("content")
                if not isinstance(content_items, list):
                    continue
                for content_item in content_items:
                    if not isinstance(content_item, dict):
                        continue
                    text_value = content_item.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        collected_parts.append(text_value.strip())

        if collected_parts:
            return "\n".join(collected_parts)

        raise OpenAIProviderExecutionError(
            category="invalid_response",
            message="OpenAI response does not contain output text.",
        )

    @staticmethod
    def _extract_chat_completions_output_text(payload: dict[str, Any]) -> str:
        """Extract one normalized output text from Chat Completions payload."""

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAIProviderExecutionError(
                category="invalid_response",
                message="Chat Completions response does not contain choices.",
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise OpenAIProviderExecutionError(
                category="invalid_response",
                message="Chat Completions first choice is not an object.",
            )

        message_payload = first_choice.get("message")
        if not isinstance(message_payload, dict):
            raise OpenAIProviderExecutionError(
                category="invalid_response",
                message="Chat Completions choice has no message object.",
            )

        content_value = message_payload.get("content")
        if isinstance(content_value, str) and content_value.strip():
            return content_value.strip()

        if isinstance(content_value, list):
            collected: list[str] = []
            for content_item in content_value:
                if not isinstance(content_item, dict):
                    continue
                text_value = content_item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    collected.append(text_value.strip())
            if collected:
                return "\n".join(collected)

        raise OpenAIProviderExecutionError(
            category="invalid_response",
            message="Chat Completions response does not contain usable content text.",
        )

    @staticmethod
    def _extract_usage(payload: dict[str, Any], *, api_family: str) -> dict[str, int]:
        """Extract usage fields while tolerating missing usage payloads."""

        usage_payload = payload.get("usage")
        if not isinstance(usage_payload, dict):
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if api_family == "chat_completions":
            prompt_tokens = OpenAIProviderExecutorService._read_int_from_usage(
                usage_payload, "prompt_tokens", "input_tokens"
            )
            completion_tokens = OpenAIProviderExecutorService._read_int_from_usage(
                usage_payload, "completion_tokens", "output_tokens"
            )
        else:
            prompt_tokens = OpenAIProviderExecutorService._read_int_from_usage(
                usage_payload, "input_tokens", "prompt_tokens"
            )
            completion_tokens = OpenAIProviderExecutorService._read_int_from_usage(
                usage_payload, "output_tokens", "completion_tokens"
            )
        total_tokens = OpenAIProviderExecutorService._read_int_from_usage(
            usage_payload, "total_tokens"
        )
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens

        return {
            "prompt_tokens": max(0, prompt_tokens),
            "completion_tokens": max(0, completion_tokens),
            "total_tokens": max(0, total_tokens),
        }

    @staticmethod
    def _read_int_from_usage(usage_payload: dict[str, Any], *keys: str) -> int:
        """Read one integer token field from usage payload."""

        for key in keys:
            value = usage_payload.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return 0

    def _build_api_base_candidates(self) -> list[str]:
        """Build ordered API base candidates while tolerating missing `/v1`."""

        normalized = self.base_url.strip().rstrip("/")
        if not normalized:
            return [_DEFAULT_BASE_URL]

        parsed = urlsplit(normalized)
        if not parsed.scheme or not parsed.netloc:
            if normalized.lower().endswith("/v1"):
                return [normalized]
            return [f"{normalized}/v1", normalized]

        path = parsed.path.rstrip("/")
        candidates: list[str] = []

        def add_candidate(path_value: str) -> None:
            candidate = urlunsplit((parsed.scheme, parsed.netloc, path_value, "", "")).rstrip("/")
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if not path:
            add_candidate("/v1")
            add_candidate("")
            return candidates

        add_candidate(path)
        if not path.endswith("/v1"):
            add_candidate(f"{path}/v1")
        return candidates

    def _is_official_openai_host(self) -> bool:
        """Whether the configured base URL points to official OpenAI host."""

        try:
            hostname = urlsplit(self.base_url).hostname
        except ValueError:
            hostname = None
        if not hostname:
            return False
        return hostname.lower() in _OPENAI_OFFICIAL_HOSTS

    @staticmethod
    def _build_responses_payload(
        *,
        model_name: str,
        prompt_text: str,
        task_id: str,
        prompt_key: str,
    ) -> dict[str, Any]:
        """Build one OpenAI Responses payload."""

        return {
            "model": model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt_text,
                        }
                    ],
                }
            ],
            "metadata": {
                "task_id": task_id,
                "prompt_key": prompt_key,
            },
        }

    @staticmethod
    def _build_chat_completions_payload(
        *,
        model_name: str,
        prompt_text: str,
        task_id: str,
        prompt_key: str,
    ) -> dict[str, Any]:
        """Build one OpenAI-compatible Chat Completions payload."""

        return {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_text,
                }
            ],
            "metadata": {
                "task_id": task_id,
                "prompt_key": prompt_key,
            },
        }

    @staticmethod
    def _categorize_http_error(
        *,
        status_code: int,
        error_body: str,
        api_family: str,
    ) -> str:
        """Map HTTP status to one stable failure category."""

        error_text = error_body.lower()
        if status_code == 401:
            return "auth_error"
        if status_code == 403:
            if "invalid_api_key" in error_text or "authentication" in error_text:
                return "auth_error"
            if api_family == "responses":
                return "endpoint_forbidden"
            return "permission_error"
        if status_code in (404, 405):
            return "endpoint_not_supported"
        if status_code in (400, 415, 422):
            return "request_schema_error"
        if status_code == 429:
            return "rate_limited"
        if status_code >= 500:
            return "upstream_error"
        return "http_error"

    @staticmethod
    def _is_retriable_compat_error(exc: OpenAIProviderExecutionError) -> bool:
        """Whether this failure should try the next compat endpoint variant."""

        if exc.status_code in (400, 403, 404, 405, 415, 422):
            return True
        return exc.category in {
            "endpoint_forbidden",
            "endpoint_not_supported",
            "request_schema_error",
            "permission_error",
            "http_error",
        }

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        """Trim one text field to a fixed length."""

        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."
