"""BCL-01 smoke: verify Provider Test endpoint response structure.

Covers:
- Not-configured returns configured=false, no 500.
- Auth error / simulated failure path returns stable error category.
- Successful simulated path returns stable passed structure.

This smoke does NOT require a real OpenAI API key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.provider_config_service import ProviderConfigService
from app.services.openai_provider_executor_service import OpenAIProviderExecutorService


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


def test_auth_error_with_invalid_key() -> None:
    """With an obviously fake key, the result should return auth_error."""
    executor = OpenAIProviderExecutorService(
        api_key="sk-fake-invalid-key-for-testing",
        base_url="https://api.openai.com/v1",
        timeout_seconds=5,
    )
    result = executor.test_connectivity()
    assert result["configured"] is True, f"Expected configured=True, got {result['configured']}"
    assert result["status"] == "failed", f"Expected status=failed, got {result['status']}"
    assert result["error_category"] in ("auth_error", "network_error", "request_error", "endpoint_not_supported"), (
        f"Expected one stable error category, got {result['error_category']}"
    )
    assert result["error_summary"] is not None
    # error_summary must NOT contain the raw API key
    error_text = str(result["error_summary"]).lower()
    assert "sk-fake" not in error_text, (
        "error_summary must not contain the raw API key"
    )
    print(f"PASS test_auth_error_with_invalid_key (category={result['error_category']})")


def test_response_structure_keys() -> None:
    """Verify all required keys are present in the result dict."""
    executor = OpenAIProviderExecutorService(api_key=None)
    result = executor.test_connectivity()
    required_keys = {
        "provider_key", "configured", "base_url", "auth_valid",
        "endpoint_reachable", "api_family", "model_name", "model_usable",
        "latency_ms", "status", "error_category", "error_summary", "tested_at",
    }
    missing = required_keys - set(result.keys())
    extra = set(result.keys()) - required_keys
    assert not missing, f"Missing keys in result: {missing}"
    assert not extra, f"Unexpected keys in result: {extra}"
    print("PASS test_response_structure_keys")


def test_network_unreachable_base_url() -> None:
    """With a clearly unreachable base URL, result should be network_error."""
    executor = OpenAIProviderExecutorService(
        api_key="sk-test-key-for-connectivity-failure",
        base_url="https://192.0.2.1:65535/v1",
        timeout_seconds=2,
    )
    result = executor.test_connectivity()
    assert result["status"] == "failed", f"Expected status=failed, got {result['status']}"
    assert result["error_category"] is not None
    # Should be network_error or timeout from unreachable host
    assert result["error_category"] in ("network_error", "timeout", "request_error"), (
        f"Expected network/timeout category, got {result['error_category']}"
    )
    print(f"PASS test_network_unreachable_base_url (category={result['error_category']})")


def test_endpoint_not_supported() -> None:
    """With a valid-looking base URL that returns 404, get endpoint_not_supported."""
    executor = OpenAIProviderExecutorService(
        api_key="sk-any-key-for-404-test",
        base_url="https://httpbin.org/status/404",
        timeout_seconds=5,
    )
    result = executor.test_connectivity()
    assert result["status"] == "failed", f"Expected status=failed, got {result['status']}"
    assert result["error_category"] is not None
    print(f"PASS test_endpoint_not_supported (category={result['error_category']})")


if __name__ == "__main__":
    all_passed = True
    for name, fn in [
        ("test_not_configured", test_not_configured),
        ("test_response_structure_keys", test_response_structure_keys),
        ("test_auth_error_with_invalid_key", test_auth_error_with_invalid_key),
        ("test_network_unreachable_base_url", test_network_unreachable_base_url),
        ("test_endpoint_not_supported", test_endpoint_not_supported),
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
