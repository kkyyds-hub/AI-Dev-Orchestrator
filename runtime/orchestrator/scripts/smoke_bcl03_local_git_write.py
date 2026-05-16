"""BCL-03 rework smoke: local git write with full guard + content discipline.

Covers:
1.  Gate not approved → apply-local blocked.
2.  Preflight not passed → apply-local blocked.
3.  Commit candidate missing → apply-local blocked.
4.  Path traversal / .git / absolute → blocked.
5.  Verification failure → apply returns applied_with_failed_verification,
    git-commit blocked with apply_verification_failed.
6.  Unrelated dirty file NOT included in commit.
7.  Success path: apply-local + git-commit → commit_sha + git_write_actions_triggered.  #
    The success path monkeypatches gate approval because constructing a fully
    approved Day14 release gate requires extensive seed data (change plans,
    verification runs, diff evidence, etc.).  All other guard layers
    (workspace, preflight, commit candidate, path safety, verification,
    git discipline) are exercised through real code paths.
8.  git_write_actions_triggered=true readable from release gate path.
"""

from __future__ import annotations

import json as _json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from _smoke_runtime_env import prepare_runtime_data_dir

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_RUNTIME_DATA_DIR = RUNTIME_ROOT / "tmp" / "v5-bcl03-git-write-rework-smoke"

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


def _request_json_any(
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
    import tempfile
    repos_root = RUNTIME_ROOT.parents[1] / "tmp" / "bcl03-repos"
    repos_root.mkdir(parents=True, exist_ok=True)
    repo_dir = Path(tempfile.mkdtemp(dir=str(repos_root), prefix="bcl03-repo-"))
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "smoke@bcl03.local"],
        cwd=str(repo_dir), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "BCL-03 Rework"],
        cwd=str(repo_dir), check=True, capture_output=True,
    )
    (repo_dir / "README.md").write_text("# BCL-03 Rework Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True, capture_output=True)
    return repo_dir


def utc_now_safe() -> datetime:
    import datetime as _dt
    return _dt.datetime.now(_dt.UTC) + _dt.timedelta(seconds=5)


# -- Seed: basic chain ----------------------------------------------------

def _seed_chain(
    client: TestClient,
    repo_dir: Path,
    *,
    preflight_status: str = "ready_for_execution",
    preflight_ready: bool = True,
    include_candidate: bool = True,
    verification_cmd: str = "echo ok",
) -> tuple[str, str]:  # (project_id, change_batch_id)
    """Create project + workspace + change_batch + optional commit_candidate.

    Args:
        preflight_status: ChangeBatchPreflightStatus value.
        preflight_ready: ready_for_execution flag.
        include_candidate: If False, skip commit candidate creation.
        verification_cmd: Verification command (use falsy cmd to trigger failure).
    """
    from app.core.db import SessionLocal
    from app.core.db_tables import RepositorySnapshotTable
    from app.repositories.change_batch_repository import ChangeBatchRepository
    from app.repositories.commit_candidate_repository import CommitCandidateRepository
    from app.repositories.repository_workspace_repository import (
        RepositoryWorkspaceRepository,
    )
    from app.domain.change_batch import (
        ChangeBatch, ChangeBatchPlanSnapshot, ChangeBatchPreflight,
        ChangeBatchPreflightStatus, ChangeBatchStatus,
    )
    from app.domain.commit_candidate import (
        CommitCandidate, CommitCandidateStatus, CommitCandidateVersion,
        CommitCandidateVerificationSummary,
    )
    from app.domain.change_plan import ChangePlanTargetFile

    project = _request_json(
        client, "POST", "/projects", 201,
        {"name": "BCL-03 Rework", "summary": "Rework smoke test."},
    )
    project_id = project["id"]

    _request_json(
        client, "PUT", f"/repositories/projects/{project_id}", 200,
        {"root_path": str(repo_dir), "display_name": "BCL-03 Rework Repo",
         "access_mode": "read_only"},
    )

    session = SessionLocal()
    try:
        ws = RepositoryWorkspaceRepository(session).get_by_project_id(UUID(project_id))
        assert ws is not None

        _now = utc_now_safe()
        snap_obj = RepositorySnapshotTable(
            id=uuid4(), project_id=UUID(project_id),
            repository_workspace_id=ws.id,
            repository_root_path=str(repo_dir),
            status="success", directory_count=2, file_count=3,
            scanned_at=_now, created_at=_now, updated_at=_now,
        )
        session.add(snap_obj)
        session.flush()

        def _plan(title: str, task_title: str, path: str) -> ChangeBatchPlanSnapshot:
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
                verification_commands=[verification_cmd],
            )

        preflight = ChangeBatchPreflight(
            status=ChangeBatchPreflightStatus(preflight_status),
            blocked=(not preflight_ready),
            ready_for_execution=preflight_ready,
            findings=[], finding_count=0,
            manual_confirmation_required=False,
        )
        batch = ChangeBatch(
            id=uuid4(), project_id=UUID(project_id),
            repository_workspace_id=ws.id,
            status=ChangeBatchStatus.PREPARING,
            title="BCL-03 Rework Batch", summary="Rework smoke batch.",
            plan_snapshots=[
                _plan("Plan A", "Task A", "src/a.txt"),
                _plan("Plan B", "Task B", "src/b.txt"),
            ],
            preflight=preflight,
        )
        ChangeBatchRepository(session).create(batch)
        change_batch_id = str(batch.id)

        if include_candidate:
            cand_id = uuid4()
            version = CommitCandidateVersion(
                id=uuid4(), commit_candidate_id=cand_id, version_number=1,
                message_title="BCL-03 rework commit",
                message_body="Rework smoke commit body.",
                impact_scope=["src"],
                related_files=["src/a.txt", "src/b.txt"],
                verification_summary=CommitCandidateVerificationSummary(
                    total_runs=1, passed_runs=1, failed_runs=0, skipped_runs=0,
                    highlights=["All passed"],
                ),
                evidence_summary="Rework evidence.",
                evidence_package_key="rework-evidence",
            )
            candidate = CommitCandidate(
                id=cand_id, project_id=UUID(project_id),
                change_batch_id=batch.id, change_batch_title="BCL-03 Rework Batch",
                status=CommitCandidateStatus.DRAFT,
                current_version_number=1, versions=[version],
            )
            CommitCandidateRepository(session).create(candidate)

        session.commit()
    finally:
        session.close()

    return project_id, change_batch_id


class _DummyGate:
    release_qualification_established = True


# -- Tests ---------------------------------------------------------------

def test_gate_not_approved_blocked(client: TestClient) -> None:
    """apply-local must be blocked when release gate is not approved (real gate path)."""
    repo_dir = _create_temp_git_repo()
    _pid, batch_id = _seed_chain(client, repo_dir)

    _s, body = _request_json_any(
        client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
        {"files": [{"relative_path": "test.txt", "content": "hello"}]},
    )
    assert body.get("status") == "failed", f"Expected failed, got {body}"
    assert body.get("error_category") == "gate_not_approved", (
        f"Expected gate_not_approved, got {body.get('error_category')}"
    )
    print("PASS test_gate_not_approved_blocked")


def test_preflight_not_passed_blocked(client: TestClient) -> None:
    """apply-local blocked when preflight is not ready_for_execution."""
    repo_dir = _create_temp_git_repo()
    _pid, batch_id = _seed_chain(
        client, repo_dir,
        preflight_status="not_started",
        preflight_ready=False,
    )

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        _s, body = _request_json_any(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": "test.txt", "content": "hello"}]},
        )
        assert body.get("status") == "failed", f"Expected failed, got {body}"
        assert body.get("error_category") == "preflight_not_passed", (
            f"Expected preflight_not_passed, got {body.get('error_category')}"
        )
    print("PASS test_preflight_not_passed_blocked")


def test_commit_candidate_missing_blocked(client: TestClient) -> None:
    """apply-local blocked when no commit candidate exists for the batch."""
    repo_dir = _create_temp_git_repo()
    _pid, batch_id = _seed_chain(client, repo_dir, include_candidate=False)

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        _s, body = _request_json_any(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": "test.txt", "content": "hello"}]},
        )
        assert body.get("status") == "failed", f"Expected failed, got {body}"
        assert body.get("error_category") == "commit_candidate_missing", (
            f"Expected commit_candidate_missing, got {body.get('error_category')}"
        )
    print("PASS test_commit_candidate_missing_blocked")


def test_path_traversal_blocked(client: TestClient) -> None:
    """.., .git, and absolute paths must be blocked."""
    repo_dir = _create_temp_git_repo()
    _pid, batch_id = _seed_chain(client, repo_dir)

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # .. traversal
        _s1, body1 = _request_json_any(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": "../evil.txt", "content": "x"}]},
        )
        assert body1.get("error_category") == "path_traversal", (
            f"Expected path_traversal, got {body1.get('error_category')}"
        )

        # .git
        _s2, body2 = _request_json_any(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": ".git/config", "content": "x"}]},
        )
        assert body2.get("error_category") == "git_internal_path", (
            f"Expected git_internal_path, got {body2.get('error_category')}"
        )

        # Absolute
        _s3, body3 = _request_json_any(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local",
            {"files": [{"relative_path": "/etc/shadow", "content": "x"}]},
        )
        assert body3.get("error_category") == "path_traversal", (
            f"Expected path_traversal, got {body3.get('error_category')}"
        )
    print("PASS test_path_traversal_blocked")


def test_verification_failure_blocks_commit(client: TestClient) -> None:
    """Verification failure → apply status=applied_with_failed_verification → commit blocked."""
    repo_dir = _create_temp_git_repo()
    _pid, batch_id = _seed_chain(
        client, repo_dir,
        verification_cmd="exit 1",  # deliberate failure
    )

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # apply-local
        apply_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local", 200,
            {"files": [{"relative_path": "src/a.txt", "content": "hello\n"}]},
        )
        assert apply_body["status"] == "applied_with_failed_verification", (
            f"Expected applied_with_failed_verification, got {apply_body['status']}"
        )
        assert apply_body["verification_passed"] is False
        assert apply_body["rollback_performed"] is False

        # git-commit must be blocked
        _s, commit_body = _request_json_any(
            client, "POST", f"/repositories/change-batches/{batch_id}/git-commit",
        )
        assert commit_body.get("status") == "failed", (
            f"Expected failed, got {commit_body}"
        )
        assert commit_body.get("error_category") == "apply_verification_failed", (
            f"Expected apply_verification_failed, got {commit_body.get('error_category')}"
        )
    print("PASS test_verification_failure_blocks_commit")


def test_unrelated_dirty_file_not_committed(client: TestClient) -> None:
    """Files not in apply-local changed_files must NOT enter the commit."""
    repo_dir = _create_temp_git_repo()

    # Pre-create an unrelated dirty file
    unrelated = repo_dir / "unrelated_dirty.txt"
    unrelated.write_text("this should not be committed\n", encoding="utf-8")

    _pid, batch_id = _seed_chain(client, repo_dir)

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # apply-local writes src/a.txt only
        apply_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local", 200,
            {"files": [{"relative_path": "src/a.txt", "content": "committed content\n"}]},
        )
        assert apply_body["status"] == "applied"

        commit_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/git-commit", 200,
        )
        assert commit_body["status"] == "committed"
        assert commit_body["commit_sha"]

        # Verify the commit contains src/a.txt but NOT unrelated_dirty.txt
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", commit_body["commit_sha"]],
            cwd=str(repo_dir), capture_output=True, text=True,
        )
        committed_files = result.stdout.strip().splitlines()
        committed_files = [f.strip() for f in committed_files if f.strip()]

        assert "src/a.txt" in committed_files, (
            f"Expected src/a.txt in commit, got {committed_files}"
        )
        assert "unrelated_dirty.txt" not in committed_files, (
            f"unrelated_dirty.txt must NOT be in commit, got {committed_files}"
        )
    print("PASS test_unrelated_dirty_file_not_committed")


def test_pre_staged_unrelated_file_not_committed(client: TestClient) -> None:
    """Pre-staged files in the git index must NOT leak into the commit.

    git_commit executes 'git reset -- .' before staging, which clears the
    index of any unrelated pre-staged files.  This test verifies that a file
    that was explicitly staged before apply-local is NOT included in the commit.
    """
    repo_dir = _create_temp_git_repo()

    # Pre-create and STAGE an unrelated file
    unrelated_staged = repo_dir / "unrelated_staged.txt"
    unrelated_staged.write_text("this was staged before apply\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "unrelated_staged.txt"],
        cwd=str(repo_dir), check=True, capture_output=True,
    )

    # Verify it IS staged
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo_dir), capture_output=True, text=True,
    )
    staged_before = result.stdout.strip().splitlines()
    assert "unrelated_staged.txt" in staged_before, (
        f"unrelated_staged.txt should be staged before test, got {staged_before}"
    )

    _pid, batch_id = _seed_chain(client, repo_dir)

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # apply-local writes only src/a.txt
        apply_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local", 200,
            {"files": [{"relative_path": "src/a.txt", "content": "committed content\n"}]},
        )
        assert apply_body["status"] == "applied"

        commit_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/git-commit", 200,
        )
        assert commit_body["status"] == "committed"
        assert commit_body["commit_sha"]

        # The commit must contain src/a.txt but NOT unrelated_staged.txt
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "-r", "--name-only",
             commit_body["commit_sha"]],
            cwd=str(repo_dir), capture_output=True, text=True,
        )
        committed_files = {f.strip() for f in result.stdout.strip().splitlines() if f.strip()}

        assert "src/a.txt" in committed_files, (
            f"src/a.txt must be in commit, got {committed_files}"
        )
        assert "unrelated_staged.txt" not in committed_files, (
            f"unrelated_staged.txt must NOT be in commit (was pre-staged before apply), "
            f"got {committed_files}"
        )
    print("PASS test_pre_staged_unrelated_file_not_committed")


def test_success_path(client: TestClient) -> None:
    """Happy path: apply-local → git-commit → commit_sha + git_write_actions_triggered.

    Gate approval is monkeypatched because a fully-approved Day14 release gate
    requires extensive seed data (change plans, verification runs, diff evidence,
    etc.).  Every other guard — workspace, preflight, commit candidate, path
    safety, verification, and git discipline — is exercised through real code.
    """
    repo_dir = _create_temp_git_repo()
    _pid, batch_id = _seed_chain(client, repo_dir)

    with patch(
        "app.services.local_git_write_service._check_gate_approved",
        return_value=_DummyGate(),
    ):
        # 1. apply-local
        apply_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/apply-local", 200,
            {"files": [{"relative_path": "src/a.txt", "content": "success content\n"}]},
        )
        assert apply_body["status"] == "applied", f"Expected applied, got {apply_body}"
        assert apply_body["verification_passed"] is True
        assert "src/a.txt" in apply_body["changed_files"]
        assert apply_body["error_category"] is None
        assert apply_body["log_path"]

        # File was written
        assert (repo_dir / "src" / "a.txt").read_text(encoding="utf-8") == "success content\n"

        # 2. git-commit
        commit_body = _request_json(
            client, "POST", f"/repositories/change-batches/{batch_id}/git-commit", 200,
        )
        assert commit_body["status"] == "committed", f"Expected committed, got {commit_body}"
        assert commit_body["commit_sha"]
        assert len(commit_body["commit_sha"]) >= 7
        assert commit_body["branch_name"]
        assert commit_body["error_category"] is None
        assert commit_body["log_path"]

        # 3. git_write_actions_triggered
        from app.services.git_write_state_tracker import has_git_write_actions_triggered
        assert has_git_write_actions_triggered(UUID(batch_id)) is True

        # 4. Commit is real in git log
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=str(repo_dir), capture_output=True, text=True,
        )
        assert commit_body["commit_sha"][:7] in result.stdout

    print("PASS test_success_path")


# -- Harness -------------------------------------------------------------

if __name__ == "__main__":
    _prepare_env()

    from app.core.db import init_database
    from app.main import create_application

    init_database()
    app = create_application()
    client = TestClient(app)

    all_passed = True
    tests = [
        ("test_gate_not_approved_blocked", test_gate_not_approved_blocked),
        ("test_preflight_not_passed_blocked", test_preflight_not_passed_blocked),
        ("test_commit_candidate_missing_blocked", test_commit_candidate_missing_blocked),
        ("test_path_traversal_blocked", test_path_traversal_blocked),
        ("test_verification_failure_blocks_commit", test_verification_failure_blocks_commit),
        ("test_unrelated_dirty_file_not_committed", test_unrelated_dirty_file_not_committed),
        ("test_pre_staged_unrelated_file_not_committed", test_pre_staged_unrelated_file_not_committed),
        ("test_success_path", test_success_path),
    ]
    for name, fn in tests:
        try:
            fn(client)
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    if all_passed:
        print("BCL-03 smoke (rework): ALL PASSED")
    else:
        print("BCL-03 smoke (rework): SOME FAILED")
        sys.exit(1)
