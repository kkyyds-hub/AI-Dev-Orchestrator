"""BCL-01 smoke: verify Provider Test endpoint response structure.

Covers:
- Not-configured returns configured=false, no 500.
- Auth error / network error / endpoint-not-supported via mocked exceptions.
- Successful simulated paths (responses and chat_completions) via mocked payloads.
- Invalid-JSON-but-HTTP-200 must NOT be misjudged as passed.

This smoke does NOT require a real OpenAI API key.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.openai_provider_executor_service import (
    OpenAIProviderExecutionError,
    OpenAIProviderExecutorService,
)


# -- Mock payloads -------------------------------------------------------

_RESPONSES_SUCCESS_PAYLOAD = {
    "id": "resp_test_smoke_001",
    "object": "response",
    "model": "gpt-4.1-mini",
    "output_text": "ok",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "ok"}],
        }
    ],
    "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
}

_CHAT_COMPLETIONS_SUCCESS_PAYLOAD = {
    "id": "chatcmpl_test_smoke_001",
    "object": "chat.completion",
    "model": "gpt-4.1-mini",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "ok"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
}

_INVALID_200_PAYLOAD = {
    "status": "ok",
    "data": {"message": "This is not an OpenAI Chat Completion shape."},
}


# -- Helpers -------------------------------------------------------------

def _make_executor(**kwargs: object) -> OpenAIProviderExecutorService:
    """Build an executor with safe defaults for smoke testing."""
    defaults: dict[str, object] = {
        "api_key": "sk-test-smoke-key",
        "base_url": "https://api.openai.com/v1",
        "timeout_seconds": 5,
    }
    defaults.update(kwargs)
    return OpenAIProviderExecutorService(
        api_key=str(defaults["api_key"]),
        base_url=str(defaults["base_url"]),
        timeout_seconds=int(defaults["timeout_seconds"]),
    )


def _assert_passed_shape(result: dict[str, object]) -> None:
    """Assert common fields for a passed test result."""
    assert result["status"] == "passed", f"Expected passed, got {result['status']}"
    assert result["auth_valid"] is True
    assert result["endpoint_reachable"] is True
    assert result["model_usable"] is True
    assert isinstance(result["api_family"], str) and result["api_family"] != "unknown"
    assert isinstance(result["latency_ms"], int) and result["latency_ms"] >= 0
    assert result["tested_at"] is not None


# -- Tests ---------------------------------------------------------------

def test_not_configured() -> None:
    """Without a key, test_connectivity returns configured=false gracefully."""
    executor = OpenAIProviderExecutorService(api_key=None)
    result = executor.test_connectivity()
    assert result["configured"] is False, f"Expected configured=False, got {result['configured']}"
    assert result["status"] == "failed", f"Expected status=failed, got {result['status']}"
    assert result["error_category"] == "not_configured", (
        f"Expected error_category=not_configured, got {result['error_category']}"
    )
    assert result["error_summary"] is not None
    assert "api_key" not in str(result["error_summary"]).lower() or "key" not in str(result["error_summary"]).lower(), (
        "error_summary should not leak API key semantics: " + str(result["error_summary"])
    )
    print("PASS test_not_configured")


def test_response_structure_keys() -> None:
    """Verify all required keys are present in the result dict."""
    executor = OpenAIProviderExecutorService(api_key=None)
    result = executor.test_connectivity()
    required_keys = {
        "provider_key", "configured", "base_url", "auth_valid",
        "endpoint_reachable", "api_family", "model_name", "model_usable",
        "latency_ms", "status", "error_category", "error_summary", "tested_at",
        "provider_receipt_id",
    }
    missing = required_keys - set(result.keys())
    extra = set(result.keys()) - required_keys
    assert not missing, f"Missing keys in result: {missing}"
    assert not extra, f"Unexpected keys in result: {extra}"
    print("PASS test_response_structure_keys")


def test_auth_error_via_mock() -> None:
    """Mock a 401 auth_error; result must explicitly report auth_error."""
    executor = _make_executor()
    with patch.object(
        executor,
        "_send_sdk_request",
        side_effect=OpenAIProviderExecutionError(
            category="auth_error",
            message="HTTP 401: Invalid API key",
            status_code=401,
        ),
    ):
        result = executor.test_connectivity()

    assert result["configured"] is True
    assert result["status"] == "failed"
    assert result["error_category"] == "auth_error", (
        f"Expected auth_error, got {result['error_category']}"
    )
    assert result["endpoint_reachable"] is True
    assert result["error_summary"] is not None
    assert "sk-test" not in str(result["error_summary"]).lower()
    print("PASS test_auth_error_via_mock")


def test_network_error_via_mock() -> None:
    """Mock a network_error; result must report endpoint_reachable=False."""
    executor = _make_executor()
    with patch.object(
        executor,
        "_send_sdk_request",
        side_effect=OpenAIProviderExecutionError(
            category="network_error",
            message="Network unreachable",
        ),
    ):
        result = executor.test_connectivity()

    assert result["status"] == "failed"
    assert result["error_category"] == "network_error", (
        f"Expected network_error, got {result['error_category']}"
    )
    assert result["endpoint_reachable"] is False
    print("PASS test_network_error_via_mock")


def test_endpoint_not_supported_via_mock() -> None:
    """Mock a 404 endpoint_not_supported; result must report it."""
    executor = _make_executor()
    with patch.object(
        executor,
        "_send_sdk_request",
        side_effect=OpenAIProviderExecutionError(
            category="endpoint_not_supported",
            message="HTTP 404: Not Found",
            status_code=404,
        ),
    ):
        result = executor.test_connectivity()

    assert result["status"] == "failed"
    assert result["error_category"] in ("endpoint_not_supported", "request_schema_error"), (
        f"Expected endpoint_not_supported or request_schema_error, got {result['error_category']}"
    )
    print(f"PASS test_endpoint_not_supported_via_mock (category={result['error_category']})")


def test_responses_success() -> None:
    """Mock a valid OpenAI Responses payload; must pass."""
    executor = _make_executor()
    with patch.object(
        executor,
        "_send_sdk_request",
        return_value=_RESPONSES_SUCCESS_PAYLOAD,
    ):
        result = executor.test_connectivity()

    _assert_passed_shape(result)
    assert result["api_family"] == "responses", (
        f"Expected responses, got {result['api_family']}"
    )
    print("PASS test_responses_success")


def test_chat_completions_success() -> None:
    """Mock a valid Chat Completions payload; must pass."""
    executor = _make_executor(base_url="https://api.deepseek.com/v1")
    with patch.object(
        executor,
        "_send_sdk_request",
        return_value=_CHAT_COMPLETIONS_SUCCESS_PAYLOAD,
    ):
        result = executor.test_connectivity()

    _assert_passed_shape(result)
    assert result["api_family"] == "chat_completions", (
        f"Expected chat_completions, got {result['api_family']}"
    )
    print("PASS test_chat_completions_success")


def test_invalid_response_not_passed() -> None:
    """HTTP-200 but non-OpenAI JSON MUST NOT be misjudged as passed."""
    executor = _make_executor()
    with patch.object(
        executor,
        "_send_sdk_request",
        return_value=_INVALID_200_PAYLOAD,
    ):
        result = executor.test_connectivity()

    assert result["status"] == "failed", (
        f"Expected failed for non-OpenAI JSON, got {result['status']}"
    )
    assert result["error_category"] in ("invalid_response", "request_schema_error"), (
        f"Expected invalid_response or request_schema_error, got {result['error_category']}"
    )
    print(f"PASS test_invalid_response_not_passed (category={result['error_category']})")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    all_passed = True
    for name, fn in [
        ("test_not_configured", test_not_configured),
        ("test_response_structure_keys", test_response_structure_keys),
        ("test_auth_error_via_mock", test_auth_error_via_mock),
        ("test_network_error_via_mock", test_network_error_via_mock),
        ("test_endpoint_not_supported_via_mock", test_endpoint_not_supported_via_mock),
        ("test_responses_success", test_responses_success),
        ("test_chat_completions_success", test_chat_completions_success),
        ("test_invalid_response_not_passed", test_invalid_response_not_passed),
    ]:
        try:
            fn()
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            all_passed = False

    print()
    if all_passed:
        print("BCL-01 smoke: ALL PASSED")
    else:
        print("BCL-01 smoke: SOME FAILED")
        sys.exit(1)
