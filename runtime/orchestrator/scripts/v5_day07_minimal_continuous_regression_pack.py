"""Day07 minimal continuous regression pack orchestrator.

This entrypoint fixes the Day07 minimal recurring regression scope to four checks:
1) role_model_policy control-surface mainline
2) role_model_policy boundary paths
3) degraded / no-run / no-routable paths
4) same-sample homepage vs project-detail page consistency
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Sequence
from urllib.error import URLError
from urllib.request import urlopen


SCRIPT_PATH = Path(__file__).resolve()
RUNTIME_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = RUNTIME_ROOT.parents[1]


def _http_ok(url: str, timeout_seconds: float = 2.0) -> bool:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= response.status < 400
    except URLError:
        return False


def _wait_http_ok(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _http_ok(url, timeout_seconds=2.0):
            return True
        time.sleep(1.0)
    return False


def _run_case(
    *,
    name: str,
    command: Sequence[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    start = time.time()
    print(f"[day07-pack] running: {name}")
    print(f"[day07-pack] command: {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
    )
    duration = round(time.time() - start, 3)
    passed = completed.returncode == 0
    if not passed:
        print(f"[day07-pack] FAILED: {name} (exit={completed.returncode})")
        if completed.stdout:
            print("[day07-pack] stdout tail:")
            print(completed.stdout.decode("utf-8", errors="replace")[-2000:])
        if completed.stderr:
            print("[day07-pack] stderr tail:")
            print(completed.stderr.decode("utf-8", errors="replace")[-2000:])
    else:
        print(f"[day07-pack] passed: {name} ({duration}s)")

    return {
        "name": name,
        "command": " ".join(command),
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "status": "passed" if passed else "failed",
        "duration_seconds": duration,
    }


def _start_backend_for_web(*, health_url: str) -> subprocess.Popen[str] | None:
    if _http_ok(health_url):
        print("[day07-pack] backend health already up, reusing existing backend")
        return None

    runtime_data_dir = RUNTIME_ROOT / "tmp" / "day07-minimal-regression-pack-backend"
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("RUNTIME_DATA_DIR", str(runtime_data_dir))

    print("[day07-pack] backend health is down, starting temporary uvicorn backend")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(RUNTIME_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    if not _wait_http_ok(health_url, timeout_seconds=45.0):
        process.terminate()
        raise SystemExit(
            "Day07 minimal regression pack blocked: backend was down and temporary uvicorn "
            "did not reach healthy state in 45s."
        )

    print("[day07-pack] temporary backend is healthy")
    return process


def _stop_backend(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Day07 minimal continuous regression pack. "
            "Use --mode runtime to run only runtime-side three facts."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("full", "runtime"),
        default="full",
        help="full=3 runtime smokes + 1 web same-sample check; runtime=3 runtime smokes only",
    )
    parser.add_argument(
        "--app-origin",
        default="http://127.0.0.1:5173",
        help="frontend origin used by same-sample web consistency spec",
    )
    parser.add_argument(
        "--backend-health",
        default="http://127.0.0.1:8000/health",
        help="backend health endpoint used before web consistency spec",
    )
    parser.add_argument(
        "--no-auto-start-backend",
        action="store_true",
        help="disable auto-starting temporary backend when backend health is down",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    runtime_cases: list[tuple[str, list[str], Path]] = [
        (
            "role_model_policy_control_surface_mainline",
            [
                sys.executable,
                "runtime/orchestrator/scripts/v5_day07_role_model_policy_control_surface_smoke.py",
            ],
            REPO_ROOT,
        ),
        (
            "role_model_policy_boundary_paths",
            [
                sys.executable,
                "runtime/orchestrator/scripts/v5_day07_role_model_policy_boundary_smoke.py",
            ],
            REPO_ROOT,
        ),
        (
            "degraded_no_run_no_routable",
            [
                sys.executable,
                "runtime/orchestrator/scripts/v5_day07_control_surface_degraded_smoke.py",
            ],
            REPO_ROOT,
        ),
    ]

    web_case: tuple[str, list[str], Path] = (
        "same_sample_page_level_consistency",
        [
            "npx.cmd",
            "--prefix",
            "apps/web",
            "playwright",
            "test",
            "apps/web/scripts/day07_same_sample_page_consistency.spec.mjs",
            "--workers=1",
        ],
        REPO_ROOT,
    )

    backend_process: subprocess.Popen[str] | None = None
    results: list[dict[str, object]] = []

    try:
        for name, command, cwd in runtime_cases:
            result = _run_case(name=name, command=command, cwd=cwd)
            results.append(result)
            if result["status"] != "passed":
                print("[day07-pack] stop on first failure in runtime pack")
                break

        all_runtime_passed = all(item["status"] == "passed" for item in results)

        if args.mode == "full" and all_runtime_passed:
            if not _http_ok(args.app_origin):
                raise SystemExit(
                    "Day07 minimal regression pack blocked: frontend origin is not reachable "
                    f"({args.app_origin}). Start frontend dev server first."
                )
            if args.no_auto_start_backend:
                if not _http_ok(args.backend_health):
                    raise SystemExit(
                        "Day07 minimal regression pack blocked: backend health is down and "
                        "--no-auto-start-backend is set."
                    )
            else:
                backend_process = _start_backend_for_web(health_url=args.backend_health)

            name, command, cwd = web_case
            results.append(_run_case(name=name, command=command, cwd=cwd))

        failed = [item for item in results if item["status"] != "passed"]
        summary = {
            "day": "Day07",
            "pack": "minimal_continuous_regression",
            "mode": args.mode,
            "fixed_scope": [
                "role_model_policy_control_surface_mainline",
                "role_model_policy_boundary_paths",
                "degraded_no_run_no_routable",
                "same_sample_page_level_consistency",
            ],
            "results": results,
            "overall_status": "passed" if not failed else "failed",
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        if failed:
            raise SystemExit(1)
    finally:
        _stop_backend(backend_process)


if __name__ == "__main__":
    main()
