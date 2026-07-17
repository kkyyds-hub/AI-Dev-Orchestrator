"""P25-G real candidate manifest and exact-base diff integration checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.db_tables import RunTable, TaskTable
from app.services.project_director_bounded_rework_candidate_diff_service import (
    P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
    P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT,
)
from tests.p25_candidate_diff_real_chain_test_support import (
    build_fresh_candidate_diff_services,
    build_real_p25_attempt_zero_candidate_diff_context,
)
from tests.p25_outcome_real_chain_test_support import (
    RaisingBoundedReworkExecutor,
    RecordingBoundedReworkExecutor,
)


def _execute_outcome(context):
    return context.outcome_context.outcome_service.execute_bounded_rework_from_reservation(
        session_id=context.session_id,
        source_task_id=context.task_id,
        source_reservation_message_id=(
            context.outcome_context.claim_context.reservation_result.message.id
        ),
    )


def _regenerate(context, outcome_message_id, *, service=None):
    return (service or context.candidate_diff_service).regenerate_candidate_manifest_and_diff(
        session_id=context.session_id,
        source_task_id=context.task_id,
        source_outcome_message_id=outcome_message_id,
    )


def _manifest_path(context) -> Path:
    return context.environment["workspace_path"] / ".ai-project-director/workspace-manifest.json"


def _business_entries(context):
    workspace = context.environment["workspace_path"]
    return tuple(
        sorted(
            (
                path.relative_to(workspace).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in workspace.rglob("*")
            if path.is_file() and ".ai-project-director" not in path.parts
        )
    )


def _git_control_fingerprint(repository: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((repository / ".git").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(repository).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _task_run_counts(session):
    caller_had_transaction = session.in_transaction()
    try:
        return (
            session.scalar(select(func.count()).select_from(TaskTable)),
            session.scalar(select(func.count()).select_from(RunTable)),
        )
    finally:
        if not caller_had_transaction and session.in_transaction():
            session.rollback()


def _p25g_messages(context, *, session=None):
    repository = context.outcome_context.claim_context.package_context.msg_repo
    if session is not None:
        repository = type(repository)(session)
    caller_had_transaction = repository._session.in_transaction()
    try:
        messages, has_more = repository.list_by_session_id(
            session_id=context.session_id, limit=200
        )
        assert has_more is False
        return tuple(
            message
            for message in messages
            if message.intent
            in {
                P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT,
                P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT,
            }
        )
    finally:
        if not caller_had_transaction and repository._session.in_transaction():
            repository._session.rollback()


def _assert_one_manifest_and_diff(messages):
    manifests = [
        message
        for message in messages
        if message.intent == P25_BOUNDED_REWORK_CANDIDATE_MANIFEST_INTENT
    ]
    diffs = [
        message
        for message in messages
        if message.intent == P25_BOUNDED_REWORK_CANDIDATE_DIFF_INTENT
    ]
    assert len(manifests) == 1
    assert len(diffs) == 1
    return manifests[0], diffs[0]


def test_real_attempt_zero_generates_candidate_manifest_and_diff(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.status == "outcome_recorded", outcome_result.blocked_reasons
        assert outcome_result.outcome is not None
        assert outcome_result.claim is not None
        assert outcome_result.outcome_message is not None

        result = _regenerate(context, outcome_result.outcome_message.id)

        assert result.status == "candidate_diff_generated", result.blocked_reasons
        assert result.blocked_reasons == ()
        assert result.candidate_manifest is not None
        assert result.candidate_diff is not None
        assert result.manifest_message is not None
        assert result.diff_message is not None
        manifest, diff = result.candidate_manifest, result.candidate_diff
        package = context.outcome_context.claim_context.package_result.package
        reservation = context.outcome_context.claim_context.reservation_result.reservation
        assert manifest.candidate_manifest_id == outcome_result.outcome.candidate_manifest_id
        assert manifest.candidate_manifest_fingerprint == outcome_result.outcome.candidate_manifest_fingerprint
        assert manifest.source_outcome_id == outcome_result.outcome.outcome_id
        assert manifest.source_claim_id == outcome_result.claim.claim_id
        assert manifest.source_reservation_id == reservation.reservation_id
        assert manifest.source_package_id == package.package_id
        assert manifest.exact_task_id == context.task_id
        assert manifest.exact_run_id == context.outcome_context.claim_context.package_context.run_id
        assert (manifest.rework_attempt_index, manifest.rework_attempt_limit) == (0, 3)
        assert len(manifest.changed_files) == 1
        assert manifest.changed_files[0].relative_path == "src/example.py"
        assert diff.diff_status == "generated"
        assert diff.non_convergence_reason is None
        assert diff.source_outcome_id == outcome_result.outcome.outcome_id
        assert diff.source_claim_id == outcome_result.claim.claim_id
        assert diff.source_reservation_id == reservation.reservation_id
        assert diff.source_package_id == package.package_id
        assert diff.candidate_manifest_id == manifest.candidate_manifest_id
        assert diff.candidate_manifest_fingerprint == manifest.candidate_manifest_fingerprint
        assert diff.previous_diff_message_id == package.source_candidate_diff_message_id
        assert diff.previous_diff_sha256 == package.source_candidate_diff_sha256
        assert diff.new_diff_sha256 == hashlib.sha256(
            diff.unified_diff_text.encode("utf-8")
        ).hexdigest()
        assert diff.new_diff_sha256 != diff.previous_diff_sha256
        assert diff.base_commit_sha == package.base_commit_sha
        assert diff.base_snapshot_fingerprint == package.base_snapshot_fingerprint
        assert diff.base_content_source == "exact_git_commit_object"
        assert diff.readonly_base_snapshot_verified is True
        assert diff.scope_paths == ("src/example.py",)
        assert diff.diff_file_count == 1
        assert len(diff.diff_entries) == 1
        assert diff.unified_diff_text
        _assert_one_manifest_and_diff(_p25g_messages(context))
    finally:
        context.close()


def test_candidate_manifest_updates_only_internal_control_projection(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        manifest_path = _manifest_path(context)
        before_business = _business_entries(context)
        before_files = tuple(sorted(path.relative_to(context.environment["workspace_path"]).as_posix() for path in context.environment["workspace_path"].rglob("*")))
        before_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        result = _regenerate(context, outcome_result.outcome_message.id)

        assert result.status == "candidate_diff_generated", result.blocked_reasons
        assert result.candidate_manifest is not None
        after_business = _business_entries(context)
        after_files = tuple(sorted(path.relative_to(context.environment["workspace_path"]).as_posix() for path in context.environment["workspace_path"].rglob("*")))
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert before_business == after_business
        assert before_files == after_files
        projection = result.candidate_manifest.model_dump(
            mode="json", exclude={"internal_manifest_content_sha256"}
        )
        assert payload["p25_bounded_rework_candidate"] == projection
        assert {
            key: value
            for key, value in payload.items()
            if key != "p25_bounded_rework_candidate"
        } == before_payload
        assert result.candidate_manifest.internal_manifest_content_sha256 == hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
    finally:
        context.close()


def test_candidate_diff_generation_performs_no_git_write(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        repository = context.environment["repository_root"]
        before = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _git_control_fingerprint(repository),
            subprocess.run(["git", "branch", "--format=%(refname)"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "tag", "--list"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _task_run_counts(context.session),
        )

        result = _regenerate(context, outcome_result.outcome_message.id)

        after = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _git_control_fingerprint(repository),
            subprocess.run(["git", "branch", "--format=%(refname)"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "tag", "--list"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            _task_run_counts(context.session),
        )
        assert result.status == "candidate_diff_generated", result.blocked_reasons
        assert before == after
        assert result.manifest_message is not None
        assert result.diff_message is not None
        false_boundaries = {
            "product_runtime_git_write_allowed=false",
            "main_project_write_allowed=false",
            "patch_apply_allowed=false",
            "git_add_allowed=false",
            "git_commit_allowed=false",
            "git_push_allowed=false",
            "branch_operation_allowed=false",
            "pull_request_allowed=false",
            "merge_allowed=false",
            "ci_trigger_allowed=false",
            "reviewer_called=false",
            "task_created=false",
            "run_created=false",
        }
        assert set(result.manifest_message.forbidden_actions_detected) == false_boundaries
        assert set(result.diff_message.forbidden_actions_detected) == false_boundaries
    finally:
        context.close()


def test_same_session_candidate_diff_replays_exactly(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        first = _regenerate(context, outcome_result.outcome_message.id)
        assert first.status == "candidate_diff_generated", first.blocked_reasons
        manifest_path = _manifest_path(context)
        before = (manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns)

        second = _regenerate(context, outcome_result.outcome_message.id)

        assert second.status == "candidate_diff_replayed", second.blocked_reasons
        assert second.candidate_manifest == first.candidate_manifest
        assert second.candidate_diff == first.candidate_diff
        assert second.manifest_message == first.manifest_message
        assert second.diff_message == first.diff_message
        assert before == (manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns)
        _assert_one_manifest_and_diff(_p25g_messages(context))
    finally:
        context.close()


def test_fresh_session_candidate_diff_replays_without_reexecution(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    fresh = None
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        first = _regenerate(context, outcome_result.outcome_message.id)
        assert first.status == "candidate_diff_generated", first.blocked_reasons
        manifest_path = _manifest_path(context)
        before = manifest_path.read_bytes()
        context.session.close()
        fresh = build_fresh_candidate_diff_services(context)

        replay = _regenerate(
            context, outcome_result.outcome_message.id, service=fresh.candidate_diff_service
        )

        assert replay.status == "candidate_diff_replayed", replay.blocked_reasons
        assert replay.candidate_manifest == first.candidate_manifest
        assert replay.candidate_diff == first.candidate_diff
        assert replay.manifest_message == first.manifest_message
        assert replay.diff_message == first.diff_message
        assert manifest_path.read_bytes() == before
        assert isinstance(context.outcome_context.executor, RecordingBoundedReworkExecutor)
        assert context.outcome_context.executor.call_count == 1
        assert fresh.session.in_transaction() is False
    finally:
        if fresh is not None:
            fresh.close()
        context.close()


def test_candidate_diff_does_not_rollback_caller_owned_transaction(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        assert context.session.in_transaction() is False
        manifest_path = _manifest_path(context)
        before = (manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns)

        context.session.begin()
        task = context.session.get(TaskTable, context.task_id)
        assert task is not None
        task.input_summary = "caller-owned P25-G pending write"
        context.session.flush()
        result = _regenerate(context, outcome_result.outcome_message.id)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("history_invalid",)
        assert context.session.in_transaction() is True
        assert context.session.execute(select(TaskTable.input_summary).where(TaskTable.id == context.task_id)).scalar_one() == "caller-owned P25-G pending write"
        assert before == (manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns)
        assert _p25g_messages(context) == ()
    finally:
        if context.session.in_transaction():
            context.session.rollback()
        context.close()


def test_raised_outcome_does_not_enter_candidate_diff(tmp_path):
    executor = RaisingBoundedReworkExecutor(session=None)
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path, executor=executor)
    try:
        executor.session = context.session
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome is not None
        assert outcome_result.outcome_message is not None
        assert outcome_result.outcome.outcome_status == "raised"
        assert outcome_result.outcome.recovery_required is True
        manifest_path = _manifest_path(context)
        before = manifest_path.read_bytes()
        business_before = _business_entries(context)

        result = _regenerate(context, outcome_result.outcome_message.id)

        assert result.status == "blocked"
        assert result.candidate_manifest is None
        assert result.candidate_diff is None
        assert _p25g_messages(context) == ()
        assert manifest_path.read_bytes() == before
        assert _business_entries(context) == business_before
    finally:
        context.close()


def test_workspace_drift_after_outcome_fails_closed(tmp_path):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        manifest_path = _manifest_path(context)
        before = manifest_path.read_bytes()
        repository = context.environment["repository_root"]
        repository_before = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
        )
        (context.environment["workspace_path"] / "src/example.py").write_text("workspace drift\n", encoding="utf-8")

        result = _regenerate(context, outcome_result.outcome_message.id)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("workspace_invalid",)
        assert _p25g_messages(context) == ()
        assert manifest_path.read_bytes() == before
        assert repository_before == (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
        )
    finally:
        context.close()


def test_candidate_diff_persistence_failure_restores_internal_manifest(tmp_path, monkeypatch):
    context = build_real_p25_attempt_zero_candidate_diff_context(tmp_path)
    try:
        outcome_result = _execute_outcome(context)
        assert outcome_result.outcome_message is not None
        manifest_path = _manifest_path(context)
        before = manifest_path.read_bytes()
        business_before = _business_entries(context)
        repository = context.environment["repository_root"]
        repository_before = (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
        )
        repository_obj = context.outcome_context.claim_context.package_context.msg_repo
        original_create = repository_obj.create
        calls = 0

        def fail_on_diff_message(message):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SQLAlchemyError("injected diff message persistence failure")
            return original_create(message)

        monkeypatch.setattr(repository_obj, "create", fail_on_diff_message)
        result = _regenerate(context, outcome_result.outcome_message.id)

        assert result.status == "blocked"
        assert result.blocked_reasons == ("persistence_failed",)
        assert calls == 2
        assert _p25g_messages(context) == ()
        assert manifest_path.read_bytes() == before
        assert _business_entries(context) == business_before
        assert repository_before == (
            subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout,
            subprocess.run(["git", "status", "--porcelain"], cwd=repository, check=True, capture_output=True, text=True).stdout,
        )
        assert not list(manifest_path.parent.glob("*.tmp"))
    finally:
        context.close()
