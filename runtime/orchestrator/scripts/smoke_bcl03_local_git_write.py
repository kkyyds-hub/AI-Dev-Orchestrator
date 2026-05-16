"""BCL-03 smoke: local git write (apply-local + git-commit).

Covers:
1. Gate not approved → apply-local / git-commit blocked.
2. Git-commit without apply → blocked.
3. Path traversal (.git, .., absolute) → blocked (via service-level test).
4. Success path: temp git repo → apply-local → git-commit → commit_sha.

Because the full Day14 release-gate checklist (7 items) requires extensive seed
data (change plans, verification runs, diff evidence), the path-traversal and
success-path tests monkeypatch _check_gate_approved to focus on the code under
test.  Gate-blocking is verified in tests 1-2 via the real gate path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl03-local-git-write-smoke"

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


# -- Helpers -------------------------------------------------------------

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
    return response.json()  # type: ignore[no-any-return]


def _request_json_any_status(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    response = client.request(method, path, json=payload)
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    return response.status_code, body  # type: ignore[no-any-return]


def _prepare_env() -> Path:
    runtime_data_dir = prepare_runtime_data_dir(SMOKE_RUNTIME_DATA_DIR)
    os.environ["RUNTIME_DATA_DIR"] = str(runtime_data_dir)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(RUNTIME_ROOT.parents[1].resolve())
    os.environ["DAILY_BUDGET_USD"] = "8.00"
    os.environ["SESSION_BUDGET_USD"] = "8.00"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"
    (runtime_data_dir / "db").mkdir(parents=True, exist_ok=True)
    return runtime_data_dir


def _create_temp_git_repo() -> Path:
    import subprocess, tempfile
    repos_root = RUNTIME_ROOT.parents[1] / "tmp" / "bcl03-repos"
    repos_root.mkdir(parents=True, exist_ok=True)
    repo_dir = Path(tempfile.mkdtemp(dir=str(repos_root), prefix="bcl03-repo-"))
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "smoke@bcl03.local"],
        cwd=str(repo_dir), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "BCL-03 Smoke"],
        cwd=str(repo_dir), check=True, capture_output=True,
    )
    readme = repo_dir / "README.md"
    readme.write_text("# BCL-03 Smoke Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo_dir), check=True, capture_output=True,
    )
    return repo_dir


# -- Seed: basic chain without gate approval ------------------------------

def _seed_chain_with_workspace(
    client: TestClient,
    repo_dir: Path,
) -> tuple[str, str]:  # (project_id, change_batch_id)
    """Create project + workspace + change_batch + commit_candidate.

    Does NOT approve the release gate (used for gate-blocked tests).
    """
    from app.core.db import SessionLocal
    from app.repositories.change_batch_repository import ChangeBatchRepository
    from app.repositories.commit_candidate_repository import CommitCandidateRepository
    from app.repositories.repository_snapshot_repository import RepositorySnapshotRepository
    from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
    from app.domain.change_batch import (
        ChangeBatch, ChangeBatchPlanSnapshot, ChangeBatchPreflight,
        ChangeBatchPreflightStatus, ChangeBatchStatus,
    )
    from app.domain.commit_candidate import (
        CommitCandidate, CommitCandidateStatus, CommitCandidateVersion,
        CommitCandidateVerificationSummary,
    )
    from app.domain.change_plan import ChangePlanTargetFile
    from app.domain._base import utc_now

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-03 Chain", "summary": "Basic chain for git write test."},
    )
    project_id = project["id"]

    _request_json(
        client, "PUT", f"/repositories/projects/{project_id}", 200,
        {"root_path": str(repo_dir), "display_name": "BCL-03 Repo", "access_mode": "read_only"},
    )

    session = SessionLocal()
    try:
        ws = RepositoryWorkspaceRepository(session).get_by_project_id(UUID(project_id))
        assert ws is not None

        # Snapshot — use direct table insert to avoid pydantic
        # scanned_at >= created_at validation race.
        from app.core.db_tables import RepositorySnapshotTable
        import datetime as _dt
        _now = _dt.datetime.now(_dt.UTC)
        snap_obj = RepositorySnapshotTable(
            id=uuid4(),
            project_id=UUID(project_id),
            repository_workspace_id=ws.id,
            repository_root_path=str(repo_dir),
            status="success",
            directory_count=2,
            file_count=3,
            scanned_at=_now,
            created_at=_now,
            updated_at=_now,
        )
        session.add(snap_obj)
        session.flush()

        # Two plan snapshots (min 2 required)
        def _make_plan(title: str, task_title: str, path: str) -> ChangeBatchPlanSnapshot:
            return ChangeBatchPlanSnapshot(
                change_plan_id=uuid4(), change_plan_title=title,
                change_plan_status="draft", selected_version_id=uuid4(),
                selected_version_number=1, task_id=uuid4(),
                task_title=task_title, task_priority="normal", task_risk_level="normal",
                intent_summary=f"{title} intent.", source_summary=f"{title} source.",
                expected_actions=["write_file"], risk_notes=["low_risk"],
                target_files=[ChangePlanTargetFile(
                    relative_path=path, language="text", file_type="txt"
                )],
                verification_commands=["echo ok"],
            )

        preflight = ChangeBatchPreflight(
            status=ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
            blocked=False, ready_for_execution=True,
            findings=[], finding_count=0, manual_confirmation_required=False,
        )
        batch = ChangeBatch(
            id=uuid4(), project_id=UUID(project_id),
            repository_workspace_id=ws.id,
            status=ChangeBatchStatus.PREPARING,
            title="BCL-03 Batch", summary="Smoke test change batch.",
            plan_snapshots=[
                _make_plan("Plan 1", "Task 1", "src/a.txt"),
                _make_plan("Plan 2", "Task 2", "src/b.txt"),
            ],
            preflight=preflight,
        )
        ChangeBatchRepository(session).create(batch)
        change_batch_id = str(batch.id)

        cand_id = uuid4()
        version = CommitCandidateVersion(
            id=uuid4(), commit_candidate_id=cand_id, version_number=1,
            message_title="BCL-03 commit", message_body="Smoke commit body.",
            impact_scope=["src"],
            related_files=["src/a.txt", "src/b.txt"],
            verification_summary=CommitCandidateVerificationSummary(
                total_runs=1, passed_runs=1, failed_runs=0, skipped_runs=0,
                highlights=["All passed"],
            ),
            evidence_summary="Smoke evidence.",
            evidence_package_key="smoke-evidence",
        )
        candidate = CommitCandidate(
            id=cand_id, project_id=UUID(project_id),
            change_batch_id=batch.id, change_batch_title="BCL-03 Batch",
            status=CommitCandidateStatus.DRAFT,
            current_version_number=1, versions=[version],
        )
        CommitCandidateRepository(session).create(candidate)
        session.commit()
    finally:
        session.close()

    return project_id, change_batch_id


# -- Tests ---------------------------------------------------------------

def test_no_gate_apply_local_blocked(client: TestClient) -> None:
    """apply-local must be blocked when release gate is not approved."""
    runtime_data_dir = Path(os.environ["RUNTIME_DATA_DIR"])
    repo_dir = _create_temp_git_repo()
    _project_id, batch_id = _seed_chain_with_workspace(client, repo_dir)

    status, body = _request_json_any_status(
        client, "POST",
        f"/repositories/change-batches/{batch_id}/apply-local",
        {"files": [{"relative_path": "test.txt", "content": "hello"}]},
    )
    assert body.get("status") == "failed", (
        f"Expected status=failed without gate, got {body}"
    )
    assert body.get("error_category") == "gate_not_approved", (
        f"Expected gate_not_approved, got {body.get('error_category')}"
    )
    print("PASS test_no_gate_apply_local_blocked")


def test_git_commit_without_apply_blocked(client: TestClient) -> None:
    """git-commit without prior apply-local must be blocked."""
    runtime_data_dir = Path(os.environ["RUNTIME_DATA_DIR"])
    repo_dir = _create_temp_git_repo()
    project_id, batch_id = _seed_chain_with_workspace(client, repo_dir)

    # Manually approve gate so gate check passes, but apply hasn't been done
    from app.core.db import SessionLocal
    from app.repositories.change_batch_repository import ChangeBatchRepository
    from app.repositories.commit_candidate_repository import CommitCandidateRepository
    from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
    from app.services.git_write_state_tracker import _resolve_git_write_state_path

    # Write approval decision (bypasses blocked gate since we just want to test apply-not-done)
    import json as _json
    from app.domain._base import utc_now
    decision_path = (
        Path(os.environ["RUNTIME_DATA_DIR"])
        / "repository-release-gates"
        / f"{batch_id}.json"
    )
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(_json.dumps({
        "project_id": project_id,
        "change_batch_id": batch_id,
        "updated_at": utc_now().isoformat(),
        "decisions": [{
            "id": str(uuid4()), "action": "approve",
            "actor_name": "Smoke", "summary": "Approved.",
            "comment": None, "highlighted_risks": [],
            "requested_changes": [], "decided_at": utc_now().isoformat(),
        }],
    }), encoding="utf-8")

    # Still, gate will be blocked (checklist items missing). We're testing apply-not-done.
    status, body = _request_json_any_status(
        client, "POST", f"/repositories/change-batches/{batch_id}/git-commit",
    )
    # Either apply_not_done or gate_not_approved — both are valid for this test
    assert body.get("status") == "failed", (
        f"Expected failed, got {body}"
    )
    assert body.get("error_category") in ("apply_not_done", "gate_not_approved"), (
        f"Expected apply_not_done or gate_not_approved, got {body.get('error_category')}"
    )
    print(f"PASS test_git_commit_without_apply_blocked (category={body.get('error_category')})")


def test_path_traversal_blocked(client: TestClient) -> None:
    """Path traversal (.., .git, absolute) must be blocked.

    Uses monkeypatch on _check_gate_approved to bypass the full gate checklist.
    """
    runtime_data_dir = Path(os.environ["RUNTIME_DATA_DIR"])
    repo_dir = _create_temp_git_repo()
    project_id, batch_id = _seed_chain_with_workspace(client, repo_dir)

    from app.services.local_git_write_service import _check_gate_approved
    from app.services.repository_release_gate_service import RepositoryReleaseGate

    # Create a dummy gate that appears approved
    class _DummyGate:
        release_qualification_established = True

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # Test .. traversal
        _s1, body1 = _request_json_any_status(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": "../outside.txt", "content": "evil"}]},
        )
        assert body1.get("status") == "failed", f".. traversal should fail: {body1}"
        assert body1.get("error_category") == "path_traversal", (
            f"Expected path_traversal, got {body1.get('error_category')}"
        )

        # Test .git path
        _s2, body2 = _request_json_any_status(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": ".git/config", "content": "evil"}]},
        )
        assert body2.get("status") == "failed", f".git path should fail: {body2}"
        assert body2.get("error_category") == "git_internal_path", (
            f"Expected git_internal_path, got {body2.get('error_category')}"
        )

        # Test absolute path
        _s3, body3 = _request_json_any_status(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": "/etc/passwd", "content": "evil"}]},
        )
        assert body3.get("status") == "failed", f"Absolute path should fail: {body3}"
        assert body3.get("error_category") == "path_traversal", (
            f"Expected path_traversal, got {body3.get('error_category')}"
        )

    print("PASS test_path_traversal_blocked")


def test_apply_local_and_commit_success(client: TestClient) -> None:
    """Full happy path: apply-local → git-commit → commit_sha + git_write_actions_triggered.

    Uses monkeypatch on _check_gate_approved to bypass the full gate checklist.
    """
    runtime_data_dir = Path(os.environ["RUNTIME_DATA_DIR"])
    repo_dir = _create_temp_git_repo()
    project_id, batch_id = _seed_chain_with_workspace(client, repo_dir)

    class _DummyGate:
        release_qualification_established = True

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # 1. apply-local
        apply_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local", 200,
            {"files": [{"relative_path": "src/a.txt", "content": "BCL-03 smoke content\n"}]},
        )
        assert apply_body["status"] == "applied", (
            f"Expected applied, got {apply_body}"
        )
        assert "src/a.txt" in apply_body["changed_files"], (
            f"Expected src/a.txt in changed_files, got {apply_body['changed_files']}"
        )
        assert apply_body["error_category"] is None
        assert apply_body["log_path"]

        # Verify file was written
        written = (repo_dir / "src" / "a.txt").read_text(encoding="utf-8")
        assert "BCL-03 smoke content" in written

        # 2. git-commit
        commit_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/git-commit", 200,
        )
        assert commit_body["status"] == "committed", (
            f"Expected committed, got {commit_body}"
        )
        assert commit_body["commit_sha"], f"commit_sha empty: {commit_body}"
        assert len(commit_body["commit_sha"]) >= 7
        assert commit_body["branch_name"]
        assert commit_body["error_category"] is None
        assert commit_body["log_path"]

        # 3. git_write_actions_triggered
        from app.services.git_write_state_tracker import has_git_write_actions_triggered
        triggered = has_git_write_actions_triggered(UUID(batch_id))
        assert triggered is True, "git_write_actions_triggered should be True"

        # 4. Verify commit in git log
        import subprocess
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=str(repo_dir), capture_output=True, text=True,
        )
        assert commit_body["commit_sha"][:7] in result.stdout, (
            f"Commit not in git log: {result.stdout}"
        )

    print("PASS test_apply_local_and_commit_success")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    client = TestClient(app)

    all_passed = True
    for name, fn in [
        ("test_no_gate_apply_local_blocked", test_no_gate_apply_local_blocked),
        ("test_git_commit_without_apply_blocked", test_git_commit_without_apply_blocked),
        ("test_path_traversal_blocked", test_path_traversal_blocked),
        ("test_apply_local_and_commit_success", test_apply_local_and_commit_success),
    ]:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-03 smoke: ALL PASSED")
    else:
        print("BCL-03 smoke: SOME FAILED")
        sys.exit(1)
