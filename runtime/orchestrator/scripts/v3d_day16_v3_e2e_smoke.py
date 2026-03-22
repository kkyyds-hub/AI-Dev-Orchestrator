"""V3-D Day16 smoke checks for end-to-end acceptance and documentation closure."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import UUID


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v3-day16-v3-e2e-smoke"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _prepare_env() -> None:
    if SMOKE_RUNTIME_DATA_DIR.exists():
        shutil.rmtree(SMOKE_RUNTIME_DATA_DIR)
    SMOKE_RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["DAILY_BUDGET_USD"] = "0.50"
    os.environ["SESSION_BUDGET_USD"] = "1.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _set_tasks_completed(*, task_ids: list[str]) -> None:
    from app.core.db import SessionLocal
    from app.domain.task import TaskStatus
    from app.repositories.task_repository import TaskRepository

    with SessionLocal() as session:
        task_repository = TaskRepository(session)
        for task_id in task_ids:
            task_repository.set_status(UUID(task_id), TaskStatus.COMPLETED)
        session.commit()


def _create_failed_run_review(*, task_id: str):
    from app.core.db import SessionLocal
    from app.domain.project_role import ProjectRoleCode
    from app.domain.run import RunFailureCategory, RunStatus
    from app.domain.task import TaskStatus
    from app.repositories.failure_review_repository import FailureReviewRepository
    from app.repositories.run_repository import RunRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.failure_review_service import FailureReviewService
    from app.services.run_logging_service import RunLoggingService

    with SessionLocal() as session:
        task_repository = TaskRepository(session)
        run_repository = RunRepository(session)
        run_logging_service = RunLoggingService()
        failure_review_service = FailureReviewService(
            failure_review_repository=FailureReviewRepository(),
            run_logging_service=run_logging_service,
        )

        task_repository.set_status(UUID(task_id), TaskStatus.FAILED)
        run = run_repository.create_running_run(
            task_id=UUID(task_id),
            route_reason="Execution-side gap remained after the project entered execution.",
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            downstream_role_code=ProjectRoleCode.ENGINEER,
            handoff_reason="Architecture follow-up still missed one integration constraint.",
            dispatch_status="handoff_pending",
        )
        log_path = run_logging_service.initialize_run_log(
            task_id=UUID(task_id),
            run_id=run.id,
        )
        run_repository.set_log_path(run.id, log_path)
        run_logging_service.append_event(
            log_path=log_path,
            event="task_routed",
            message="Task was routed for one more execution attempt during Day16 acceptance.",
            data={"reason": "execution_gap"},
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="execution_finished",
            level="error",
            message="Execution failed while closing the remaining integration gap.",
            data={"exit_code": 1},
        )
        run_logging_service.append_event(
            log_path=log_path,
            event="run_finalized",
            level="error",
            message="Run finalized as failed and was sent into retrospective clustering.",
            data={"status": "failed"},
        )
        failed_run = run_repository.finish_run(
            run.id,
            status=RunStatus.FAILED,
            result_summary="Execution failed on the final integration follow-up task.",
            failure_category=RunFailureCategory.EXECUTION_FAILED,
            quality_gate_passed=False,
        )
        task = task_repository.get_by_id(UUID(task_id))
        _assert(task is not None, "task should exist when creating a Day16 failure review")
        review = failure_review_service.ensure_review(task=task, run=failed_run)
        session.commit()

    _assert(review is not None, "failure review should be created for the failed run")
    return failed_run, review


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.core.db import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        draft_response = client.post(
            "/planning/drafts",
            json={
                "brief": "\n".join(
                    [
                        "为老板视角整理一个 V3 端到端验收项目。",
                        "1. 先生成项目与任务草案。",
                        "2. 需要串起角色协作、策略路由、交付件、审批和复盘。",
                        "3. 最终要能在项目总览里展示时间线、项目记忆和审批闭环。",
                    ]
                ),
                "max_tasks": 4,
            },
        )
        _assert(
            draft_response.status_code == 200,
            f"planning draft failed: {draft_response.status_code}",
        )
        draft_payload = draft_response.json()
        _assert(draft_payload["project"] is not None, "draft response should include a project")
        _assert(len(draft_payload["tasks"]) >= 3, "draft should include at least 3 tasks")

        reviewed_project = {
            **draft_payload["project"],
            "name": "V3 Day16 端到端验收项目",
            "summary": (
                "串起项目规划、策略路由、角色接力、交付件审批、项目时间线和复盘收口，"
                "用于验证 V3 Day01-Day15 的最小闭环。"
            ),
        }
        apply_response = client.post(
            "/planning/apply",
            json={
                "project_summary": reviewed_project["summary"],
                "project": reviewed_project,
                "tasks": draft_payload["tasks"],
            },
        )
        _assert(
            apply_response.status_code == 201,
            f"planning apply failed: {apply_response.status_code}",
        )
        apply_payload = apply_response.json()
        project = apply_payload["project"]
        project_id = project["id"]
        planning_tasks = apply_payload["tasks"]

        _assert(project_id, "planning apply should return a project id")
        _assert(
            all(task["project_id"] == project_id for task in planning_tasks),
            "all applied tasks should be attached to the new project",
        )

        _set_tasks_completed(task_ids=[task["id"] for task in planning_tasks])

        project_detail_response = client.get(f"/projects/{project_id}")
        _assert(
            project_detail_response.status_code == 200,
            f"project detail failed: {project_detail_response.status_code}",
        )
        project_detail = project_detail_response.json()
        _assert(
            len(project_detail["tasks"]) >= len(planning_tasks),
            "project detail should expose the imported planning task tree",
        )

        role_catalog_response = client.get(f"/roles/projects/{project_id}")
        _assert(
            role_catalog_response.status_code == 200,
            f"role catalog failed: {role_catalog_response.status_code}",
        )
        role_catalog = role_catalog_response.json()
        _assert(role_catalog["enabled_role_count"] >= 4, "project should expose the full role catalog")

        success_task_response = client.post(
            "/tasks",
            json={
                "project_id": project_id,
                "title": "补齐 PRD 审批版并触发老板验收",
                "input_summary": (
                    "simulate: 输出一版可提交审批的 PRD 摘要，覆盖目标、范围、风险、"
                    "验收标准与下一阶段建议。"
                ),
                "priority": "urgent",
                "risk_level": "normal",
                "acceptance_criteria": [
                    "给出老板可直接阅读的 PRD 摘要",
                    "明确范围边界与关键风险",
                    "说明进入执行阶段的前置条件",
                ],
                "owner_role_code": "product_manager",
                "downstream_role_code": "architect",
            },
        )
        _assert(
            success_task_response.status_code == 201,
            f"explicit Day16 task create failed: {success_task_response.status_code}",
        )
        success_task = success_task_response.json()

        strategy_preview_response = client.get(f"/strategy/projects/{project_id}/preview")
        _assert(
            strategy_preview_response.status_code == 200,
            f"strategy preview failed: {strategy_preview_response.status_code}",
        )
        strategy_preview = strategy_preview_response.json()
        _assert(
            strategy_preview["selected_task_id"] == success_task["id"],
            "strategy preview should prioritize the Day16 urgent task",
        )
        _assert(strategy_preview["owner_role_code"] == "product_manager", "preview should keep the PM owner role")
        _assert(strategy_preview["model_name"], "preview should expose the routed model")
        _assert(
            strategy_preview["selected_skill_names"],
            "preview should expose bound skills for the routed task",
        )

        worker_response = client.post("/workers/run-once")
        _assert(worker_response.status_code == 200, f"worker run failed: {worker_response.status_code}")
        worker_payload = worker_response.json()
        _assert(worker_payload["claimed"], "worker should claim one task")
        _assert(worker_payload["task_id"] == success_task["id"], "worker should execute the Day16 urgent task")
        _assert(worker_payload["run_id"], "worker should return a run id")
        _assert(worker_payload["strategy_code"], "worker should expose a strategy code")
        _assert(worker_payload["selected_skill_names"], "worker should expose selected skills")

        run_logs_response = client.get(f"/runs/{worker_payload['run_id']}/logs")
        _assert(
            run_logs_response.status_code == 200,
            f"run logs failed: {run_logs_response.status_code}",
        )
        run_logs_payload = run_logs_response.json()
        _assert(
            any(event["event"] == "role_handoff" for event in run_logs_payload["events"]),
            "run logs should include the role handoff event",
        )

        decision_trace_response = client.get(f"/runs/{worker_payload['run_id']}/decision-trace")
        _assert(
            decision_trace_response.status_code == 200,
            f"decision trace failed: {decision_trace_response.status_code}",
        )
        decision_trace = decision_trace_response.json()
        trace_stages = {item["stage"] for item in decision_trace["trace_items"]}
        _assert("routing" in trace_stages, "decision trace should include routing")
        _assert("handoff" in trace_stages, "decision trace should include handoff")
        _assert("execution" in trace_stages, "decision trace should include execution")
        _assert("finalize" in trace_stages, "decision trace should include finalization")

        workbench_response = client.get(
            "/console/role-workbench",
            params={"project_id": project_id},
        )
        _assert(
            workbench_response.status_code == 200,
            f"role workbench failed: {workbench_response.status_code}",
        )
        workbench_payload = workbench_response.json()
        _assert(workbench_payload["recent_handoff_count"] >= 1, "workbench should surface recent handoffs")

        deliverable_response = client.post(
            "/deliverables",
            json={
                "project_id": project_id,
                "type": "prd",
                "title": "老板审批版 PRD",
                "stage": "planning",
                "created_by_role_code": "product_manager",
                "summary": "提交 PRD v1，供老板做 Day16 端到端验收。",
                "content": "# 目标\n- 完成 V3 最小闭环验收。\n\n# 范围\n- 规划\n- 路由\n- 审批\n- 复盘",
                "content_format": "markdown",
                "source_task_id": success_task["id"],
                "source_run_id": worker_payload["run_id"],
            },
        )
        _assert(
            deliverable_response.status_code == 201,
            f"deliverable create failed: {deliverable_response.status_code}",
        )
        deliverable = deliverable_response.json()

        deliverable_snapshot_response = client.get(f"/deliverables/projects/{project_id}")
        _assert(
            deliverable_snapshot_response.status_code == 200,
            f"deliverable snapshot failed: {deliverable_snapshot_response.status_code}",
        )
        deliverable_snapshot = deliverable_snapshot_response.json()
        _assert(deliverable_snapshot["total_deliverables"] >= 1, "project should have at least one deliverable")

        approval_v1_response = client.post(
            "/approvals",
            json={
                "deliverable_id": deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "请审阅 PRD v1，确认是否可以推进执行阶段。",
                "due_in_hours": 24,
            },
        )
        _assert(
            approval_v1_response.status_code == 201,
            f"approval v1 create failed: {approval_v1_response.status_code}",
        )
        approval_v1 = approval_v1_response.json()

        inbox_pending_response = client.get(f"/approvals/projects/{project_id}")
        _assert(
            inbox_pending_response.status_code == 200,
            f"approval inbox failed: {inbox_pending_response.status_code}",
        )
        inbox_pending = inbox_pending_response.json()
        _assert(inbox_pending["pending_requests"] >= 1, "approval inbox should show a pending request")

        reject_response = client.post(
            f"/approvals/{approval_v1['id']}/actions",
            json={
                "action": "reject",
                "actor_name": "老板",
                "summary": "PRD v1 还缺少验收边界与执行前提，暂不通过。",
                "comment": "请补充可量化验收标准，并明确进入执行阶段的前提清单。",
                "requested_changes": [
                    "补充验收边界",
                    "增加执行前提清单",
                ],
            },
        )
        _assert(
            reject_response.status_code == 200,
            f"approval rejection failed: {reject_response.status_code}",
        )

        history_after_reject_response = client.get(f"/approvals/{approval_v1['id']}/history")
        _assert(
            history_after_reject_response.status_code == 200,
            f"approval history after reject failed: {history_after_reject_response.status_code}",
        )
        history_after_reject = history_after_reject_response.json()
        _assert(
            history_after_reject["rework_status"] == "rework_required",
            "approval history should require rework after the rejection",
        )

        deliverable_v2_response = client.post(
            f"/deliverables/{deliverable['id']}/versions",
            json={
                "author_role_code": "product_manager",
                "summary": "提交 PRD v2，补齐验收边界、执行前提与关键风险。",
                "content": (
                    "# 验收边界\n- 老板可直接确认范围与风险。\n\n"
                    "# 执行前提\n- 角色分工明确\n- 关键接口边界清晰"
                ),
                "content_format": "markdown",
                "source_task_id": success_task["id"],
                "source_run_id": worker_payload["run_id"],
            },
        )
        _assert(
            deliverable_v2_response.status_code == 200,
            f"deliverable v2 failed: {deliverable_v2_response.status_code}",
        )

        history_after_rework_response = client.get(f"/approvals/{approval_v1['id']}/history")
        _assert(
            history_after_rework_response.status_code == 200,
            f"approval history after rework failed: {history_after_rework_response.status_code}",
        )
        history_after_rework = history_after_rework_response.json()
        _assert(
            history_after_rework["rework_status"] == "reworking",
            "approval history should mark the deliverable as reworking after v2 is submitted",
        )

        approval_v2_response = client.post(
            "/approvals",
            json={
                "deliverable_id": deliverable["id"],
                "requester_role_code": "product_manager",
                "request_note": "PRD v2 已补充老板意见，请重新审批。",
                "due_in_hours": 24,
            },
        )
        _assert(
            approval_v2_response.status_code == 201,
            f"approval v2 create failed: {approval_v2_response.status_code}",
        )
        approval_v2 = approval_v2_response.json()

        history_after_resubmission_response = client.get(f"/approvals/{approval_v2['id']}/history")
        _assert(
            history_after_resubmission_response.status_code == 200,
            f"approval history after resubmission failed: {history_after_resubmission_response.status_code}",
        )
        history_after_resubmission = history_after_resubmission_response.json()
        _assert(
            history_after_resubmission["rework_status"] == "resubmitted",
            "approval history should mark the cycle as resubmitted while approval v2 is pending",
        )

        approve_response = client.post(
            f"/approvals/{approval_v2['id']}/actions",
            json={
                "action": "approve",
                "actor_name": "老板",
                "summary": "PRD v2 已满足验收要求，可以进入执行阶段。",
                "comment": "同意进入执行，并保留本次驳回重做链路作为项目经验。",
            },
        )
        _assert(
            approve_response.status_code == 200,
            f"approval v2 approve failed: {approve_response.status_code}",
        )

        final_history_response = client.get(f"/approvals/{approval_v2['id']}/history")
        _assert(
            final_history_response.status_code == 200,
            f"final approval history failed: {final_history_response.status_code}",
        )
        final_history = final_history_response.json()
        _assert(
            final_history["rework_status"] == "approved_after_rework",
            "approval history should close as approved after rework",
        )
        _assert(
            final_history["negative_decision_count"] == 1,
            "approval history should preserve one negative decision",
        )

        stage_advance_response = client.post(
            f"/projects/{project_id}/advance-stage",
            json={"note": "老板审批通过后，推进项目进入执行阶段。"},
        )
        _assert(
            stage_advance_response.status_code == 200,
            f"stage advance failed: {stage_advance_response.status_code}",
        )
        stage_advance = stage_advance_response.json()
        _assert(stage_advance["advanced"] is True, "project should advance into execution")
        _assert(stage_advance["current_stage"] == "execution", "project should now be in execution stage")

        failed_task_response = client.post(
            "/tasks",
            json={
                "project_id": project_id,
                "title": "补齐执行阶段的集成约束",
                "input_summary": "执行阶段补齐集成约束，并沉淀失败复盘。",
                "priority": "high",
                "risk_level": "high",
                "owner_role_code": "architect",
                "upstream_role_code": "product_manager",
                "downstream_role_code": "engineer",
            },
        )
        _assert(
            failed_task_response.status_code == 201,
            f"failed follow-up task create failed: {failed_task_response.status_code}",
        )
        failed_task = failed_task_response.json()

    failed_run, review = _create_failed_run_review(task_id=failed_task["id"])

    with TestClient(app) as client:
        failure_review_response = client.get(f"/runs/{failed_run.id}/failure-review")
        _assert(
            failure_review_response.status_code == 200,
            f"failure review fetch failed: {failure_review_response.status_code}",
        )
        failure_review_payload = failure_review_response.json()
        _assert(failure_review_payload is not None, "failure review endpoint should return the stored review")

        memory_snapshot_response = client.get(f"/projects/{project_id}/memory")
        memory_search_response = client.get(
            f"/projects/{project_id}/memory/search",
            params={"q": "审批 证据", "limit": 6},
        )
        memory_context_response = client.get(
            f"/projects/{project_id}/memory/context",
            params={"task_id": success_task["id"], "limit": 3},
        )
        _assert(memory_snapshot_response.status_code == 200, "memory snapshot should succeed")
        _assert(memory_search_response.status_code == 200, "memory search should succeed")
        _assert(memory_context_response.status_code == 200, "memory context should succeed")
        memory_snapshot = memory_snapshot_response.json()
        memory_search = memory_search_response.json()
        memory_context = memory_context_response.json()
        _assert(memory_snapshot["total_memories"] >= 4, "project memory should aggregate run, approval and failure items")
        _assert(memory_search["total_matches"] >= 1, "memory search should find approval-related evidence")
        _assert(memory_context["items"], "task memory context should recall related project memories")

        timeline_response = client.get(f"/projects/{project_id}/timeline")
        _assert(
            timeline_response.status_code == 200,
            f"project timeline failed: {timeline_response.status_code}",
        )
        timeline_payload = timeline_response.json()
        timeline_event_types = {item["event_type"] for item in timeline_payload["events"]}
        _assert("stage" in timeline_event_types, "timeline should include stage events")
        _assert("deliverable" in timeline_event_types, "timeline should include deliverable events")
        _assert("approval" in timeline_event_types, "timeline should include approval events")
        _assert(
            {"role_handoff", "decision"} & timeline_event_types,
            "timeline should include role handoff or decision replay events",
        )

        retrospective_response = client.get(f"/approvals/projects/{project_id}/retrospective")
        _assert(
            retrospective_response.status_code == 200,
            f"project retrospective failed: {retrospective_response.status_code}",
        )
        retrospective_payload = retrospective_response.json()
        _assert(
            retrospective_payload["summary"]["negative_approval_cycles"] >= 1,
            "retrospective should include the approval rework cycle",
        )
        _assert(
            retrospective_payload["summary"]["total_failure_reviews"] >= 1,
            "retrospective should include the failed execution review",
        )

        boss_overview_response = client.get("/console/project-overview")
        _assert(
            boss_overview_response.status_code == 200,
            f"boss overview failed: {boss_overview_response.status_code}",
        )
        boss_overview = boss_overview_response.json()
        _assert(
            any(item["id"] == project_id for item in boss_overview["projects"]),
            "boss overview should list the Day16 acceptance project",
        )

    report = {
        "project": {
            "id": project_id,
            "name": project["name"],
            "stage_after_acceptance": stage_advance["current_stage"],
            "planning_task_count": len(planning_tasks),
        },
        "roles": {
            "enabled_role_count": role_catalog["enabled_role_count"],
            "recent_handoff_count": workbench_payload["recent_handoff_count"],
        },
        "strategy": {
            "selected_task_id": strategy_preview["selected_task_id"],
            "model_name": strategy_preview["model_name"],
            "strategy_code": strategy_preview["strategy_code"],
            "selected_skill_names": strategy_preview["selected_skill_names"],
        },
        "worker": {
            "task_id": worker_payload["task_id"],
            "run_id": worker_payload["run_id"],
            "model_name": worker_payload["model_name"],
            "model_tier": worker_payload["model_tier"],
            "trace_stages": sorted(trace_stages),
        },
        "deliverable": {
            "deliverable_id": deliverable["id"],
            "current_version_number": 2,
            "total_deliverables": deliverable_snapshot["total_deliverables"],
        },
        "approval": {
            "history_status": final_history["rework_status"],
            "negative_decision_count": final_history["negative_decision_count"],
            "step_kinds": [step["event_kind"] for step in final_history["steps"]],
        },
        "memory": {
            "total_memories": memory_snapshot["total_memories"],
            "search_total_matches": memory_search["total_matches"],
            "context_item_count": len(memory_context["items"]),
        },
        "timeline": {
            "total_events": timeline_payload["total_events"],
            "event_types": sorted(timeline_event_types),
        },
        "retrospective": {
            "summary": retrospective_payload["summary"],
            "failure_cluster_keys": [
                item["cluster_key"] for item in retrospective_payload["failure_clusters"]
            ],
        },
        "failure_review": {
            "run_id": str(failed_run.id),
            "review_id": review.review_id,
            "conclusion": review.conclusion,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
