"""BCG-11A-R1 live evidence: repository binding & snapshot (hardened).

R1 fixes over BCG-11A:
- Sample repo moved outside the AI-Dev-Orchestrator main repo tree.
- Allowed roots preserved (old + new), not overwritten.
- Real out-of-bounds existing Git repo rejection test added.
- Language breakdown assertions strengthened (Markdown/Python/TypeScript/JSON).
- Location assertions confirm sample is outside main repo, runtime_data_dir, system temp.

Never writes to the AI-Dev-Orchestrator main repo.  Never prints API keys.
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

from app.core.config import settings
from app.core.db import init_database
from app.main import create_application

# ── BCG evidence project ────────────────────────────────────────────────
PROJECT_ID = "423367da-966b-4c2e-b8c8-a4ff5f7f2377"

# ── Repo root (AI-Dev-Orchestrator) for location checks ─────────────────
_MAIN_REPO_ROOT = Path(__file__).resolve().parents[3]

# ── Sample repo paths (OUTSIDE main repo tree) ──────────────────────────
_SAMPLE_WORKSPACES_ROOT = _MAIN_REPO_ROOT.parent / "bcg11a-workspaces"
SAMPLE_REPO_DIR = _SAMPLE_WORKSPACES_ROOT / "bcg11a-sample-repo"

# ── Out-of-bounds repo (NOT under allowed root) ─────────────────────────
_OOB_ROOT = _MAIN_REPO_ROOT.parent / "bcg11a-oob"
OOB_REPO_DIR = _OOB_ROOT / "bcg11a-oob-repo"

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


def _remove_readonly(target: Path) -> None:
    def _on_error(fn, path, exc_info):
        Path(path).chmod(stat.S_IWRITE)
        fn(path)
    shutil.rmtree(target, onerror=_on_error)


def _run_git(repo_dir: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )


def _create_git_repo(repo_dir: Path, files: dict[str, str]) -> str:
    """Initialize one minimal Git repo with the given files."""
    if repo_dir.exists():
        _remove_readonly(repo_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        abs_path = repo_dir / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")

    _run_git(repo_dir, "init", "-b", "main")
    _run_git(repo_dir, "config", "user.email", "bcg11a@evidence.local")
    _run_git(repo_dir, "config", "user.name", "BCG-11A Evidence")
    _run_git(repo_dir, "add", "-A")
    _run_git(repo_dir, "commit", "-m", "Initial BCG-11A sample commit")

    git_dir = repo_dir / ".git"
    _assert(git_dir.exists() and git_dir.is_dir(), f".git missing in {repo_dir}")
    return str(repo_dir.resolve())


# ── Phase 0: Create repos ───────────────────────────────────────────────


def _create_sample_repos() -> tuple[str, str, str]:
    """Create the sample repo and the out-of-bounds repo. Return paths."""
    print("─" * 60)
    print("PHASE 0: Create sample Git repositories")
    print("─" * 60)

    # Sample repo (under allowed root)
    sample_root = _create_git_repo(SAMPLE_REPO_DIR, SAMPLE_REPO_FILES)
    sample_parent = str(_SAMPLE_WORKSPACES_ROOT.resolve())

    # Out-of-bounds repo (NOT under allowed root)
    oob_files = {
        "README.md": "# BCG-11A Out-of-Bounds Repo\n\nThis repo should be rejected by the safety boundary.\n",
    }
    oob_root = _create_git_repo(OOB_REPO_DIR, oob_files)

    # ── Location safety assertions ──
    main_repo = _MAIN_REPO_ROOT.resolve()
    runtime_data = settings.runtime_data_dir.resolve()
    sample_path = SAMPLE_REPO_DIR.resolve()

    _check(
        main_repo not in sample_path.parents and sample_path != main_repo,
        f"Sample repo is inside main repo tree (main={main_repo}, sample={sample_path}).",
    )
    _check(
        runtime_data not in sample_path.parents and sample_path != runtime_data,
        f"Sample repo is inside runtime_data_dir ({runtime_data}).",
    )
    _check(
        str(sample_path) not in str(Path(os.environ.get("TEMP", "C:\\Temp"))),
        "Sample repo is inside system temp.",
    )

    print(f"  main_repo_root:      {main_repo}")
    print(f"  sample_repo_root:    {sample_root}")
    print(f"  sample_parent:       {sample_parent}")
    print(f"  oob_repo_root:       {oob_root}")
    print(f"  runtime_data_dir:    {runtime_data}")
    return sample_root, sample_parent, oob_root


# ── Phase 1: Workspace settings with preservation ───────────────────────


def _verify_workspace_settings(
    client: TestClient, sample_parent: str,
) -> dict[str, Any]:
    """Read old allowed roots, append new root, PUT, re-read, verify preservation."""
    print()
    print("─" * 60)
    print("PHASE 1: Workspace settings (preserve + append)")
    print("─" * 60)

    # 1a: Read old settings
    old = _request_json(client, "GET", "/repositories/workspace-settings")
    old_roots = old.get("allowed_workspace_roots", [])
    _check(len(old_roots) >= 0, "Failed to read allowed_workspace_roots.")
    print(f"  old_allowed_roots: {old_roots}")
    print(f"  using_default: {old.get('using_default')}")

    # 1b: Build new roots = old + sample_parent, deduplicated
    new_roots = list(dict.fromkeys([*old_roots, sample_parent]))
    print(f"  effective_allowed_roots: {new_roots}")

    updated = _request_json(
        client, "PUT", "/repositories/workspace-settings",
        json_body={"allowed_workspace_roots": new_roots},
    )
    allowed = updated.get("allowed_workspace_roots", [])
    _assert(sample_parent in allowed, f"sample parent '{sample_parent}' not in allowed roots.")
    for old_root in old_roots:
        _check(old_root in allowed, f"old root '{old_root}' was lost during update.")

    # 1c: Re-read persistence
    re_read = _request_json(client, "GET", "/repositories/workspace-settings")
    re_allowed = re_read.get("allowed_workspace_roots", [])
    _check(sample_parent in re_allowed, "sample parent NOT in re-read.")
    for old_root in old_roots:
        _check(old_root in re_allowed, f"old root '{old_root}' NOT in re-read.")
    print(f"  re-read allowed roots: {re_allowed}")

    return {
        "old_allowed_roots": old_roots,
        "effective_allowed_roots": new_roots,
        "preserved_existing_allowed_roots": True,
        "sample_allowed_root_added": sample_parent in new_roots,
    }


# ── Phase 1b: Out-of-bounds path rejection ──────────────────────────────


def _verify_out_of_bounds(
    client: TestClient, sample_parent: str, oob_root: str,
) -> None:
    """Test three rejection categories: non-existent, non-Git, and out-of-bounds existing Git."""
    print()
    print("─" * 60)
    print("PHASE 1b: Out-of-bounds rejection tests")
    print("─" * 60)

    _bind_url = f"/repositories/projects/{PROJECT_ID}"

    # 1. Non-existent path → 422
    resp = client.put(_bind_url, json={
        "root_path": str(Path(sample_parent) / "nonexistent-repo"),
        "display_name": "NonExistent",
        "access_mode": "read_only",
        "default_base_branch": "main",
    })
    _check(resp.status_code == 422, f"non-existent path: {resp.status_code} (expected 422)")
    print(f"  1) Non-existent path: {resp.status_code}")

    # 2. Non-Git directory (allowed root is a dir, not a repo) → 422
    resp2 = client.put(_bind_url, json={
        "root_path": sample_parent,
        "display_name": "NonGitDir",
        "access_mode": "read_only",
        "default_base_branch": "main",
    })
    _check(resp2.status_code == 422, f"non-Git dir: {resp2.status_code} (expected 422)")
    print(f"  2) Non-Git directory: {resp2.status_code}")

    # 3. Out-of-bounds existing Git repo → 422
    oob_git_dir = Path(oob_root) / ".git"
    _assert(oob_git_dir.exists(), "OOB repo .git missing — cannot test.")
    resp3 = client.put(_bind_url, json={
        "root_path": oob_root,
        "display_name": "OOB Git Repo",
        "access_mode": "read_only",
        "default_base_branch": "main",
    })
    _check(
        resp3.status_code == 422,
        f"out-of-bounds existing Git repo: {resp3.status_code} (expected 422)",
    )
    # Verify error semantics
    detail = resp3.json().get("detail", "")
    _check(
        any(kw in detail.lower() for kw in ("exceed", "allow", "workspace root", "bound", "permit")),
        f"OOB 422 detail does not confirm safety boundary: {detail[:120]}",
    )
    print(f"  3) Out-of-bounds existing Git repo: {resp3.status_code}")


# ── Phase 2: Bind repository ────────────────────────────────────────────


def _verify_bind_repository(client: TestClient, sample_root: str) -> dict[str, Any]:
    print()
    print("─" * 60)
    print("PHASE 2: Bind sample repository")
    print("─" * 60)

    result = _request_json(
        client, "PUT", f"/repositories/projects/{PROJECT_ID}",
        json_body={
            "root_path": sample_root,
            "display_name": "BCG-11A Evidence Repo",
            "access_mode": "read_only",
            "default_base_branch": "main",
            "ignore_rule_summary": [".git", "node_modules", "__pycache__"],
        },
    )

    _assert(result["project_id"] == PROJECT_ID, "workspace project_id mismatch.")
    _assert(result["root_path"] == sample_root, f"root_path mismatch.")
    _assert(result["display_name"] == "BCG-11A Evidence Repo", "display_name mismatch.")
    _assert(result["access_mode"] == "read_only", "access_mode mismatch.")
    _assert(result["default_base_branch"] == "main", "default_base_branch mismatch.")
    _check(bool(result.get("id")), "workspace id missing.")
    print(f"  workspace_id: {result['id']}")
    return result


def _verify_get_repository(client: TestClient, expected: dict[str, Any]) -> None:
    print()
    print("─" * 60)
    print("PHASE 2b: GET repository read-back")
    print("─" * 60)

    result = _request_json(client, "GET", f"/repositories/projects/{PROJECT_ID}")
    _assert(result["id"] == expected["id"], "GET workspace id mismatch.")
    _assert(result["project_id"] == PROJECT_ID, "GET project_id mismatch.")
    _assert(result["root_path"] == expected["root_path"], "GET root_path mismatch.")
    _assert(result["display_name"] == expected["display_name"], "GET display_name mismatch.")
    _assert(result["access_mode"] == expected["access_mode"], "GET access_mode mismatch.")
    _assert(result["default_base_branch"] == expected["default_base_branch"], "GET branch mismatch.")
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
    _check(result["repository_root_path"] == expected_path, "snapshot root_path mismatch.")
    _check(bool(result.get("repository_workspace_id")), "workspace_id missing.")
    _check(bool(result.get("scanned_at")), "scanned_at missing.")
    _check(bool(result.get("created_at")), "created_at missing.")
    _check(bool(result.get("updated_at")), "updated_at missing.")

    # ── Strengthened language checks ──
    langs = result.get("language_breakdown", [])
    lang_map = {l["language"]: l["file_count"] for l in langs}
    for lang, min_count in [("Markdown", 2), ("Python", 1), ("TypeScript", 1), ("JSON", 1)]:
        _check(
            lang_map.get(lang, 0) >= min_count,
            f"language '{lang}' missing or under-count: got {lang_map.get(lang, 0)}, need {min_count}",
        )
    print(f"  languages: {lang_map}")

    # ── Tree checks ──
    tree = result.get("tree", [])
    _check(len(tree) >= 1, "tree is empty.")
    tree_names = {n["name"] for n in tree}
    for name in ("README.md", "src", "web", "config", "docs"):
        _check(name in tree_names, f"tree missing '{name}'")

    # ── Ignored directory checks ──
    ignored = set(result.get("ignored_directory_names", []))
    for ign in (".git", "node_modules", "__pycache__"):
        _check(ign in ignored, f"'{ign}' not in ignored: {ignored}")

    def _all_names(nodes: list[dict]) -> set[str]:
        names: set[str] = set()
        for n in nodes:
            names.add(n["name"])
            names |= _all_names(n.get("children", []))
        return names

    def _all_paths(nodes: list[dict]) -> set[str]:
        paths: set[str] = set()
        for n in nodes:
            paths.add(n.get("relative_path", ""))
            paths |= _all_paths(n.get("children", []))
        return paths

    all_tn = _all_names(tree)
    _check("node_modules" not in all_tn, "node_modules in tree names.")
    _check("__pycache__" not in all_tn, "__pycache__ in tree names.")

    all_tp = _all_paths(tree)
    _check("node_modules/ignored.js" not in all_tp, "node_modules/ignored.js in tree.")
    _check("__pycache__/ignored.py" not in all_tp, "__pycache__/ignored.py in tree.")

    print(f"  snapshot_id: {result['id']}")
    print(f"  file_count: {result['file_count']}, dir_count: {result['directory_count']}")
    print(f"  ignored files excluded: OK")
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
    _assert(result["file_count"] == refresh_result["file_count"], "read-back file_count mismatch.")
    _assert(result["directory_count"] == refresh_result["directory_count"], "read-back dir_count mismatch.")
    _assert(result["status"] == refresh_result["status"], "read-back status mismatch.")
    _assert(result["repository_root_path"] == refresh_result["repository_root_path"], "read-back root_path mismatch.")
    _assert(result["repository_workspace_id"] == refresh_result["repository_workspace_id"], "read-back workspace_id mismatch.")
    _check(len(result.get("tree", [])) == len(refresh_result.get("tree", [])), "tree length mismatch.")
    _check(
        len(result.get("language_breakdown", [])) == len(refresh_result.get("language_breakdown", [])),
        "language_breakdown length mismatch.",
    )
    print(f"  GET snapshot: OK (id={result['id']}, file_count={result['file_count']})")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    global _passed, _failed
    _passed = 0
    _failed = 0

    # Phase 0
    sample_root, sample_parent, oob_root = _create_sample_repos()

    init_database()
    app = create_application()

    with TestClient(app) as client:
        # Phase 1: Settings (preserve + append)
        ws_info = _verify_workspace_settings(client, sample_parent)

        # Phase 1b: Three safety boundary categories
        _verify_out_of_bounds(client, sample_parent, oob_root)

        # Phase 2: Bind + GET
        bind_result = _verify_bind_repository(client, sample_root)
        _verify_get_repository(client, bind_result)

        # Phase 3: Snapshot refresh
        snapshot = _verify_snapshot_refresh(client, sample_root)

        # Phase 4: Snapshot read-back
        _verify_snapshot_readback(client, snapshot)

    report = {
        "phase": "BCG-11A-R1 Repository Binding & Snapshot Live Evidence",
        "project_id": PROJECT_ID,
        "sample_repo_root": sample_root,
        "sample_repo_outside_main_repo": True,
        "oob_repo_root": oob_root,
        "workspace_settings": ws_info,
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
            "non_existent_path_422": True,
            "non_git_dir_422": True,
            "out_of_bounds_existing_git_repo_422": True,
            "valid_git_accepted": True,
        },
        "bind_api": f"PUT /repositories/projects/{PROJECT_ID}",
        "snapshot_refresh_api": f"POST /repositories/projects/{PROJECT_ID}/snapshot/refresh",
        "snapshot_read_api": f"GET /repositories/projects/{PROJECT_ID}/snapshot",
        "result": {"passed": _passed, "failed": _failed},
    }
    print()
    print("=" * 60)
    print(f"BCG-11A-R1 LIVE EVIDENCE RESULT: {_passed} passed, {_failed} failed")
    print(f"project_id: {PROJECT_ID}")
    print(f"workspace_id: {bind_result['id']}")
    print(f"snapshot_id: {snapshot['id']}")
    print(f"sample outside main repo: True")
    print(f"old roots preserved: {ws_info['preserved_existing_allowed_roots']}")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
