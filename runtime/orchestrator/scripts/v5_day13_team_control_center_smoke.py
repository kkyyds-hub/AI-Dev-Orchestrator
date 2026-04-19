"""Day13 smoke for team assembly and team control center cross-layer contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-day13-team-control-center-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _request_json(
    client: TestClient,
    method: str,
    path: str,
    expected_status: int,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.request(method, path, json=payload)
    if response.status_code != expected_status:
        raise SystemExit(
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )
    return response.json()


def _prepare_env() -> Path:
    runtime_data_dir = prepare_runtime_data_dir(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "20.00"
    os.environ["SESSION_BUDGET_USD"] = "10.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    return runtime_data_dir


def main() -> None:
    runtime_data_dir = _prepare_env()

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            201,
            {
                "name": "Day13 Team Control Smoke",
                "summary": "Validate team assembly / team policy / budget policy Day13 contracts.",
                "stage": "execution",
            },
        )
        project_id = project["id"]

        initial_snapshot = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/team-control-center",
            200,
        )
        _assert(
            "day14_prerequisites" in initial_snapshot,
            "initial team control snapshot should include day14_prerequisites",
        )

        payload = {
            "team_name": initial_snapshot["team_name"],
            "team_mission": initial_snapshot["team_mission"],
            "assembly": [
                {
                    "role_code": "product_manager",
                    "enabled": True,
                    "display_name": "Product Manager",
                    "allocation_percent": 45,
                    "notes": "Lead requirements and boss sync.",
                },
                {
                    "role_code": "engineer",
                    "enabled": True,
                    "display_name": "Engineer",
                    "allocation_percent": 55,
                    "notes": "Primary execution owner.",
                },
            ],
            "team_policy": {
                "collaboration_mode": "pair-routing",
                "intervention_mode": "boss-review",
                "escalation_enabled": True,
                "handoff_required": True,
                "review_gate": "required",
            },
            "budget_policy": {
                "daily_budget_usd": 88.0,
                "per_run_budget_usd": 12.0,
                "hard_stop_enabled": False,
                "pressure_mode": "balanced",
            },
            "role_model_policy": {
                "role_preferences": [
                    {"role_code": "product_manager", "model_tier": "balanced"},
                    {"role_code": "engineer", "model_tier": "premium"},
                ],
                "stage_overrides": [
                    {
                        "stage": "execution",
                        "role_code": "engineer",
                        "model_tier": "premium",
                    }
                ],
            },
        }
        save_snapshot = _request_json(
            client,
            "PUT",
            f"/projects/{project_id}/team-control-center",
            200,
            payload,
        )
        replay_snapshot = _request_json(
            client,
            "GET",
            f"/projects/{project_id}/team-control-center",
            200,
        )
        _assert(
            replay_snapshot["team_policy"]["collaboration_mode"] == "pair-routing",
            "team policy should be persisted and replayed via Day13 endpoint",
        )
        _assert(
            replay_snapshot["budget_policy"]["daily_budget_usd"] == 88.0,
            "budget policy should be persisted and replayed via Day13 endpoint",
        )
        _assert(
            replay_snapshot["day14_prerequisites"]["team_size"] == 2,
            "day14_prerequisites.team_size should reflect Day13 assembly",
        )
        _assert(
            replay_snapshot["day14_prerequisites"]["enabled_role_codes"]
            == ["product_manager", "engineer"],
            "day14_prerequisites.enabled_role_codes should reflect enabled assembly roles",
        )
        _assert(
            replay_snapshot["day14_prerequisites"]["role_preference_count"] == 2,
            "day14_prerequisites.role_preference_count should match role preferences",
        )
        _assert(
            replay_snapshot["day14_prerequisites"]["stage_override_count"] == 1,
            "day14_prerequisites.stage_override_count should match stage overrides",
        )
        _assert(
            "GET /strategy/projects/{project_id}/preview"
            in replay_snapshot["runtime_consumption_boundary"]["role_model_policy_paths"],
            "runtime_consumption_boundary should expose strategy preview path",
        )
        _assert(
            "POST /workers/run-once?project_id={project_id}"
            in replay_snapshot["runtime_consumption_boundary"]["role_model_policy_paths"],
            "runtime_consumption_boundary should expose worker run-once path",
        )

        strategy_rules = _request_json(client, "GET", "/strategy/rules", 200)
        _assert(
            strategy_rules["rules"]["role_model_tier_preferences"]["engineer"] == "premium",
            "Day13 save should update strategy rules role preference",
        )
        _assert(
            strategy_rules["rules"]["stage_model_tier_overrides"]["execution"]["engineer"]
            == "premium",
            "Day13 save should update strategy rules stage override",
        )

    print(
        json.dumps(
            {
                "runtime_data_dir": str(SMOKE_RUNTIME_DATA_DIR),
                "runtime_data_dir_effective": str(runtime_data_dir),
                "project_id": project_id,
                "initial_snapshot": initial_snapshot,
                "save_snapshot": save_snapshot,
                "replay_snapshot": replay_snapshot,
                "strategy_rules": strategy_rules,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
