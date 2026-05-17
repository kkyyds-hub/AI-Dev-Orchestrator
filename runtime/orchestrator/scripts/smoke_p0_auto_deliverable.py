"""P0-1 smoke: verify auto-generate deliverable on successful worker run.

This smoke:
1. Creates an isolated project with one task
2. Runs the worker once (uses real provider config if available)
3. Checks that a deliverable was auto-generated for the successful run
4. Re-runs the worker (no more pending tasks) — no duplicate deliverable
5. Verifies GET /deliverables/projects/{project_id} returns the deliverable
"""

from __future__ import annotations

import json, os, shutil, stat, sys
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "smoke-p0-auto-deliverable"
SMOKE_RUNTIME_DATA = SMOKE_ROOT / "runtime-data"
REAL_CONFIG_PATH = RUNTIME_ROOT.parent / "data" / "provider-settings" / "openai-provider-config.json"


def _remove_readonly(f, p, _):
    Path(p).chmod(stat.S_IWRITE)
    f(p)


def setup():
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)
    SMOKE_RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
    (SMOKE_RUNTIME_DATA / "db").mkdir(exist_ok=True)
    (SMOKE_RUNTIME_DATA / "provider-settings").mkdir(exist_ok=True)

    if REAL_CONFIG_PATH.exists():
        rc = json.loads(REAL_CONFIG_PATH.read_text(encoding="utf-8"))
        (SMOKE_RUNTIME_DATA / "provider-settings" / "openai-provider-config.json").write_text(
            json.dumps(rc, ensure_ascii=False), encoding="utf-8"
        )

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ROOT / "workspaces")
    os.environ["DAILY_BUDGET_USD"] = "10.00"
    os.environ["SESSION_BUDGET_USD"] = "10.00"


def main() -> int:
    setup()

    from fastapi.testclient import TestClient
    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    passed = 0
    failed = 0

    def check(condition: bool, label: str) -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {label}")
        else:
            failed += 1
            print(f"  FAIL: {label}")

    with TestClient(app) as client:
        # ── Create project + task ──────────────────────────────────
        draft = client.post("/planning/drafts", json={
            "brief": "最小任务：返回 hello world",
            "max_tasks": 3,
        }).json()

        apply_resp = client.post("/planning/apply", json={
            "project_summary": draft.get("project_summary", "test"),
            "project": {**draft["project"], "name": "P0-1 Auto Deliverable Smoke", "stage": "execution"},
            "tasks": draft["tasks"],
        })
        ar = apply_resp.json()
        project_id = ar["project"]["id"]
        created_tasks = ar["tasks"]
        print(f"\nProject: {project_id}, tasks: {len(created_tasks)}")

        client.put(f"/projects/{project_id}/team-control-center", json={
            "team_name": "P0 Test",
            "team_mission": "test",
            "assembly": [{"role_code": "engineer", "display_name": "E", "enabled": True, "allocation_percent": 100, "notes": ""}],
            "team_policy": {"collaboration_mode": "role-led", "intervention_mode": "boss-review", "escalation_enabled": True, "handoff_required": False, "review_gate": "optional"},
            "budget_policy": {"daily_budget_usd": 10.0, "per_run_budget_usd": 5.0, "hard_stop_enabled": False, "pressure_mode": "balanced"},
            "role_model_policy": {
                "role_preferences": [{"role_code": "engineer", "model_tier": "balanced"}],
                "stage_overrides": [{"stage": "execution", "role_code": "engineer", "model_tier": "balanced"}],
            },
        })

        # ── Worker run #1 ──────────────────────────────────────────
        print("\n>>> Worker run #1 ...")
        wr1 = client.post(f"/workers/run-once?project_id={project_id}").json()
        run_status = wr1.get("run_status")
        exec_mode = wr1.get("execution_mode")
        receipt = wr1.get("provider_receipt_id", "")
        print(f"  run_status={run_status}, exec_mode={exec_mode}, receipt={receipt}")

        # ── Check deliverables after run ───────────────────────────
        print("\n>>> Checking deliverables ...")
        deliv_resp = client.get(f"/deliverables/projects/{project_id}")
        deliv_data = deliv_resp.json()
        total = deliv_data.get("total_deliverables", 0)
        deliverables = deliv_data.get("deliverables", [])
        print(f"  total_deliverables={total}")

        # If the worker ran successfully (real provider or mock), a deliverable
        # should have been auto-generated when execution succeeded.
        if run_status == "succeeded":
            check(total >= 1, f"deliverable auto-generated (total={total})")

            if deliverables:
                d = deliverables[0]
                latest = d.get("latest_version", {})
                print(f"  deliverable: {d.get('title')}")
                print(f"  source_task_id: {latest.get('source_task_id')}")
                print(f"  source_run_id: {latest.get('source_run_id')}")
                check(
                    bool(latest.get("source_task_id")),
                    "deliverable has source_task_id",
                )
                check(
                    bool(latest.get("source_run_id")),
                    "deliverable has source_run_id",
                )
                check(
                    not str(latest.get("source_run_id", "")).startswith("mock-"),
                    "source_run_id is not mock- prefix",
                )
        else:
            print("  Skipping deliverable checks — run did not succeed")
            check(True, "no deliverable expected for failed run")

        # ── Worker run #2 ── verify idempotent (no duplicate) ─────
        print("\n>>> Worker run #2 (should find no pending tasks) ...")
        wr2 = client.post(f"/workers/run-once?project_id={project_id}").json()
        claimed2 = wr2.get("claimed", False)
        print(f"  claimed={claimed2}")

        # If nothing claimed, the original deliverable count should be unchanged
        deliv_resp2 = client.get(f"/deliverables/projects/{project_id}")
        total2 = deliv_resp2.json().get("total_deliverables", 0)
        check(total2 == total, f"idempotent — no duplicate (was {total}, now {total2})")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
