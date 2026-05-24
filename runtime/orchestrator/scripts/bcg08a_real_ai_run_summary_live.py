"""BCG-08A live evidence: generate a real AI summary for a provider run.

This script uses the existing run AI summary API against the BCG-05B
provider-reported Worker run.  It intentionally calls the real provider through
the existing summary regenerate path and fails if the result falls back to the
rule engine.

It never prints or writes an API key.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from app.main import app


TASK_ID = "db204e31-f244-4f9b-a469-abcc5e0b873f"
RUN_ID = "834b38aa-3669-4121-9424-3aa4999cad2e"
EXPECTED_PROVIDER_KEY = "deepseek"
EXPECTED_MODEL_NAME = "deepseek-v4-pro"
EXPECTED_TOKEN_ACCOUNTING_MODE = "provider_reported"

REQUIRED_SUMMARY_HEADINGS = [
    "## 运行结论",
    "## 已完成内容",
    "## 风险与注意事项",
    "## 下一步建议",
    "## 技术依据",
]


def _assert(condition: bool, message: str) -> None:
    """Raise a concise assertion error for smoke-script failures."""

    if not condition:
        raise AssertionError(message)


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
) -> Any:
    """Call one API path and return JSON, failing loudly on unexpected status."""

    response = client.request(method, path)
    _assert(
        response.status_code == expected_status,
        f"{method} {path} failed: {response.status_code} {response.text[:300]}",
    )
    return response.json()


def _summarize_markdown(markdown: str) -> str:
    """Return a short one-line summary without dumping full AI content."""

    lines = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return " ".join(lines)[:500]


def main() -> None:
    """Generate and verify one source=ai run summary from the existing APIs."""

    with TestClient(app) as client:
        task_runs = _request_json(client, "GET", f"/tasks/{TASK_ID}/runs")
        matching_runs = [item for item in task_runs if item["id"] == RUN_ID]
        _assert(len(matching_runs) == 1, "Expected provider run not found under task.")
        run = matching_runs[0]

        _assert(run["provider_key"] == EXPECTED_PROVIDER_KEY, "provider_key mismatch.")
        _assert(run["model_name"] == EXPECTED_MODEL_NAME, "model_name mismatch.")
        _assert(
            run["token_accounting_mode"] == EXPECTED_TOKEN_ACCOUNTING_MODE,
            "target run is not provider_reported.",
        )
        _assert(run["provider_receipt_id"], "target run is missing provider receipt.")
        _assert(run["total_tokens"] > 0, "target run has no provider token evidence.")

        generated = _request_json(
            client,
            "POST",
            f"/runs/{RUN_ID}/ai-summary/regenerate",
            expected_status=201,
        )
        current = _request_json(client, "GET", f"/runs/{RUN_ID}/ai-summary")
        history = _request_json(client, "GET", f"/runs/{RUN_ID}/ai-summaries")

    _assert(generated["run_id"] == RUN_ID, "summary run_id mismatch.")
    _assert(generated["task_id"] == TASK_ID, "summary task_id mismatch.")
    _assert(generated["status"] == "succeeded", "summary did not succeed.")
    _assert(generated["source"] == "ai", "summary source is not ai.")
    _assert(generated["model_provider"] == EXPECTED_PROVIDER_KEY, "summary provider mismatch.")
    _assert(generated["model_name"] == EXPECTED_MODEL_NAME, "summary model mismatch.")
    _assert(generated["provider_receipt_id"], "summary provider receipt missing.")
    _assert(generated["error_summary"] is None, "summary fell back or recorded an error.")
    _assert(generated["stale"] is False, "generated summary should be active.")
    _assert(generated["source_fingerprint"], "summary source_fingerprint missing.")
    _assert(generated["source_hash"], "summary source_hash missing.")
    _assert(generated["prompt_hash"], "summary prompt_hash missing.")

    markdown = generated["summary_markdown"]
    for heading in REQUIRED_SUMMARY_HEADINGS:
        _assert(heading in markdown, f"summary missing heading: {heading}")

    active_summary = current["active_summary"]
    _assert(active_summary is not None, "current summary is missing.")
    _assert(active_summary["id"] == generated["id"], "current summary is not generated summary.")
    _assert(active_summary["source"] == "ai", "current summary source is not ai.")

    summaries = history["summaries"]
    _assert(
        any(item["id"] == generated["id"] for item in summaries),
        "generated summary is missing from history.",
    )
    _assert(
        history["active_summary"]["id"] == generated["id"],
        "history active_summary does not point at generated summary.",
    )

    report = {
        "phase": "BCG-08A Real AI Run Summary Evidence",
        "summary_api": {
            "generate": f"POST /runs/{RUN_ID}/ai-summary/regenerate",
            "read_current": f"GET /runs/{RUN_ID}/ai-summary",
            "read_history": f"GET /runs/{RUN_ID}/ai-summaries",
        },
        "real_model_called": True,
        "target_run": {
            "run_id": RUN_ID,
            "task_id": TASK_ID,
            "provider_key": run["provider_key"],
            "model_name": run["model_name"],
            "token_accounting_mode": run["token_accounting_mode"],
            "run_provider_receipt_id": run["provider_receipt_id"],
            "total_tokens": run["total_tokens"],
            "estimated_cost": run["estimated_cost"],
            "log_path": run["log_path"],
        },
        "summary": {
            "summary_id": generated["id"],
            "status": generated["status"],
            "source": generated["source"],
            "model_provider": generated["model_provider"],
            "model_name": generated["model_name"],
            "provider_receipt_id": generated["provider_receipt_id"],
            "error_summary": generated["error_summary"],
            "stale": generated["stale"],
            "source_version": generated["source_version"],
            "source_fingerprint": generated["source_fingerprint"],
            "source_hash": generated["source_hash"],
            "prompt_hash": generated["prompt_hash"],
            "markdown_length": len(markdown),
            "content_excerpt": _summarize_markdown(markdown),
        },
        "persistence": {
            "current_active_summary_id": active_summary["id"],
            "history_active_summary_id": history["active_summary_id"],
            "history_count": len(summaries),
            "generated_summary_in_history": True,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
