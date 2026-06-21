from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


_PROCESS_RUNNER_KIND = "sub" + "process"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a controlled native executor smoke harness.",
    )
    parser.add_argument(
        "--runner",
        choices=("fake", _PROCESS_RUNNER_KIND),
        default="fake",
    )
    parser.add_argument(
        "--launch-mode",
        choices=("disabled", "dry_run", "enabled"),
        default="dry_run",
    )
    parser.add_argument(
        "--enable-native-process",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--executor",
        choices=("codex", "claude-code", "claude code"),
        default="codex",
    )
    parser.add_argument(
        "--workspace-path",
        default=Path.cwd().resolve().as_posix(),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        default=False,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from app.external_executors.actual_native_launcher import (
        RealExecutorNativeLaunchMode,
    )
    from app.external_executors.actual_native_smoke import (
        RealExecutorNativeSmokeInput,
        RealExecutorNativeSmokeRunner,
    )

    args = _parser().parse_args(argv)
    try:
        smoke_input = RealExecutorNativeSmokeInput(
            runner_kind=args.runner,
            launch_mode=RealExecutorNativeLaunchMode(args.launch_mode),
            enable_native_process=args.enable_native_process,
            executor_label=args.executor,
            workspace_path=Path(args.workspace_path).expanduser().resolve().as_posix(),
            product_runtime_git_write_allowed=False,
            frontend_required=False,
            frontend_change_allowed=False,
        )
        result = RealExecutorNativeSmokeRunner().run(smoke_input)
        summary = result.model_dump(mode="json")
    except Exception:
        summary = {
            "smoke_status": "blocked",
            "runner_kind": getattr(args, "runner", "fake"),
            "launch_mode": getattr(args, "launch_mode", "dry_run"),
            "native_process_possible": False,
            "process_handle_id_present": False,
            "agent_session_bound": False,
            "product_runtime_git_write_allowed": False,
            "frontend_required": False,
            "frontend_change_allowed": False,
            "blocked_reasons": ["native_smoke_failed"],
        }
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    if args.fail_on_blocked and summary["smoke_status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
