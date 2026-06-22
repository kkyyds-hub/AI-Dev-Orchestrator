from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = RUNTIME_ROOT / "scripts" / "p11_project_director_evidence_to_agent_api_smoke.py"


def test_p11_project_director_evidence_to_agent_api_smoke_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json"],
        cwd=RUNTIME_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)

    assert summary["smoke_status"] == "passed"
    assert summary["session_created"] is True
    assert summary["session_id"]
    assert summary["dry_run_api_ok"] is True
    assert summary["evidence_pack_created"] is True
    assert summary["evidence_pack_id"].startswith("p10-a-")
    assert summary["task_composer_consumed_evidence"] is True
    assert summary["composed_tasks_count"] > 0
    assert summary["programmer_assignment_created"] is True
    assert summary["reviewer_assignment_created"] is True
    assert summary["message_bound"] is True
    assert summary["message_readback_ok"] is True
    assert summary["isolated_runtime_data"] is True
    assert summary["runtime_data_dir"] != str((RUNTIME_ROOT / "data").resolve())
    assert summary["sqlite_db_path"].endswith("/db/orchestrator.db")
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["worker_started"] is False
    assert summary["real_task_created"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["blocked_reasons"] == []

    payload = json.dumps(summary, ensure_ascii=False).lower()
    for forbidden in (
        "api_key",
        "token",
        "secret",
        "pid",
        "raw command",
        "raw stdout",
        "raw stderr",
    ):
        assert forbidden not in payload
