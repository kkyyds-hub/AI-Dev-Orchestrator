"""P14 Project Director controlled subprocess lifecycle smoke.

Default path delegates to the P13 dry-run chain and does not start native
executors, Codex, Claude Code, Worker subprocesses, worktree writes, or product
runtime Git writes. The controlled subprocess path is available only when every
explicit safety flag is present.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from p13_project_director_controlled_executor_lifecycle_smoke import (
    DEFAULT_RUNTIME_DATA_DIR,
    run_smoke as run_p13_smoke,
)


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    parser.add_argument(
        "--keep-temp-data",
        action="store_true",
        help="Keep the isolated runtime data directory after the smoke finishes.",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        help="Use this isolated runtime data directory instead of a temp directory.",
    )
    parser.add_argument(
        "--launch-mode",
        choices=("dry_run", "controlled_smoke"),
        default="dry_run",
    )
    parser.add_argument(
        "--executor",
        choices=("codex", "claude-code"),
        default="codex",
    )
    parser.add_argument(
        "--requested-agent-role",
        choices=("programmer", "reviewer"),
        default="programmer",
    )
    parser.add_argument("--enable-native-process", action="store_true")
    parser.add_argument("--auto-terminate", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=0.0)
    parser.add_argument("--use-supervisor", action="store_true")
    parser.add_argument("--supervisor-cleanup-after-launch", action="store_true")
    return parser.parse_args()


def _base_summary(runtime_data_dir: Path, sqlite_db_path: Path) -> dict[str, Any]:
    return {
        "smoke_status": "failed",
        "session_created": False,
        "session_id": None,
        "p11_dry_run_message_bound": False,
        "p12_safe_task_created": False,
        "p13_dispatch_message_bound": False,
        "p14_lifecycle_result_message_bound": False,
        "message_readback_ok": False,
        "launch_mode": "dry_run",
        "requested_executor": "codex",
        "requested_agent_role": "programmer",
        "controlled_executor_pilot": True,
        "executor_backed_agent": True,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "agent_session_bound": False,
        "runtime_handle_id_present": False,
        "process_handle_id_present": False,
        "supervisor_required": True,
        "supervisor_registered": False,
        "auto_terminate_required": True,
        "terminate_attempted": False,
        "cleanup_required": True,
        "supervisor_cleanup_done": False,
        "product_runtime_git_write_allowed": False,
        "worktree_write_allowed": False,
        "frontend_required": False,
        "run_created": False,
        "real_code_modified": False,
        "git_write_performed": False,
        "ai_project_director_total_loop": "Partial",
        "p9_production_safe_long_running_executor_lifecycle": "Partial",
        "runtime_data_dir": str(runtime_data_dir),
        "sqlite_db_path": str(sqlite_db_path),
        "isolated_runtime_data": False,
        "blocked_reasons": [],
        "risks": [
            "controlled subprocess smoke is not code modification completion",
            "controlled subprocess smoke is not product runtime Git write authorization",
        ],
        "unknowns": [
            "production-safe long-running executor lifecycle is still downstream work",
        ],
    }


def _configure_isolated_environment(runtime_data_dir: Path) -> Path:
    sqlite_db_path = runtime_data_dir / "db" / "orchestrator.db"
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["SQLITE_DB_PATH"] = str(sqlite_db_path)
    os.environ["WORKER_SIMULATE_EXECUTION_OVERRIDE"] = "true"
    os.environ.pop("OPENAI_API_KEY", None)
    return sqlite_db_path


def _controlled_smoke_gate(args: argparse.Namespace) -> list[str]:
    if args.launch_mode != "controlled_smoke":
        return []
    blocked_reasons: list[str] = []
    if not args.enable_native_process:
        blocked_reasons.append("enable_native_process_required")
    if not args.auto_terminate:
        blocked_reasons.append("auto_terminate_required")
    if args.timeout_seconds <= 0:
        blocked_reasons.append("positive_timeout_seconds_required")
    if not args.use_supervisor:
        blocked_reasons.append("supervisor_required")
    if not args.supervisor_cleanup_after_launch:
        blocked_reasons.append("supervisor_cleanup_after_launch_required")
    return blocked_reasons


def _p13_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        json=True,
        keep_temp_data=True,
        runtime_dir=None,
        launch_mode="dry_run",
        executor=args.executor,
        requested_agent_role=args.requested_agent_role,
        enable_native_process=False,
        auto_terminate=False,
        timeout_seconds=0.0,
        use_supervisor=False,
        supervisor_cleanup_after_launch=False,
    )


def run_smoke(runtime_data_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db_path = _configure_isolated_environment(runtime_data_dir)
    summary = _base_summary(runtime_data_dir.resolve(), sqlite_db_path.resolve())
    summary["isolated_runtime_data"] = runtime_data_dir.resolve() != DEFAULT_RUNTIME_DATA_DIR
    summary["launch_mode"] = args.launch_mode
    summary["requested_executor"] = args.executor
    summary["requested_agent_role"] = args.requested_agent_role

    if not summary["isolated_runtime_data"]:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("runtime_data_dir_must_be_isolated")
        return summary

    gate_blocks = _controlled_smoke_gate(args)
    if gate_blocks:
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].extend(gate_blocks)
        return summary

    if args.launch_mode == "controlled_smoke":
        summary["smoke_status"] = "blocked"
        summary["blocked_reasons"].append("controlled_subprocess_runner_not_configured")
        return summary

    p13_summary = run_p13_smoke(runtime_data_dir, _p13_args(args))
    summary.update(
        {
            "smoke_status": p13_summary["smoke_status"],
            "session_created": p13_summary["session_created"],
            "session_id": p13_summary["session_id"],
            "p11_dry_run_message_bound": p13_summary["p11_dry_run_message_bound"],
            "p12_safe_task_created": p13_summary["p12_safe_task_created"],
            "p13_dispatch_message_bound": p13_summary["p13_dispatch_message_bound"],
            "message_readback_ok": p13_summary["message_readback_ok"],
            "runtime_data_dir": p13_summary["runtime_data_dir"],
            "sqlite_db_path": p13_summary["sqlite_db_path"],
            "blocked_reasons": list(p13_summary["blocked_reasons"]),
        }
    )
    return summary


def main() -> int:
    args = _parse_args()
    temp_created = args.runtime_dir is None
    runtime_data_dir = (
        Path(tempfile.mkdtemp(prefix="p14-controlled-subprocess-smoke-"))
        if args.runtime_dir is None
        else args.runtime_dir
    ).resolve()
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = run_smoke(runtime_data_dir, args)
    finally:
        should_cleanup = temp_created and not args.keep_temp_data
        if should_cleanup:
            shutil.rmtree(runtime_data_dir, ignore_errors=True)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P14 controlled subprocess smoke: {summary['smoke_status']}")

    return 0 if summary["smoke_status"] in {"passed", "passed_dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
