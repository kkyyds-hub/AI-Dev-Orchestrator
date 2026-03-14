"""Smoke test for V2-C Day13 limited parallel execution."""

from __future__ import annotations

from pathlib import Path
import json
import os
import shutil


runtime_root = Path(__file__).resolve().parents[1] / "tmp" / "day13_smoke_runtime"
if runtime_root.exists():
    shutil.rmtree(runtime_root)

os.environ["RUNTIME_DATA_DIR"] = str(runtime_root)
os.environ["SQLITE_DB_DIR"] = str(runtime_root / "db")
os.environ["SQLITE_DB_PATH"] = str(runtime_root / "db" / "day13_smoke.db")
os.environ["MAX_CONCURRENT_WORKERS"] = "2"

from fastapi.testclient import TestClient

from app.core.db import SessionLocal, init_database
from app.domain.task import Task
from app.main import app
from app.repositories.task_repository import TaskRepository


def main() -> None:
    """Seed tasks, run the worker pool, and verify replay + slot observability."""

    init_database()
    session = SessionLocal()
    task_repository = TaskRepository(session)

    seeded_tasks = [
        task_repository.create(
            Task(
                title=f"day13 smoke task {index}",
                input_summary=f"simulate: parallel smoke payload {index}",
                acceptance_criteria=[
                    "task can be picked by worker pool",
                    "run log and replay stay readable after parallel execution",
                ],
            )
        )
        for index in range(1, 4)
    ]
    session.close()

    with TestClient(app) as client:
        pool_response = client.post("/workers/run-pool-once?requested_workers=2")
        if pool_response.status_code != 200:
            raise SystemExit(f"worker pool smoke failed: {pool_response.status_code}")

        pool_payload = pool_response.json()
        claimed_results = [item for item in pool_payload["results"] if item.get("claimed")]
        if pool_payload["launched_workers"] != 2 or len(claimed_results) != 2:
            raise SystemExit(
                "worker pool smoke expected 2 launched workers and 2 claimed runs, "
                f"got launched={pool_payload['launched_workers']} claimed={len(claimed_results)}"
            )

        slot_response = client.get("/console/worker-slots")
        if slot_response.status_code != 200:
            raise SystemExit(f"worker slot overview failed: {slot_response.status_code}")

        slot_payload = slot_response.json()
        if slot_payload["slot_snapshot"]["max_concurrent_workers"] != 2:
            raise SystemExit(
                "worker slot overview returned unexpected capacity: "
                f"{slot_payload['slot_snapshot']['max_concurrent_workers']}"
            )

        if slot_payload["pending_tasks"] != 1:
            raise SystemExit(
                f"expected 1 pending task after one pool cycle, got {slot_payload['pending_tasks']}"
            )

        pooled_run_reports: list[dict[str, object]] = []
        for result in claimed_results:
            run_id = result["run_id"]
            task_id = result["task_id"]

            logs_response = client.get(f"/runs/{run_id}/logs?limit=50")
            trace_response = client.get(f"/runs/{run_id}/decision-trace")
            history_response = client.get(f"/tasks/{task_id}/decision-history")

            if logs_response.status_code != 200:
                raise SystemExit(f"run logs failed for {run_id}: {logs_response.status_code}")
            if trace_response.status_code != 200:
                raise SystemExit(f"decision trace failed for {run_id}: {trace_response.status_code}")
            if history_response.status_code != 200:
                raise SystemExit(
                    f"decision history failed for task {task_id}: {history_response.status_code}"
                )

            log_events = [event["event"] for event in logs_response.json()["events"]]
            if "worker_slot_assigned" not in log_events or "worker_slot_released" not in log_events:
                raise SystemExit(
                    f"parallel slot events missing for run {run_id}: events={log_events}"
                )

            trace_stages = [item["stage"] for item in trace_response.json()["trace_items"]]
            if "parallel" not in trace_stages:
                raise SystemExit(
                    f"parallel stage missing in decision trace for run {run_id}: {trace_stages}"
                )

            history_items = history_response.json()
            if not history_items:
                raise SystemExit(f"decision history empty for task {task_id}")

            pooled_run_reports.append(
                {
                    "task_id": task_id,
                    "run_id": run_id,
                    "log_events": log_events,
                    "trace_stages": trace_stages,
                    "history_items": len(history_items),
                }
            )

        fallback_response = client.post("/workers/run-once")
        if fallback_response.status_code != 200:
            raise SystemExit(f"single worker fallback failed: {fallback_response.status_code}")

        fallback_payload = fallback_response.json()
        if not fallback_payload.get("claimed"):
            raise SystemExit("single worker fallback did not claim the remaining task")

        final_slot_response = client.get("/console/worker-slots")
        if final_slot_response.status_code != 200:
            raise SystemExit(f"final worker slot overview failed: {final_slot_response.status_code}")

        final_slot_payload = final_slot_response.json()
        if final_slot_payload["pending_tasks"] != 0:
            raise SystemExit(
                f"expected 0 pending tasks after fallback run, got {final_slot_payload['pending_tasks']}"
            )

        report = {
            "seeded_task_ids": [str(task.id) for task in seeded_tasks],
            "pool_cycle": {
                "requested_workers": pool_payload["requested_workers"],
                "launched_workers": pool_payload["launched_workers"],
                "claimed_runs": pool_payload["claimed_runs"],
                "idle_workers": pool_payload["idle_workers"],
            },
            "slot_overview_after_pool": {
                "pending_tasks": slot_payload["pending_tasks"],
                "running_tasks": slot_payload["running_tasks"],
                "blocked_tasks": slot_payload["blocked_tasks"],
                "idle_slots": slot_payload["slot_snapshot"]["idle_slots"],
                "running_slots": slot_payload["slot_snapshot"]["running_slots"],
            },
            "pooled_runs": pooled_run_reports,
            "single_worker_fallback": {
                "claimed": fallback_payload["claimed"],
                "task_id": fallback_payload["task_id"],
                "run_id": fallback_payload["run_id"],
                "run_status": fallback_payload["run_status"],
            },
            "slot_overview_final": {
                "pending_tasks": final_slot_payload["pending_tasks"],
                "running_tasks": final_slot_payload["running_tasks"],
                "blocked_tasks": final_slot_payload["blocked_tasks"],
                "idle_slots": final_slot_payload["slot_snapshot"]["idle_slots"],
                "running_slots": final_slot_payload["slot_snapshot"]["running_slots"],
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
