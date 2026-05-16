"""Live Provider connectivity smoke -- verifies REAL provider connectivity.

This smoke does NOT use mock provider.  It requires a real, configured
OpenAI / compatible Provider API key and makes a minimal live request.

On success it persists evidence to:
  <runtime_data_dir>/provider-settings/live-connectivity-test-result.json

The diagnostics service reads this file so that the closure rollup
no longer flags ``provider_not_tested``.

Requirements:
  - OPENAI_API_KEY (or saved provider config with api_key)
  - A reachable provider endpoint
  - Valid auth and non-exhausted quota
  - Provider must respond with a valid OpenAI-shaped payload

On ANY failure (missing key, auth error, network unreachable, timeout,
rate-limited, etc.) the smoke MUST fail directly -- no mock fallback.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Allow importing the app package from the orchestrator root
RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


# -- Helpers -----------------------------------------------------------------

def _resolve_runtime_data_dir() -> Path:
    from app.core.config import settings
    return settings.runtime_data_dir


def _resolve_evidence_path() -> Path:
    return _resolve_runtime_data_dir() / "provider-settings" / "live-connectivity-test-result.json"


def _pick_test_model(base_url: str) -> str:
    """Pick a sensible test model for the configured provider gateway."""
    env_model = os.environ.get("OPENAI_TEST_MODEL_NAME", "").strip()
    if env_model:
        return env_model
    base_lower = base_url.lower()
    if "deepseek" in base_lower:
        return "deepseek-v4-pro"
    if "openai" in base_lower:
        return "gpt-4.1-mini"
    if "anthropic" in base_lower:
        return "claude-sonnet-4-6"
    return "gpt-4.1-mini"


def _write_evidence(evidence: dict) -> None:
    evidence_path = _resolve_evidence_path()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  Evidence written to: {evidence_path}")


# -- Main smoke --------------------------------------------------------------

def main() -> int:
    print("=" * 64)
    print("Live Provider Connectivity Smoke")
    print("=" * 64)

    # 1. Resolve runtime provider config ------------------------------------
    print("\n[1/5] Resolving provider config ...")
    from app.services.provider_config_service import ProviderConfigService

    provider_config_service = ProviderConfigService()
    runtime_config = provider_config_service.resolve_openai_runtime_config()

    api_key = runtime_config.api_key
    base_url = runtime_config.base_url
    timeout_seconds = runtime_config.timeout_seconds

    if not api_key:
        print("\nFAIL: Provider not configured.")
        print("  Reason: No API key found (checked saved config + OPENAI_API_KEY env).")
        print("  Action: Set OPENAI_API_KEY environment variable or configure via")
        print("          PUT /provider-settings/openai")
        _write_evidence({
            "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "failed",
            "provider_configured": False,
            "error_category": "not_configured",
            "error_summary": "No API key found in saved config or OPENAI_API_KEY env.",
        })
        return 1

    summary = provider_config_service.get_openai_summary()
    print(f"  provider_key : {summary.provider_key}")
    print(f"  configured   : {summary.configured}")
    print(f"  masked_key   : {summary.masked_api_key}")
    print(f"  base_url     : {summary.base_url}")
    print(f"  timeout      : {summary.timeout_seconds}s")
    print(f"  source       : {summary.source}")

    # 2. Build executor -----------------------------------------------------
    print("\n[2/5] Creating OpenAIProviderExecutorService ...")
    from app.services.openai_provider_executor_service import (
        OpenAIProviderExecutionError,
        OpenAIProviderExecutorService,
    )

    executor = OpenAIProviderExecutorService(
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    print(f"  executor.is_enabled = {executor.is_enabled}")

    # 3. Run live connectivity test -----------------------------------------
    print("\n[3/5] Running live connectivity test (real HTTP request) ...")
    test_model = _pick_test_model(base_url)
    print(f"  test_model  : {test_model}")
    t0 = time.perf_counter()
    try:
        result = executor.test_connectivity(model_name=test_model)
    except OpenAIProviderExecutionError as exc:
        elapsed = time.perf_counter() - t0
        print(f"\nFAIL: Provider execution error after {elapsed:.1f}s")
        print(f"  category    : {exc.category}")
        print(f"  message     : {exc.message}")
        print(f"  status_code : {exc.status_code}")
        _write_evidence({
            "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "failed",
            "provider_configured": True,
            "base_url": base_url,
            "error_category": exc.category,
            "error_summary": exc.message,
            "status_code": exc.status_code,
            "latency_ms": int(elapsed * 1000),
        })
        return 1
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"\nFAIL: Unexpected error after {elapsed:.1f}s")
        print(f"  type : {type(exc).__name__}")
        print(f"  args : {exc}")
        _write_evidence({
            "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "failed",
            "provider_configured": True,
            "base_url": base_url,
            "error_category": "unexpected_error",
            "error_summary": f"{type(exc).__name__}: {exc}",
            "latency_ms": int(elapsed * 1000),
        })
        return 1

    elapsed_s = time.perf_counter() - t0

    # 4. Validate result ----------------------------------------------------
    print("\n[4/5] Validating connectivity result ...")

    configured = bool(result.get("configured"))
    status = result.get("status")
    auth_valid = bool(result.get("auth_valid"))
    endpoint_reachable = bool(result.get("endpoint_reachable"))
    model_usable = bool(result.get("model_usable"))
    api_family = result.get("api_family", "unknown")
    model_name = result.get("model_name", "unknown")
    latency_ms = result.get("latency_ms", 0)
    tested_at = result.get("tested_at")
    provider_receipt_id = result.get("provider_receipt_id")
    error_category = result.get("error_category")
    error_summary = result.get("error_summary")

    print(f"  configured         = {configured}")
    print(f"  status             = {status}")
    print(f"  auth_valid         = {auth_valid}")
    print(f"  endpoint_reachable = {endpoint_reachable}")
    print(f"  model_usable       = {model_usable}")
    print(f"  api_family         = {api_family}")
    print(f"  model_name         = {model_name}")
    print(f"  latency_ms         = {latency_ms}")
    print(f"  tested_at          = {tested_at}")
    print(f"  provider_receipt_id= {provider_receipt_id}")
    if error_category:
        print(f"  error_category     = {error_category}")
    if error_summary:
        print(f"  error_summary      = {error_summary}")

    # Check each condition and fail on first violation
    checks: list[tuple[bool, str]] = [
        (configured, "provider_configured must be True"),
        (status == "passed", f"status must be 'passed', got '{status}'"),
        (auth_valid, "auth_valid must be True"),
        (endpoint_reachable, "endpoint_reachable must be True"),
        (model_usable, "model_usable must be True"),
        (
            isinstance(provider_receipt_id, str) and bool(provider_receipt_id.strip()),
            "provider_receipt_id must be a non-empty string",
        ),
        (tested_at is not None, "tested_at must be set"),
        (
            isinstance(provider_receipt_id, str)
            and not provider_receipt_id.startswith("mock-"),
            f"provider_receipt_id must NOT start with 'mock-' (got: {provider_receipt_id})",
        ),
    ]

    all_passed = True
    for condition, message in checks:
        if not condition:
            print(f"  FAIL: {message}")
            all_passed = False

    if not all_passed:
        print(f"\nFAIL: Connectivity checks failed (wall time {elapsed_s:.1f}s).")
        _write_evidence({
            "tested_at": tested_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "failed",
            "provider_configured": configured,
            "base_url": base_url,
            "auth_valid": auth_valid,
            "endpoint_reachable": endpoint_reachable,
            "model_usable": model_usable,
            "error_category": error_category or "validation_failed",
            "error_summary": error_summary or "One or more connectivity checks failed.",
            "provider_receipt_id": provider_receipt_id,
            "api_family": api_family,
            "model_name": model_name,
            "latency_ms": latency_ms,
            "token_accounting_mode": None,
        })
        return 1

    # 5. Write success evidence ---------------------------------------------
    print("\n[5/5] Writing success evidence ...")
    evidence = {
        "tested_at": tested_at,
        "status": "passed",
        "provider_configured": True,
        "base_url": base_url,
        "auth_valid": auth_valid,
        "endpoint_reachable": endpoint_reachable,
        "model_usable": model_usable,
        "provider_receipt_id": provider_receipt_id,
        "api_family": api_family,
        "model_name": model_name,
        "latency_ms": latency_ms,
        "token_accounting_mode": "provider_reported",
    }
    _write_evidence(evidence)

    print()
    print("=" * 64)
    print("Live Provider Connectivity Smoke: PASSED")
    print(f"  api_family  : {api_family}")
    print(f"  model       : {model_name}")
    print(f"  receipt_id  : {provider_receipt_id}")
    print(f"  latency_ms  : {latency_ms}")
    print(f"  wall_time   : {elapsed_s:.1f}s")
    print(f"  endpoint    : {base_url}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
