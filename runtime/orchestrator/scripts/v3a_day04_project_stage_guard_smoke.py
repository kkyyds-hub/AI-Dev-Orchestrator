"""V3-A Day04 smoke checks for project milestones and stage guards."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import UUID


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day04-project-stage-guard-smoke"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.10"
    os.environ["SESSION_BUDGET_USD"] = "0.30"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def main() -> None:
    """Exercise the Day04 stage-guard workflow from planning to delivery."""

    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import SessionLocal, init_database
    from app.domain.task import TaskStatus
    from app.main import app
    from app.repositories.task_repository import TaskRepository

    init_database()

    with TestClient(app) as client:
        project_response = client.post(
            "/projects",
            json={
                "name": "项目阶段守卫 Day04 Smoke",
                "summary": "验证项目里程碑、阶段守卫、阻塞原因与阶段时间线。",
                "stage": "planning",
            },
        )
        _assert(
            project_response.status_code == 201,
            f"project create failed: {project_response.status_code}",
        )
        project_payload = project_response.json()
        project_id = project_payload["id"]

        initial_detail_response = client.get(f"/projects/{project_id}")
        _assert(
            initial_detail_response.status_code == 200,
            f"initial project detail failed: {initial_detail_response.status_code}",
        )
        initial_detail_payload = initial_detail_response.json()
        _assert(
            initial_detail_payload["stage_guard"]["target_stage"] == "execution",
            "planning project should target execution as its next stage",
        )
        _assert(
            initial_detail_payload["stage_guard"]["can_advance"] is False,
            "planning project without tasks must be blocked by milestones",
        )
        _assert(
            len(initial_detail_payload["stage_timeline"]) == 1,
            "new project should carry one initial stage-history entry",
        )

        blocked_without_tasks_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "第一次检查：还没有挂任务"},
        )
        _assert(
            blocked_without_tasks_response.status_code == 200,
            f"blocked advance should still return 200 payload: {blocked_without_tasks_response.status_code}",
        )
        blocked_without_tasks_payload = blocked_without_tasks_response.json()
        _assert(
            blocked_without_tasks_payload["advanced"] is False,
            "stage advance should be rejected when planning milestones are incomplete",
        )
        _assert(
            blocked_without_tasks_payload["timeline_entry"]["outcome"] == "blocked",
            "blocked stage check should be written into the timeline",
        )

        paused_task_response = client.post(
            "/tasks",
            json={
                "project_id": project_id,
                "title": "暂停中的任务",
                "input_summary": "模拟 Day04 里程碑守卫对 paused 任务的拦截。",
                "paused_reason": "等待老板补充边界条件",
            },
        )
        ready_task_response = client.post(
            "/tasks",
            json={
                "project_id": project_id,
                "title": "可立即执行的任务",
                "input_summary": "模拟 Day04 规划结束后可直接进入执行的任务。",
            },
        )
        _assert(paused_task_response.status_code == 201, "paused task create failed")
        _assert(ready_task_response.status_code == 201, "ready task create failed")
        paused_task_id = paused_task_response.json()["id"]
        ready_task_id = ready_task_response.json()["id"]

        planning_detail_response = client.get(f"/projects/{project_id}")
        planning_detail_payload = planning_detail_response.json()
        _assert(
            planning_detail_payload["stage_guard"]["can_advance"] is False,
            "planning stage should remain blocked while one task stays paused",
        )
        _assert(
            any(
                blocker["task_id"] == paused_task_id
                and any("暂停" in reason for reason in blocker["blocking_reasons"])
                for blocker in planning_detail_payload["stage_guard"]["blocking_tasks"]
            ),
            "project stage blockers should surface the paused task reason",
        )

        resume_response = client.post(f"/tasks/{paused_task_id}/resume")
        _assert(resume_response.status_code == 200, "paused task resume failed")

        ready_detail_response = client.get(f"/projects/{project_id}")
        ready_detail_payload = ready_detail_response.json()
        _assert(
            ready_detail_payload["stage_guard"]["can_advance"] is True,
            "planning stage should become advanceable once hard blockers are cleared",
        )
        _assert(
            ready_detail_payload["stage_guard"]["ready_task_count"] >= 1,
            "stage guard should report at least one ready task",
        )

        execution_transition_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "规划完成，开始执行"},
        )
        _assert(
            execution_transition_response.status_code == 200,
            "execution transition failed",
        )
        execution_transition_payload = execution_transition_response.json()
        _assert(
            execution_transition_payload["advanced"] is True,
            "project should advance into execution once milestones are satisfied",
        )
        _assert(
            execution_transition_payload["current_stage"] == "execution",
            "project should now be in execution stage",
        )

        execution_detail_response = client.get(f"/projects/{project_id}")
        execution_detail_payload = execution_detail_response.json()
        _assert(
            execution_detail_payload["stage_guard"]["target_stage"] == "verification",
            "execution project should target verification as the next stage",
        )
        _assert(
            execution_detail_payload["stage_guard"]["can_advance"] is False,
            "execution project with unfinished tasks must not enter verification",
        )

        with SessionLocal() as session:
            task_repository = TaskRepository(session)
            task_repository.set_status(UUID(paused_task_id), TaskStatus.COMPLETED)
            task_repository.set_status(UUID(ready_task_id), TaskStatus.COMPLETED)
            session.commit()

        verification_ready_response = client.get(f"/projects/{project_id}")
        verification_ready_payload = verification_ready_response.json()
        _assert(
            verification_ready_payload["stage_guard"]["can_advance"] is True,
            "execution project should become verification-ready once all tasks complete",
        )

        verification_transition_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "执行收口，进入验证"},
        )
        _assert(
            verification_transition_response.status_code == 200,
            "verification transition failed",
        )
        _assert(
            verification_transition_response.json()["current_stage"] == "verification",
            "project should now be in verification stage",
        )

        with SessionLocal() as session:
            task_repository = TaskRepository(session)
            task_repository.set_status(UUID(ready_task_id), TaskStatus.FAILED)
            session.commit()

        blocked_delivery_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "尝试直接进入交付，但保留一个 failed 任务"},
        )
        _assert(
            blocked_delivery_response.status_code == 200,
            "blocked delivery attempt should still return a structured payload",
        )
        blocked_delivery_payload = blocked_delivery_response.json()
        _assert(
            blocked_delivery_payload["advanced"] is False,
            "verification project with failed tasks must not enter delivery",
        )
        _assert(
            blocked_delivery_payload["timeline_entry"]["outcome"] == "blocked",
            "failed delivery attempt should be written into the timeline",
        )

        with SessionLocal() as session:
            task_repository = TaskRepository(session)
            task_repository.set_status(UUID(ready_task_id), TaskStatus.COMPLETED)
            session.commit()

        delivery_transition_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "验证通过，进入交付"},
        )
        _assert(
            delivery_transition_response.status_code == 200,
            "delivery transition failed",
        )
        delivery_transition_payload = delivery_transition_response.json()
        _assert(
            delivery_transition_payload["advanced"] is True,
            "verification project should enter delivery after blockers are cleared",
        )
        _assert(
            delivery_transition_payload["current_stage"] == "delivery",
            "project should now be in delivery stage",
        )

        final_detail_response = client.get(f"/projects/{project_id}")
        _assert(final_detail_response.status_code == 200, "final project detail failed")
        final_detail_payload = final_detail_response.json()
        _assert(
            final_detail_payload["stage_guard"]["target_stage"] is None,
            "delivery stage should no longer expose another target stage",
        )
        _assert(
            len(final_detail_payload["stage_timeline"]) >= 5,
            "stage timeline should preserve both blocked and applied actions",
        )
        _assert(
            any(
                entry["outcome"] == "blocked"
                for entry in final_detail_payload["stage_timeline"]
            ),
            "timeline should include at least one blocked guard attempt",
        )
        _assert(
            any(
                entry["outcome"] == "applied"
                and entry["to_stage"] == "delivery"
                for entry in final_detail_payload["stage_timeline"]
            ),
            "timeline should include the final delivery transition",
        )

    report = {
        "project_id": project_id,
        "planning_guard_before_tasks": {
            "can_advance": initial_detail_payload["stage_guard"]["can_advance"],
            "blocking_reasons": initial_detail_payload["stage_guard"]["blocking_reasons"],
        },
        "planning_guard_with_paused_task": {
            "blocking_tasks": planning_detail_payload["stage_guard"]["blocking_tasks"],
        },
        "execution_transition": execution_transition_payload,
        "blocked_delivery_transition": blocked_delivery_payload,
        "final_stage": final_detail_payload["stage"],
        "timeline_outcomes": [
            entry["outcome"] for entry in final_detail_payload["stage_timeline"]
        ],
        "timeline_length": len(final_detail_payload["stage_timeline"]),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
