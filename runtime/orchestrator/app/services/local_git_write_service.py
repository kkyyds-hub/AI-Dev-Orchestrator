"""BCL-03 Phase 1: Local-safe git write -- apply-local + git-commit.

This service enforces the full Day14 guard chain:
  workspace binding -> change batch -> preflight -> release gate -> commit candidate
before any file is written or any git commit is created.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain._base import utc_now
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchPreflightStatus,
)
from app.domain.commit_candidate import CommitCandidate
from app.domain.repository_workspace import RepositoryWorkspace
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.services.git_write_state_tracker import (
    _load_git_write_state,
    _resolve_git_write_state_path,
    has_git_write_actions_triggered,
)
from app.services.repository_release_gate_service import (
    RepositoryReleaseGate,
    RepositoryReleaseGateService,
)


# -- Error classes ---------------------------------------------------------

class LocalGitWriteError(Exception):
    """Structured error for local git write operations."""

    def __init__(
        self,
        *,
        category: str,
        message: str,
        log_path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.log_path = log_path


# -- Path safety -----------------------------------------------------------

_WINDOWS_ABS_PATTERN = None
try:
    import re as _re
    _WINDOWS_ABS_PATTERN = _re.compile(r"^[a-zA-Z]:\\")
except Exception:
    pass


def _validate_and_resolve_file_path(
    relative_path: str,
    workspace_root: Path,
) -> Path:
    """Validate a file write path and resolve it within the workspace root.

    Rejects: absolute paths, path traversal (..), .git internal paths,
    and paths that resolve outside the workspace root.
    """

    normalized = relative_path.strip().replace("\\", "/")

    if not normalized:
        raise LocalGitWriteError(
            category="invalid_file_path",
            message=f"File path must not be empty.",
        )

    # Reject absolute Unix paths
    if normalized.startswith("/"):
        raise LocalGitWriteError(
            category="path_traversal",
            message=f"Absolute paths are not allowed: {relative_path}",
        )

    # Reject absolute Windows paths
    if _WINDOWS_ABS_PATTERN is not None and _WINDOWS_ABS_PATTERN.match(relative_path.strip()):
        raise LocalGitWriteError(
            category="path_traversal",
            message=f"Absolute paths are not allowed: {relative_path}",
        )

    # Split and reject traversal
    parts: list[str] = []
    for part in normalized.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise LocalGitWriteError(
                category="path_traversal",
                message=f"Path traversal (..) is not allowed: {relative_path}",
            )
        parts.append(part)

    if not parts:
        raise LocalGitWriteError(
            category="invalid_file_path",
            message=f"File path must not be empty after normalization: {relative_path}",
        )

    # Reject .git paths
    if parts[0] == ".git":
        raise LocalGitWriteError(
            category="git_internal_path",
            message=f"Writing to .git directory is forbidden: {relative_path}",
        )

    # Resolve against workspace root
    try:
        full_path = (workspace_root / "/".join(parts)).resolve()
    except Exception as exc:
        raise LocalGitWriteError(
            category="path_resolve_error",
            message=f"Failed to resolve path {relative_path}: {exc}",
        ) from exc

    # Verify the resolved path stays within the workspace root
    try:
        full_path.relative_to(workspace_root.resolve())
    except ValueError:
        raise LocalGitWriteError(
            category="path_outside_workspace",
            message=f"Resolved path is outside workspace: {relative_path} -> {full_path}",
        )

    return full_path


# -- JSONL logging ----------------------------------------------------------

def _append_jsonl(
    log_path: Path,
    entry: dict[str, object],
    *,
    ensure_dir: bool = True,
) -> None:
    """Append one JSON line to a JSONL log file."""
    if ensure_dir:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        json.dump(entry, fh, ensure_ascii=False, default=str)
        fh.write("\n")


# -- Tracking (write side) --------------------------------------------------

def _save_git_write_state(change_batch_id: UUID, state: dict[str, object]) -> None:
    """Persist git-write tracking state."""
    path = _resolve_git_write_state_path(change_batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, default=str), encoding="utf-8")


# -- Gate / preflight / candidate checks -----------------------------------

def _check_gate_approved(
    release_gate_service: RepositoryReleaseGateService,
    change_batch_id: UUID,
) -> RepositoryReleaseGate:
    """Load the release gate and verify it is approved."""
    gate = release_gate_service.get_release_gate(change_batch_id)
    if not gate.release_qualification_established:
        raise LocalGitWriteError(
            category="gate_not_approved",
            message=(
                f"Release gate is not approved for change batch {change_batch_id}. "
                f"Status: {gate.status.value if gate.status else 'blocked'}."
            ),
        )
    return gate


def _check_preflight_passed(preflight_status: str | None, ready_for_execution: bool | None) -> None:
    """Verify preflight status is acceptable."""
    if preflight_status not in {
        ChangeBatchPreflightStatus.READY_FOR_EXECUTION.value,
        ChangeBatchPreflightStatus.MANUAL_CONFIRMED.value,
    } or not ready_for_execution:
        raise LocalGitWriteError(
            category="preflight_not_passed",
            message=(
                f"Preflight has not passed. "
                f"Status: {preflight_status}, ready_for_execution: {ready_for_execution}."
            ),
        )


def _check_commit_candidate_exists(
    commit_candidate_repository: CommitCandidateRepository,
    change_batch_id: UUID,
) -> CommitCandidate:
    """Verify a commit candidate exists for this change batch."""
    candidate = commit_candidate_repository.get_by_change_batch_id(change_batch_id)
    if candidate is None:
        raise LocalGitWriteError(
            category="commit_candidate_missing",
            message=f"No commit candidate found for change batch {change_batch_id}.",
        )
    return candidate


# -- Diff helpers ----------------------------------------------------------

def _compute_file_diff_summary(
    workspace_root: Path,
    files: list[dict[str, str]],
) -> dict[str, list[str]]:
    """Compute a simple diff summary (added / modified) for files-to-write."""
    added: list[str] = []
    modified: list[str] = []
    for entry in files:
        rel = entry["relative_path"]
        full_path = workspace_root / rel
        if full_path.exists():
            modified.append(rel)
        else:
            added.append(rel)
    return {"added": added, "modified": modified}


# -- Verification ----------------------------------------------------------

def _run_verification_commands(
    change_batch: ChangeBatch,
    workspace_root: Path,
) -> dict[str, object]:
    """Run verification commands from change batch plan snapshots.

    Returns: {"passed": bool, "results": [{"command": str, "exit_code": int, "output": str}]}
    """
    results: list[dict[str, object]] = []
    all_passed = True

    for plan_snapshot in change_batch.plan_snapshots:
        for cmd in plan_snapshot.verification_commands:
            cmd_str = str(cmd).strip()
            if not cmd_str:
                continue
            try:
                proc = subprocess.run(
                    cmd_str,
                    cwd=str(workspace_root),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = (proc.stdout[:2000] or "") + (proc.stderr[:2000] or "")
                results.append({
                    "command": cmd_str,
                    "exit_code": proc.returncode,
                    "output": output,
                })
                if proc.returncode != 0:
                    all_passed = False
            except subprocess.TimeoutExpired as exc:
                results.append({
                    "command": cmd_str,
                    "exit_code": -1,
                    "output": f"Command timed out: {exc}",
                })
                all_passed = False
            except Exception as exc:
                results.append({
                    "command": cmd_str,
                    "exit_code": -1,
                    "output": str(exc),
                })
                all_passed = False

    return {"passed": all_passed, "results": results}


# -- Git operations --------------------------------------------------------

def _run_git(
    *args: str,
    cwd: Path,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Run a git command and return (exit_code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return -1, "", "git command not found"
    except subprocess.TimeoutExpired:
        return -1, "", "git command timed out"
    except Exception as exc:
        return -1, "", str(exc)


def _get_current_branch(cwd: Path) -> str:
    """Get the current branch name of the git repo."""
    exit_code, stdout, _stderr = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return stdout if exit_code == 0 and stdout else "unknown"


def _git_status_short(cwd: Path) -> str:
    """Get git status --short output."""
    _ec, stdout, _stderr = _run_git("status", "--short", cwd=cwd)
    return stdout


# -- Service ---------------------------------------------------------------

class LocalGitWriteService:
    """Orchestrate local git writes with full guard-chain enforcement."""

    def __init__(
        self,
        *,
        change_batch_repository: ChangeBatchRepository,
        commit_candidate_repository: CommitCandidateRepository,
        workspace_repository: RepositoryWorkspaceRepository,
        release_gate_service: RepositoryReleaseGateService,
    ) -> None:
        self._change_batch_repository = change_batch_repository
        self._commit_candidate_repository = commit_candidate_repository
        self._workspace_repository = workspace_repository
        self._release_gate_service = release_gate_service

    def apply_local(
        self,
        *,
        change_batch_id: UUID,
        files: list[dict[str, str]],
    ) -> dict[str, object]:
        """Validate the full guard chain, dry-run diff, write files to workspace.

        Args:
            change_batch_id: The change batch to apply.
            files: [{relative_path: str, content: str}] — files to write.

        Returns a dict with keys: status, change_batch_id, changed_files,
        diff_summary, verification_passed, log_path, error_category, error_summary.
        """
        log_path = _resolve_git_write_state_path(change_batch_id).parent / "apply-local.jsonl"

        try:
            # 1. Load change batch
            batch = self._change_batch_repository.get_by_id(change_batch_id)
            if batch is None:
                raise LocalGitWriteError(
                    category="change_batch_not_found",
                    message=f"Change batch {change_batch_id} not found.",
                )

            # 2. Load workspace (via project_id — the workspace repository
            #    maps project -> workspace, not by workspace UUID)
            workspace: RepositoryWorkspace | None = (
                self._workspace_repository.get_by_project_id(batch.project_id)
            )
            if workspace is None:
                raise LocalGitWriteError(
                    category="workspace_not_bound",
                    message="No repository workspace bound for this change batch.",
                )

            workspace_root = Path(workspace.root_path).resolve()
            if not workspace_root.exists() or not (workspace_root / ".git").exists():
                raise LocalGitWriteError(
                    category="workspace_invalid",
                    message=f"Workspace root {workspace_root} does not exist or is not a git repo.",
                )

            # 3. Check preflight (before gate so the error category is precise)
            preflight = batch.preflight
            if preflight is None:
                raise LocalGitWriteError(
                    category="preflight_not_passed",
                    message="No preflight data on change batch.",
                )
            _check_preflight_passed(
                preflight.status.value if preflight.status else None,
                preflight.ready_for_execution,
            )

            # 4. Check commit candidate (before gate so the error category is precise)
            candidate = _check_commit_candidate_exists(
                self._commit_candidate_repository, change_batch_id
            )

            # 5. Check release gate (last pre-write guard; gate must still approve before any file is written)
            gate = _check_gate_approved(self._release_gate_service, change_batch_id)

            # 6. Validate file paths — safety checks
            validated: list[tuple[str, Path, str]] = []  # (rel_path, full_path, content)
            for entry in files:
                rel_path = str(entry.get("relative_path", "") or "")
                content = str(entry.get("content", "") or "")
                full_path = _validate_and_resolve_file_path(rel_path, workspace_root)
                validated.append((rel_path, full_path, content))

            # 7. Dry-run diff
            diff = _compute_file_diff_summary(workspace_root, files)
            changed_files = sorted(set(diff["added"] + diff["modified"]))

            # 8. Write files
            for rel_path, full_path, content in validated:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")

            # 9. Run verification
            verification = _run_verification_commands(batch, workspace_root)
            verification_passed = bool(verification["passed"])

            # 10. Record apply state
            #     Files are always written (best-effort), but the status
            #     reflects whether verification passed so git_commit can gate.
            apply_status = (
                "applied" if verification_passed else "applied_with_failed_verification"
            )
            result: dict[str, object] = {
                "status": apply_status,
                "change_batch_id": str(change_batch_id),
                "applied_at": utc_now().isoformat(),
                "changed_files": changed_files,
                "diff_summary": {
                    "added_files": diff["added"],
                    "modified_files": diff["modified"],
                },
                "verification_passed": verification_passed,
                "verification_results": verification["results"],
                "log_path": str(log_path),
                "error_category": None,
                "error_summary": None,
                "rollback_performed": False,
                "rollback_reason": "Rollback not implemented in BCL-03 Phase 1.",
            }
            _save_git_write_state(change_batch_id, {
                "apply_local": result,
                "git_write_actions_triggered": False,
            })
            _append_jsonl(log_path, result)
            return result

        except LocalGitWriteError as exc:
            error_result: dict[str, object] = {
                "status": "failed",
                "change_batch_id": str(change_batch_id),
                "changed_files": [],
                "diff_summary": {},
                "verification_passed": False,
                "log_path": str(log_path),
                "error_category": exc.category,
                "error_summary": exc.message,
                "rollback_performed": False,
                "rollback_reason": "Rollback not implemented in BCL-03 Phase 1.",
            }
            _append_jsonl(log_path, error_result)
            return error_result

    def git_commit(
        self,
        *,
        change_batch_id: UUID,
    ) -> dict[str, object]:
        """Stage only apply-local files and create a local git commit.

        Requires a prior apply_local with status=applied AND verification_passed=true.
        Only stages files from apply_result.changed_files (not unrelated dirty files).
        """
        log_path = _resolve_git_write_state_path(change_batch_id).parent / "git-commit.jsonl"

        try:
            # Verify prior apply
            prior_state = _load_git_write_state(change_batch_id)
            if prior_state is None:
                raise LocalGitWriteError(
                    category="apply_not_done",
                    message="apply-local must be called successfully before git-commit.",
                )
            apply_result = prior_state.get("apply_local")
            if not isinstance(apply_result, dict):
                raise LocalGitWriteError(
                    category="apply_not_done",
                    message="apply-local result is missing or corrupted.",
                )

            apply_status = str(apply_result.get("status", ""))
            verification_passed = bool(apply_result.get("verification_passed", False))

            # Require apply status = "applied" (not "applied_with_failed_verification")
            if apply_status != "applied":
                raise LocalGitWriteError(
                    category="apply_verification_failed",
                    message=(
                        f"apply-local status is '{apply_status}', "
                        f"verification_passed={verification_passed}. "
                        "Commit is blocked until verification passes."
                    ),
                )

            # 1. Load change batch
            batch = self._change_batch_repository.get_by_id(change_batch_id)
            if batch is None:
                raise LocalGitWriteError(
                    category="change_batch_not_found",
                    message=f"Change batch {change_batch_id} not found.",
                )

            # 2. Load workspace (via project_id)
            workspace: RepositoryWorkspace | None = (
                self._workspace_repository.get_by_project_id(batch.project_id)
            )
            if workspace is None:
                raise LocalGitWriteError(
                    category="workspace_not_bound",
                    message="No repository workspace bound.",
                )

            workspace_root = Path(workspace.root_path).resolve()

            # 3. Re-check preflight (before gate so error category is precise)
            preflight_object = batch.preflight
            if preflight_object is None:
                raise LocalGitWriteError(
                    category="preflight_not_passed",
                    message="No preflight data.",
                )
            _check_preflight_passed(
                preflight_object.status.value if preflight_object.status else None,
                preflight_object.ready_for_execution,
            )

            # 4. Re-check commit candidate (before gate so error category is precise)
            candidate = _check_commit_candidate_exists(
                self._commit_candidate_repository, change_batch_id
            )

            # 5. Re-check gate
            _check_gate_approved(self._release_gate_service, change_batch_id)

            # 6. Get changed files from apply, re-validate every path
            changed_files_raw = apply_result.get("changed_files")
            if isinstance(changed_files_raw, list):
                changed_files_list = [str(f) for f in changed_files_raw]
            else:
                changed_files_list = []

            if not changed_files_list:
                raise LocalGitWriteError(
                    category="no_changes_to_commit",
                    message="apply-local changed_files is empty; nothing to commit.",
                )

            # Re-validate every changed file path against the workspace
            for rel_path in changed_files_list:
                _validate_and_resolve_file_path(rel_path, workspace_root)

            # 7. Clear any pre-staged files, then stage ONLY the apply-local
            #    changed_files.  This prevents unrelated staged files from
            #    leaking into the commit.
            branch = _get_current_branch(workspace_root)

            # 7a. Reset index to HEAD to discard any pre-staged files.
            exit_code, _stdout, stderr = _run_git(
                "reset", "--", ".", cwd=workspace_root
            )
            if exit_code != 0:
                raise LocalGitWriteError(
                    category="git_reset_failed",
                    message=f"git reset failed: {stderr}",
                )

            # 7b. Stage only the apply-local files.
            for rel_path in changed_files_list:
                exit_code, _stdout, stderr = _run_git(
                    "add", "--", rel_path, cwd=workspace_root
                )
                if exit_code != 0:
                    raise LocalGitWriteError(
                        category="git_add_failed",
                        message=f"git add {rel_path} failed: {stderr}",
                    )

            # 7c. Verify staged files match apply-local changed_files exactly.
            exit_code, staged_output, _stderr = _run_git(
                "diff", "--cached", "--name-only", cwd=workspace_root
            )
            if exit_code != 0:
                raise LocalGitWriteError(
                    category="staged_files_check_failed",
                    message="Failed to read staged file list.",
                )
            staged_files = {f.strip() for f in staged_output.splitlines() if f.strip()}
            expected_files = set(changed_files_list)

            extra = staged_files - expected_files
            missing = expected_files - staged_files
            if extra or missing:
                raise LocalGitWriteError(
                    category="staged_files_mismatch",
                    message=(
                        f"Staged files do not match apply-local changed_files. "
                        f"Extra: {sorted(extra)}, Missing: {sorted(missing)}"
                    ),
                )

            # 8. Get commit message from candidate
            versions = candidate.versions
            if versions:
                latest_version = versions[-1]
                commit_title = latest_version.message_title or "Apply changes"
                commit_body = latest_version.message_body or ""
                message = commit_title
                if commit_body:
                    message = f"{commit_title}\n\n{commit_body}"
            else:
                message = "Apply local changes (BCL-03)"

            # 9. Create commit (only previously-staged files are included)
            exit_code, _stdout, stderr = _run_git(
                "commit", "-m", message, cwd=workspace_root, timeout=60
            )
            if exit_code != 0:
                raise LocalGitWriteError(
                    category="git_commit_failed",
                    message=f"git commit failed: {stderr}",
                )

            # 10. Get commit SHA
            exit_code, commit_sha, _stderr = _run_git(
                "rev-parse", "HEAD", cwd=workspace_root
            )
            if exit_code != 0 or not commit_sha:
                commit_sha = "unknown"

            # 11. Record git write triggered
            state = prior_state.copy() if isinstance(prior_state, dict) else {}
            state["git_commit"] = {
                "status": "committed",
                "commit_sha": commit_sha,
                "branch_name": branch,
                "committed_at": utc_now().isoformat(),
            }
            state["git_write_actions_triggered"] = True
            _save_git_write_state(change_batch_id, state)

            # 12. Return result
            result: dict[str, object] = {
                "status": "committed",
                "change_batch_id": str(change_batch_id),
                "commit_sha": commit_sha,
                "branch_name": branch,
                "changed_files": changed_files_list,
                "log_path": str(log_path),
                "error_category": None,
                "error_summary": None,
                "committed_at": utc_now().isoformat(),
            }
            _append_jsonl(log_path, result)
            return result

        except LocalGitWriteError as exc:
            error_result: dict[str, object] = {
                "status": "failed",
                "change_batch_id": str(change_batch_id),
                "commit_sha": None,
                "branch_name": None,
                "changed_files": [],
                "log_path": str(log_path),
                "error_category": exc.category,
                "error_summary": exc.message,
            }
            _append_jsonl(log_path, error_result)
            return error_result
