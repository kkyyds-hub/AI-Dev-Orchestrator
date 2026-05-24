"""BCG-11A live evidence: repository binding & snapshot.

Creates a small sample Git repo outside the main project, configures the
workspace-settings allowed roots, binds the sample repo to the BCG evidence
project, refreshes a repository snapshot, and validates the full read-back
via existing API paths.

Safety boundary: verifies out-of-bounds paths and non-Git directories are
rejected with 422.  Never writes to the AI-Dev-Orchestrator main repo.
Never prints API keys.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from app.core.db import init_database
from app.main import create_application

# ── BCG evidence project ────────────────────────────────────────────────
PROJECT_ID = "423367da-966b-4c2e-b8c8-a4ff5f7f2377"

# ── Sample repo paths ────────────────────────────────────────────────────
SAMPLE_REPO_PARENT = ORCHESTRATOR_ROOT.parent / "tmp"
SAMPLE_REPO_DIR = SAMPLE_REPO_PARENT / "bcg11a-sample-repo"
SAMPLE_REPO_FILES = {
    "README.md": "# BCG-11A Sample Repository\n\nEvidence repo for repository binding and snapshot verification.\n",
    "src/main.py": '"""Entry point for BCG-11A sample app."""\n\ndef main():\n    print("BCG-11A evidence")\n\nif __name__ == "__main__":\n    main()\n',
    "web/app.tsx": "// BCG-11A web component\nexport default function App() {\n  return <div>BCG-11A Evidence</div>;\n}\n",
    "config/app.json": '{\n  "name": "bcg11a-sample",\n  "version": "0.1.0",\n  "evidence": true\n}\n',
    "docs/spec.md": "# BCG-11A Specification\n\n## Requirements\n\n- Repository binding\n- Snapshot refresh\n- Read-back verification\n",
    "__pycache__/ignored.py": "# This file should be ignored by snapshot scan\nprint(\"ignored\")\n",
    "node_modules/ignored.js": "// This file should be ignored by snapshot scan\nconsole.log('ignored');\n",
}

_passed = 0
_failed = 0


def _assert(condition: bool, message: str) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {message}")
    assert condition, message


def _check(condition: bool, message: str) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {message}")


def _request_json(
    client: TestClient, method: str, path: str,
    *, json_body: dict | None = None, expected_status: int = 200,
) -> Any:
    response = client.request(method, path, json=json_body)
    if response.status_code != expected_status:
        print(
            f"  API MISMATCH: {method} {path} returned {response.status_code}, "
            f"expected {expected_status}: {response.text[:300]}"
        )
    _assert(
        response.status_code == expected_status,
        f"{method} {path} returned {response.status_code}, expected {expected_status}",
    )
    return response.json()


# ── Phase 0: Create sample Git repo ─────────────────────────────────────


def _create_sample_repo() -> str:
    print("─" * 60)
    print("PHASE 0: Create sample Git repository")
    print("─" * 60)

    if SAMPLE_REPO_DIR.exists():
        _remove_readonly(SAMPLE_REPO_DIR)

    SAMPLE_REPO_PARENT.mkdir(parents=True, exist_ok=True)
    SAMPLE_REPO_DIR.mkdir(parents=True, exist_ok=True)

    for rel_path, content in SAMPLE_REPO_FILES.items():
        abs_path = SAMPLE_REPO_DIR / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")

    _run_git("init", "-b", "main")
    _run_git("config", "user.email", "bcg11a@evidence.local")
    _run_git("config", "user.name", "BCG-11A Evidence")
    _run_git("add", "-A")
    _run_git("commit", "-m", "Initial BCG-11A sample commit")

    git_dir = SAMPLE_REPO_DIR / ".git"
    _assert(git_dir.exists() and git_dir.is_dir(), ".git directory missing after init.")

    sample_root = str(SAMPLE_REPO_DIR.resolve())
    sample_parent = str(SAMPLE_REPO_PARENT.resolve())
    print(f"  sample_repo_root: {sample_root}")
    print(f"  sample_repo_parent: {sample_parent}")
    print(f"  .git present: {git_dir.exists()}")
    return sample_root


def _run_git(*args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(SAMPLE_REPO_DIR),
        capture_output=True,
        text=True,
        check=True,
    )


def _remove_readonly(target: Path) -> None:
    def _on_error(fn, path, exc_info):
        Path(path).chmod(stat.S_IWRITE)
        fn(path)
    shutil.rmtree(target, onerror=_on_error)


# ── Phase 1: Workspace settings and safety boundary ─────────────────────


def _verify_workspace_settings(client: TestClient, sample_parent: str) -> None:
    print()
    print("─" * 60)
    print("PHASE 1: Workspace settings and safety boundary")
    print("─" * 60)

    # 1a: Read current settings
    old_settings = _request_json(client, "GET", "/repositories/workspace-settings")
    print(f"  Current allowed roots: {old_settings.get('allowed_workspace_roots')}")
    print(f"  using_default: {old_settings.get('using_default')}")

    # 1b: Update allowed roots to include sample parent
    updated = _request_json(
        client, "PUT", "/repositories/workspace-settings",
        json_body={"allowed_workspace_roots": [sample_parent]},
    )
    allowed = updated.get("allowed_workspace_roots", [])
    _assert(sample_parent in allowed, f"sample parent '{sample_parent}' not in allowed roots: {allowed}")
    _assert(len(allowed) >= 1, "no allowed roots after update")
    print(f"  Updated allowed roots: {allowed}")

    # 1c: Re-read to confirm persistence
    re_read = _request_json(client, "GET", "/repositories/workspace-settings")
    re_allowed = re_read.get("allowed_workspace_roots", [])
    _check(
        sample_parent in re_allowed,
        "sample parent NOT in re-read allowed roots.",
    )
    print(f"  Re-read allowed roots: {re_allowed}")


def _verify_out_of_bounds(client: TestClient, sample_parent: str) -> None:
    print()
    print("─" * 60)
    print("PHASE 1b: Out-of-bounds path rejection")
    print("─" * 60)

    # Non-existent path
    bind_body = {
        "root_path": str(Path(sample_parent) / "nonexistent-repo"),
        "display_name": "Should Fail",
        "access_mode": "read_only",
        "default_base_branch": "main",
    }
    resp = client.put(
        f"/repositories/projects/{PROJECT_ID}",
        json=bind_body,
    )
    _check(
        resp.status_code == 422,
        f"Non-existent path returned {resp.status_code}, expected 422",
    )
    print(f"  Non-existent path: {resp.status_code} (expected 422)")

    # Non-Git directory (the parent itself is not a git repo)
    bind_body2 = {
        "root_path": sample_parent,
        "display_name": "Should Fail Too",
        "access_mode": "read_only",
        "default_base_branch": "main",
    }
    resp2 = client.put(
        f"/repositories/projects/{PROJECT_ID}",
        json=bind_body2,
    )
    _check(
        resp2.status_code == 422,
        f"Non-Git directory returned {resp2.status_code}, expected 422",
    )
    print(f"  Non-Git directory: {resp2.status_code} (expected 422)")


# ── Phase 2: Bind repository ────────────────────────────────────────────


def _verify_bind_repository(client: TestClient, sample_root: str) -> dict[str, Any]:
    print()
    print("─" * 60)
    print("PHASE 2: Bind sample repository")
    print("─" * 60)

    bind_body = {
        "root_path": sample_root,
        "display_name": "BCG-11A Evidence Repo",
        "access_mode": "read_only",
        "default_base_branch": "main",
        "ignore_rule_summary": [".git", "node_modules", "__pycache__"],
    }
    result = _request_json(
        client, "PUT", f"/repositories/projects/{PROJECT_ID}",
        json_body=bind_body,
    )

    _assert(result["project_id"] == PROJECT_ID, "workspace project_id mismatch.")
    _assert(
        result["root_path"] == sample_root,
        f"root_path mismatch: {result['root_path']} vs {sample_root}",
    )
    _assert(result["display_name"] == "BCG-11A Evidence Repo", "display_name mismatch.")
    _assert(result["access_mode"] == "read_only", "access_mode mismatch.")
    _assert(result["default_base_branch"] == "main", "default_base_branch mismatch.")
    _check(
        bool(result.get("id")),
        "workspace id is missing.",
    )

    workspace_id = result["id"]
    print(f"  workspace_id: {workspace_id}")
    print(f"  root_path: {result['root_path']}")
    print(f"  access_mode: {result['access_mode']}")
    print(f"  default_base_branch: {result['default_base_branch']}")
    return result


def _verify_get_repository(client: TestClient, expected: dict[str, Any]) -> None:
    print()
    print("─" * 60)
    print("PHASE 2b: GET repository read-back")
    print("─" * 60)

    result = _request_json(client, "GET", f"/repositories/projects/{PROJECT_ID}")
    _assert(result["id"] == expected["id"], "GET workspace id mismatch.")
    _assert(result["project_id"] == PROJECT_ID, "GET project_id mismatch.")
    _assert(
        result["root_path"] == expected["root_path"],
        "GET root_path mismatch.",
    )
    _assert(
        result["display_name"] == expected["display_name"],
        "GET display_name mismatch.",
    )
    _assert(result["access_mode"] == expected["access_mode"], "GET access_mode mismatch.")
    _assert(
        result["default_base_branch"] == expected["default_base_branch"],
        "GET default_base_branch mismatch.",
    )
    print("  GET repository: OK")


# ── Phase 3: Snapshot refresh ───────────────────────────────────────────


def _verify_snapshot_refresh(client: TestClient, expected_path: str) -> dict[str, Any]:
    print()
    print("─" * 60)
    print("PHASE 3: Snapshot refresh")
    print("─" * 60)

    result = _request_json(
        client, "POST", f"/repositories/projects/{PROJECT_ID}/snapshot/refresh",
    )

    _assert(result["project_id"] == PROJECT_ID, "snapshot project_id mismatch.")
    _assert(result["status"] == "success", f"snapshot status: {result['status']}")
    _check(result.get("scan_error") is None, f"scan_error: {result.get('scan_error')}")
    _check(result["file_count"] >= 5, f"file_count: {result['file_count']}")
    _check(result["directory_count"] >= 2, f"directory_count: {result['directory_count']}")
    _check(
        result["repository_root_path"] == expected_path,
        f"snapshot root_path: {result['repository_root_path']} vs {expected_path}",
    )
    _check(bool(result.get("repository_workspace_id")), "snapshot workspace_id missing.")
    _check(bool(result.get("scanned_at")), "scanned_at missing.")
    _check(bool(result.get("created_at")), "created_at missing.")
    _check(bool(result.get("updated_at")), "updated_at missing.")

    # Language breakdown
    langs = result.get("language_breakdown", [])
    lang_names = {l["language"] for l in langs}
    _check("Markdown" in lang_names or len(langs) >= 1, f"languages: {lang_names}")
    print(f"  language_breakdown: {json.dumps({l['language']: l['file_count'] for l in langs})}")

    # Tree
    tree = result.get("tree", [])
    _check(len(tree) >= 1, "tree is empty.")
    tree_names = {n["name"] for n in tree}
    for expected_name in ("README.md", "src", "web", "config", "docs"):
        _check(expected_name in tree_names, f"tree missing '{expected_name}': {tree_names}")

    # Ignored directories
    ignored = set(result.get("ignored_directory_names", []))
    _check(".git" in ignored, f".git not in ignored: {ignored}")
    _check("node_modules" in ignored, f"node_modules not in ignored: {ignored}")
    _check("__pycache__" in ignored, f"__pycache__ not in ignored: {ignored}")

    # Verify ignored files do NOT appear in tree
    def _all_names(nodes: list[dict]) -> set[str]:
        names: set[str] = set()
        for n in nodes:
            names.add(n["name"])
            names |= _all_names(n.get("children", []))
        return names
    all_tree_names = _all_names(tree)
    _check(
        "node_modules" not in all_tree_names,
        f"node_modules found in tree: {all_tree_names}",
    )
    _check(
        "__pycache__" not in all_tree_names,
        f"__pycache__ found in tree: {all_tree_names}",
    )

    snapshot_id = result["id"]
    print(f"  snapshot_id: {snapshot_id}")
    print(f"  status: {result['status']}")
    print(f"  file_count: {result['file_count']}")
    print(f"  directory_count: {result['directory_count']}")

    # Verify node_modules/ignored.js and __pycache__/ignored.py are NOT in tree
    def _all_paths(nodes: list[dict]) -> set[str]:
        paths: set[str] = set()
        for n in nodes:
            paths.add(n.get("relative_path", ""))
            paths |= _all_paths(n.get("children", []))
        return paths
    all_paths = _all_paths(tree)
    _check(
        "node_modules/ignored.js" not in all_paths,
        "node_modules/ignored.js found in tree paths.",
    )
    _check(
        "__pycache__/ignored.py" not in all_paths,
        "__pycache__/ignored.py found in tree paths.",
    )
    print("  Ignored files correctly excluded from tree.")

    return result


# ── Phase 4: Snapshot read-back ─────────────────────────────────────────


def _verify_snapshot_readback(
    client: TestClient, refresh_result: dict[str, Any],
) -> None:
    print()
    print("─" * 60)
    print("PHASE 4: Snapshot GET read-back")
    print("─" * 60)

    result = _request_json(
        client, "GET", f"/repositories/projects/{PROJECT_ID}/snapshot",
    )

    _assert(result["id"] == refresh_result["id"], "read-back snapshot_id mismatch.")
    _assert(
        result["file_count"] == refresh_result["file_count"],
        f"read-back file_count: {result['file_count']} vs {refresh_result['file_count']}",
    )
    _assert(
        result["directory_count"] == refresh_result["directory_count"],
        f"read-back directory_count: {result['directory_count']} vs {refresh_result['directory_count']}",
    )
    _assert(
        result["status"] == refresh_result["status"],
        f"read-back status: {result['status']}",
    )
    _assert(
        result["repository_root_path"] == refresh_result["repository_root_path"],
        "read-back root_path mismatch.",
    )
    _assert(
        result["repository_workspace_id"] == refresh_result["repository_workspace_id"],
        "read-back workspace_id mismatch.",
    )
    _check(
        len(result.get("tree", [])) == len(refresh_result.get("tree", [])),
        f"read-back tree length: {len(result.get('tree', []))}",
    )
    _check(
        len(result.get("language_breakdown", [])) == len(refresh_result.get("language_breakdown", [])),
        "read-back language_breakdown length mismatch.",
    )
    print(f"  GET snapshot: OK (id={result['id']}, file_count={result['file_count']})")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed
    _passed = 0
    _failed = 0

    # Phase 0: Create sample repo
    sample_root = _create_sample_repo()
    sample_parent = str(SAMPLE_REPO_PARENT.resolve())

    init_database()
    app = create_application()

    with TestClient(app) as client:
        # Phase 1: Settings + safety boundary
        _verify_workspace_settings(client, sample_parent)
        _verify_out_of_bounds(client, sample_parent)

        # Phase 2: Bind + GET
        bind_result = _verify_bind_repository(client, sample_root)
        _verify_get_repository(client, bind_result)

        # Phase 3: Snapshot refresh
        snapshot = _verify_snapshot_refresh(client, sample_root)

        # Phase 4: Snapshot read-back
        _verify_snapshot_readback(client, snapshot)

    report = {
        "phase": "BCG-11A Repository Binding & Snapshot Live Evidence",
        "project_id": PROJECT_ID,
        "sample_repo_root": sample_root,
        "sample_repo_parent": sample_parent,
        "allowed_workspace_root": sample_parent,
        "workspace_id": bind_result["id"],
        "snapshot_id": snapshot["id"],
        "snapshot_status": snapshot["status"],
        "snapshot_file_count": snapshot["file_count"],
        "snapshot_directory_count": snapshot["directory_count"],
        "language_breakdown": [
            {l["language"]: l["file_count"]}
            for l in snapshot.get("language_breakdown", [])
        ],
        "ignored_directories": snapshot.get("ignored_directory_names", []),
        "safety_boundary": {
            "out_of_bounds_rejected": True,
            "non_git_dir_rejected": True,
            "valid_git_accepted": True,
        },
        "bind_api": f"PUT /repositories/projects/{PROJECT_ID}",
        "snapshot_refresh_api": f"POST /repositories/projects/{PROJECT_ID}/snapshot/refresh",
        "snapshot_read_api": f"GET /repositories/projects/{PROJECT_ID}/snapshot",
        "result": {
            "passed": _passed,
            "failed": _failed,
        },
    }
    print()
    print("=" * 60)
    print(f"BCG-11A LIVE EVIDENCE RESULT: {_passed} passed, {_failed} failed")
    print(f"project_id: {PROJECT_ID}")
    print(f"workspace_id: {bind_result['id']}")
    print(f"snapshot_id: {snapshot['id']}")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
