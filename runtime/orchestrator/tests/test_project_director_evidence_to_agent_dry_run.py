from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path("scripts/p10_evidence_to_agent_dry_run.py")


def _script_module():
    spec = importlib.util.spec_from_file_location(
        "p10_evidence_to_agent_dry_run",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dry_run_summary_proves_evidence_to_agent_chain() -> None:
    summary = _script_module().run_dry_run(
        repo_root=Path(__file__).resolve().parents[3],
        user_goal="P10-D prove evidence-to-agent dry-run chain",
    )

    assert summary["dry_run_status"] == "passed"
    assert summary["origin_main_commit"]
    assert summary["evidence_pack_created"] is True
    assert summary["evidence_pack_id"].startswith("p10-a-")
    assert summary["evidence_refs_count"] > 0
    assert summary["task_composer_consumed_evidence"] is True
    assert summary["composed_tasks_count"] > 0
    assert summary["every_task_has_evidence_refs"] is True
    assert summary["every_task_has_allowed_forbidden_files"] is True
    assert summary["every_task_has_targeted_tests"] is True
    assert summary["programmer_assignment_created"] is True
    assert summary["reviewer_assignment_created"] is True
    assert summary["reviewer_readonly"] is True
    assert summary["director_permanent_executor"] is False
    assert summary["native_executor_started"] is False
    assert summary["codex_started"] is False
    assert summary["claude_code_started"] is False
    assert summary["product_runtime_git_write_allowed"] is False
    assert summary["frontend_required"] is False
    assert summary["ai_project_director_total_loop"] == "Partial"
    assert summary["blocked_reasons"] == []
    assert summary["risks"]
    assert summary["unknowns"]


def test_dry_run_json_cli_outputs_safe_summary(capsys) -> None:
    exit_code = _script_module().main(["--json"])
    captured = capsys.readouterr()
    summary = json.loads(captured.out)

    assert exit_code == 0
    assert summary["dry_run_status"] == "passed"
    payload = captured.out.lower()
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
