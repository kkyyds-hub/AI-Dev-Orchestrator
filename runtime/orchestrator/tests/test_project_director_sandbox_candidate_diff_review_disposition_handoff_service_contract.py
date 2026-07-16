"""Contract tests for P21-D-C3 disposition handoff & bounded rework budget."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db_tables import (
    ORMBase,
    ProjectDirectorMessageTable,
    ProjectDirectorSessionTable,
    ProjectTable,
    TaskTable,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_handoff_service import (
    DISPOSITION_HANDOFF_SCHEMA_VERSION,
    MAX_AUTOMATIC_REWORK_HANDOFFS_PER_REVIEW_LINEAGE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
    PreparedSandboxCandidateDiffReviewDispositionHandoff,
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)

# ── Constants ───────────────────────────────────────────────────────

SESSION_ID = uuid4()
TASK_ID = uuid4()
PROJECT_ID = uuid4()

_C2_FALSE_FLAGS = [
    "continuation_started",
    "rework_started",
    "human_escalation_package_created",
    "human_decision_recorded",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
    "gate_allows_write",
]

_HANDOFF_FALSE_FLAGS = list(_C2_FALSE_FLAGS)


# ── Test database helpers ───────────────────────────────────────────


def _make_test_engine(db_path: str):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    ORMBase.metadata.create_all(bind=engine)
    return engine


def _make_session_factory(engine):
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


# ── Seed helpers ────────────────────────────────────────────────────


def _seed_base_records(session: Session) -> None:
    session.add(
        ProjectTable(
            id=PROJECT_ID,
            name="Test",
            summary="Test project",
            status="active",
            stage="intake",
        )
    )
    session.flush()
    acceptance = json.dumps(
        [
            "safe_dry_run_task=true",
            "worker_simulate_required=true",
            "product_runtime_git_write_allowed=false",
            "native_executor_started=false",
            "codex_started=false",
            "claude_code_started=false",
        ]
    )
    session.add(
        TaskTable(
            id=TASK_ID,
            project_id=PROJECT_ID,
            title="Test task",
            status="pending",
            priority="normal",
            input_summary="SAFE DRY-RUN TASK DISPATCH ONLY",
            risk_level="normal",
            human_status="none",
            source_draft_id="p12-test-draft",
            acceptance_criteria=acceptance,
        )
    )
    session.add(
        ProjectDirectorSessionTable(
            id=SESSION_ID,
            project_id=PROJECT_ID,
            goal_text="Test goal",
            constraints="",
            status="confirmed",
        )
    )
    session.commit()


def _seed_c2_consumed_message(
    session: Session,
    *,
    source_task_id: UUID = TASK_ID,
    disposition_type: str = "AUTO_CONTINUE",
    consumption_id: UUID | None = None,
    c2_msg_id: UUID | None = None,
    seq_no: int = 100,
    source_review_message_id: UUID | None = None,
    source_disposition_message_id: UUID | None = None,
    source_diff_message_id: UUID | None = None,
    disposition_id: UUID | None = None,
    review_result_fingerprint: str | None = None,
) -> tuple[UUID, UUID]:
    consumption_id = consumption_id or uuid4()
    c2_msg_id = c2_msg_id or uuid4()
    review_fingerprint_sha = review_result_fingerprint or "a" * 64
    diff_sha = "b" * 64
    review_prompt_sha = "c" * 64
    scope = ["src/example.py"]
    action: dict[str, Any] = {
        "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
        "schema_version": DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
        "consumption_status": "consumed",
        "consumption_id": str(consumption_id),
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        "session_id": str(SESSION_ID),
        "source_task_id": str(source_task_id),
        "source_consumption_preflight_message_id": str(uuid4()),
        "source_disposition_message_id": str(source_disposition_message_id or uuid4()),
        "source_review_message_id": str(source_review_message_id or uuid4()),
        "source_diff_message_id": str(source_diff_message_id or uuid4()),
        "disposition_id": str(disposition_id or uuid4()),
        "disposition_type": disposition_type,
        "disposition_reason": (
            "review_has_no_blocking_findings"
            if disposition_type == "AUTO_CONTINUE"
            else "review_changes_required_within_automatic_rework_boundary"
        ),
        "review_result_fingerprint": review_fingerprint_sha,
        "revalidated_review_result_fingerprint": review_fingerprint_sha,
        "reviewed_diff_sha256": diff_sha,
        "persisted_source_diff_sha256": diff_sha,
        "current_diff_sha256": diff_sha,
        "review_prompt_sha256": review_prompt_sha,
        "reviewed_scope_paths": list(scope),
        "persisted_source_scope_paths": list(scope),
        "current_scope_paths": list(scope),
        "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "source_review_verdict": (
            "no_blocking_findings"
            if disposition_type == "AUTO_CONTINUE"
            else "changes_required"
        ),
        "source_review_risk_level": "low",
        "workspace_path": "/tmp/ws",
        "workspace_path_within_root": True,
        "source_diff_revalidated": True,
        "current_diff_regenerated": True,
        "evidence_fresh": True,
        "disposition_consumed": True,
        "continuation_eligible": disposition_type == "AUTO_CONTINUE",
        "rework_eligible": disposition_type == "AUTO_REWORK",
        "replay_check_completed": True,
        "prior_consumption_detected": False,
        "blocked_reasons": [],
        "ai_project_director_total_loop": "Partial",
    }
    for flag in _C2_FALSE_FLAGS:
        action[flag] = False
    session.add(
        ProjectDirectorMessageTable(
            id=c2_msg_id,
            session_id=SESSION_ID,
            role="assistant",
            content="Consumption recorded.",
            sequence_no=seq_no,
            source="system",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=source_task_id,
        )
    )
    session.commit()
    return c2_msg_id, consumption_id


def _seed_filler_messages(
    session: Session, start_seq: int, count: int = 105
) -> None:
    for i in range(count):
        session.add(
            ProjectDirectorMessageTable(
                id=uuid4(),
                session_id=SESSION_ID,
                role="user",
                content=f"filler-{i}",
                sequence_no=start_seq + i,
                source="system",
                source_detail="filler",
                suggested_actions_json="[]",
                requires_confirmation=False,
                risk_level="low",
                related_project_id=PROJECT_ID,
                related_task_id=TASK_ID,
            )
        )
    session.commit()


def _c3_prepare_handoff(
    SessionLocal,
    c2_msg_id: UUID,
    *,
    source_task_id: UUID = TASK_ID,
) -> tuple[UUID, int]:
    svc, session = _make_c3_service(SessionLocal)
    result = svc.prepare_candidate_diff_review_disposition_handoff(
        session_id=SESSION_ID,
        source_task_id=source_task_id,
        source_message_id=c2_msg_id,
    )
    assert result.result.handoff_status == "prepared"
    assert result.message is not None
    handoff_msg_id = result.message.id
    handoff_seq_no = result.message.sequence_no
    session.close()
    return handoff_msg_id, handoff_seq_no


# ── Service helper ──────────────────────────────────────────────────


def _make_c3_service(session_local):
    session = session_local()
    msg_repo = ProjectDirectorMessageRepository(session)
    sess_repo = ProjectDirectorSessionRepository(session)
    task_repo = TaskRepository(session)
    svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    return svc, session


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = _make_test_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_session(db_engine):
    SessionLocal = _make_session_factory(db_engine)
    session = SessionLocal()
    _seed_base_records(session)
    c2_msg_id, _ = _seed_c2_consumed_message(session)
    session.close()
    return SessionLocal, c2_msg_id


# ══════════════════════════════════════════════════════════════════════
# 1. TestConstants
# ══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_handoff_source_detail(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
            == "p21_d_sandbox_candidate_diff_review_disposition_handoff_prepared"
        )

    def test_handoff_action_type(self) -> None:
        assert (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE
            == "p21_d_sandbox_candidate_diff_review_disposition_handoff_record"
        )

    def test_disposition_handoff_schema_version(self) -> None:
        assert DISPOSITION_HANDOFF_SCHEMA_VERSION == "p21-d-c3.v1"

    def test_max_automatic_rework_handoffs_per_review_lineage(self) -> None:
        assert MAX_AUTOMATIC_REWORK_HANDOFFS_PER_REVIEW_LINEAGE == 1


# ══════════════════════════════════════════════════════════════════════
# 2. TestPublicSignature
# ══════════════════════════════════════════════════════════════════════


class TestPublicSignature:
    def test_method_signature(self) -> None:
        import inspect

        sig = inspect.signature(
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService.prepare_candidate_diff_review_disposition_handoff
        )
        params = list(sig.parameters.keys())
        assert params == ["self", "session_id", "source_task_id", "source_message_id"]

    def test_constructor_signature(self) -> None:
        import inspect

        sig = inspect.signature(
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService.__init__
        )
        params = [p for p in sig.parameters.keys() if p != "self"]
        assert set(params) == {
            "session_repository",
            "message_repository",
            "task_repository",
        }


# ══════════════════════════════════════════════════════════════════════
# 3. TestDomainBlockedContract
# ══════════════════════════════════════════════════════════════════════


class TestDomainBlockedContract:
    def test_blocked_requires_reasons(self) -> None:
        with pytest.raises(ValueError, match="blocked handoff requires a reason"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                blocked_reasons=[],
            )

    def test_blocked_no_handoff_id(self) -> None:
        with pytest.raises(ValueError, match="blocked handoff may not be prepared"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                handoff_id=uuid4(),
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_prepared_at(self) -> None:
        with pytest.raises(ValueError, match="blocked handoff may not be prepared"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                prepared_at=datetime.now(timezone.utc),
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_handoff_kind(self) -> None:
        with pytest.raises(
            ValueError, match="blocked handoff may not expose a handoff kind"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                handoff_kind="automatic_continuation",
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_continuation_prepared(self) -> None:
        with pytest.raises(
            ValueError, match="blocked handoff may not expose prepared work"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                continuation_handoff_prepared=True,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_no_rework_prepared(self) -> None:
        with pytest.raises(
            ValueError, match="blocked handoff may not expose prepared work"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                rework_handoff_prepared=True,
                blocked_reasons=["some_reason"],
            )

    def test_blocked_replay_requires_flag(self) -> None:
        with pytest.raises(
            ValueError, match="blocked handoff replay contract is invalid"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                prior_handoff_detected=False,
                replay_check_completed=True,
                blocked_reasons=["handoff_already_prepared"],
            )

    def test_blocked_replay_flag_requires_reason(self) -> None:
        with pytest.raises(
            ValueError, match="blocked handoff replay contract is invalid"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                prior_handoff_detected=True,
                replay_check_completed=True,
                blocked_reasons=["other_reason"],
            )

    def test_blocked_replay_check_completed(self) -> None:
        with pytest.raises(
            ValueError, match="blocked handoff replay check must be complete"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                prior_handoff_detected=True,
                replay_check_completed=False,
                blocked_reasons=["handoff_already_prepared"],
            )

    def test_blocked_budget_exhaustion_requires_non_convergence(self) -> None:
        with pytest.raises(
            ValueError, match="rework budget exhaustion requires non-convergence"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                bounded_rework_budget_exhausted=True,
                rework_non_convergence_detected=False,
                replay_check_completed=True,
                blocked_reasons=["other"],
            )

    def test_blocked_budget_requires_prior_handoff(self) -> None:
        with pytest.raises(
            ValueError, match="rework budget exhaustion requires a prior handoff"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                bounded_rework_budget_exhausted=True,
                rework_non_convergence_detected=True,
                prior_rework_handoff_count=0,
                replay_check_completed=True,
                blocked_reasons=["other"],
            )

    def test_blocked_budget_reasons_must_match_flags(self) -> None:
        with pytest.raises(
            ValueError, match="rework budget reasons and flags must match"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
                handoff_status="blocked",
                source_consumption_message_id=uuid4(),
                bounded_rework_budget_exhausted=False,
                rework_non_convergence_detected=False,
                replay_check_completed=True,
                blocked_reasons=[
                    "bounded_rework_budget_exhausted",
                    "rework_non_convergence",
                ],
            )

    def test_blocked_valid(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
            handoff_status="blocked",
            source_consumption_message_id=uuid4(),
            replay_check_completed=True,
            blocked_reasons=["session_missing"],
        )
        assert result.handoff_status == "blocked"
        assert result.blocked_reasons == ["session_missing"]


# ══════════════════════════════════════════════════════════════════════
# 4. TestDomainPreparedContract
# ══════════════════════════════════════════════════════════════════════


def _valid_prepared_kwargs(
    *,
    disposition_type: str = "AUTO_CONTINUE",
) -> dict[str, Any]:
    sha = hashlib.sha256(b"valid").hexdigest()
    now = datetime.now(timezone.utc)
    is_continue = disposition_type == "AUTO_CONTINUE"
    return dict(
        handoff_status="prepared",
        handoff_id=uuid4(),
        source_consumption_message_id=uuid4(),
        source_consumption_id=uuid4(),
        source_consumption_preflight_message_id=uuid4(),
        source_disposition_message_id=uuid4(),
        source_review_message_id=uuid4(),
        source_diff_message_id=uuid4(),
        disposition_id=uuid4(),
        disposition_type=disposition_type,
        disposition_reason="review_has_no_blocking_findings" if is_continue else "review_changes_required_within_automatic_rework_boundary",
        handoff_kind="automatic_continuation" if is_continue else "bounded_automatic_rework",
        review_result_fingerprint=sha,
        revalidated_review_result_fingerprint=sha,
        reviewed_diff_sha256=sha,
        persisted_source_diff_sha256=sha,
        current_diff_sha256=sha,
        review_prompt_sha256=sha,
        reviewed_scope_paths=["src/x.py"],
        persisted_source_scope_paths=["src/x.py"],
        current_scope_paths=["src/x.py"],
        workspace_path="/tmp/ws",
        workspace_path_within_root=True,
        source_consumption_validated=True,
        replay_check_completed=True,
        prior_handoff_detected=False,
        prior_rework_handoff_count=0 if is_continue else 0,
        rework_attempt_number=0 if is_continue else 1,
        rework_attempt_limit=1,
        continuation_handoff_prepared=is_continue,
        rework_handoff_prepared=not is_continue,
        prepared_at=now,
    )


class TestDomainPreparedContract:
    def test_valid_auto_continue(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
            **_valid_prepared_kwargs(disposition_type="AUTO_CONTINUE")
        )
        assert result.handoff_status == "prepared"
        assert result.handoff_kind == "automatic_continuation"
        assert result.continuation_handoff_prepared is True
        assert result.rework_handoff_prepared is False

    def test_valid_auto_rework(self) -> None:
        result = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
            **_valid_prepared_kwargs(disposition_type="AUTO_REWORK")
        )
        assert result.handoff_status == "prepared"
        assert result.handoff_kind == "bounded_automatic_rework"
        assert result.continuation_handoff_prepared is False
        assert result.rework_handoff_prepared is True

    def test_prepared_requires_ids(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["handoff_id"] = None
        with pytest.raises(
            ValueError, match="prepared handoff requires complete evidence bindings"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    @pytest.mark.parametrize(
        "field",
        [
            "source_consumption_id",
            "source_consumption_preflight_message_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_diff_message_id",
            "disposition_id",
        ],
    )
    def test_prepared_requires_id_field(self, field: str) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs[field] = None
        with pytest.raises(
            ValueError, match="prepared handoff requires complete evidence bindings"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_auto_type(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["disposition_type"] = None
        with pytest.raises(
            ValueError, match="prepared handoff requires an automatic disposition"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_reason(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["disposition_reason"] = ""
        with pytest.raises(
            ValueError, match="prepared handoff requires a disposition reason"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_valid_sha(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["review_result_fingerprint"] = "invalid"
        with pytest.raises(
            ValueError, match="prepared handoff requires valid fingerprints"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_matching_fingerprints(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["revalidated_review_result_fingerprint"] = "b" * 64
        with pytest.raises(
            ValueError, match="prepared handoff requires matching review fingerprints"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_matching_diff_shas(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["persisted_source_diff_sha256"] = "b" * 64
        with pytest.raises(
            ValueError, match="prepared handoff requires matching diff fingerprints"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_scopes(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["reviewed_scope_paths"] = []
        with pytest.raises(
            ValueError, match="prepared handoff requires matching ordered scopes"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_scope_match(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["current_scope_paths"] = ["src/other.py"]
        with pytest.raises(
            ValueError, match="prepared handoff requires matching ordered scopes"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_workspace(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["workspace_path"] = ""
        with pytest.raises(
            ValueError, match="prepared handoff requires a trusted workspace"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_workspace_within_root(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["workspace_path_within_root"] = False
        with pytest.raises(
            ValueError, match="prepared handoff requires a trusted workspace"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_validated_consumption(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["source_consumption_validated"] = False
        with pytest.raises(
            ValueError,
            match="prepared handoff requires validated unreplayed consumption",
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_replay_check(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["replay_check_completed"] = False
        with pytest.raises(
            ValueError,
            match="prepared handoff requires validated unreplayed consumption",
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_rejects_prior_handoff(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["prior_handoff_detected"] = True
        with pytest.raises(
            ValueError,
            match="prepared handoff requires validated unreplayed consumption",
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_rejects_budget_exhausted(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["bounded_rework_budget_exhausted"] = True
        with pytest.raises(
            ValueError, match="prepared handoff may not be blocked"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_rejects_blocked_reasons(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["blocked_reasons"] = ["stale"]
        with pytest.raises(
            ValueError, match="prepared handoff may not be blocked"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_requires_timezone(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["prepared_at"] = datetime(2025, 1, 1)
        with pytest.raises(
            ValueError,
            match="prepared handoff requires a timezone-aware timestamp",
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_auto_continue_mapping(self) -> None:
        kwargs = _valid_prepared_kwargs(disposition_type="AUTO_CONTINUE")
        kwargs["rework_attempt_number"] = 1
        with pytest.raises(
            ValueError, match="automatic continuation handoff mapping is invalid"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_prepared_auto_rework_mapping(self) -> None:
        kwargs = _valid_prepared_kwargs(disposition_type="AUTO_REWORK")
        kwargs["prior_rework_handoff_count"] = 1
        with pytest.raises(
            ValueError, match="bounded automatic rework handoff mapping is invalid"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_rework_attempt_limit_must_be_one(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["rework_attempt_limit"] = 2
        with pytest.raises(
            ValueError, match="disposition handoff rework limit must remain one"
        ):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 5. TestFalseOnlyFlags
# ══════════════════════════════════════════════════════════════════════


class TestFalseOnlyFlags:
    @pytest.mark.parametrize("flag", _HANDOFF_FALSE_FLAGS)
    def test_forbidden_side_effect_flag_rejected(self, flag: str) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs[flag] = True
        with pytest.raises(ValueError, match="disposition handoff may not"):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)

    def test_total_loop_must_be_partial(self) -> None:
        kwargs = _valid_prepared_kwargs()
        kwargs["ai_project_director_total_loop"] = "Full"
        with pytest.raises(ValueError):
            ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(**kwargs)


# ══════════════════════════════════════════════════════════════════════
# 6. TestDependenciesAndTransaction
# ══════════════════════════════════════════════════════════════════════


class TestDependenciesAndTransaction:
    def test_missing_session_repository(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
            session_repository=None,
            message_repository=msg_repo,
            task_repository=task_repo,
        )
        with pytest.raises(ValueError, match="disposition handoff dependencies"):
            svc.prepare_candidate_diff_review_disposition_handoff(
                session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
            )
        session.close()

    def test_missing_message_repository(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        sess_repo = ProjectDirectorSessionRepository(session)
        task_repo = TaskRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
            session_repository=sess_repo,
            message_repository=None,
            task_repository=task_repo,
        )
        with pytest.raises(ValueError, match="disposition handoff dependencies"):
            svc.prepare_candidate_diff_review_disposition_handoff(
                session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
            )
        session.close()

    def test_missing_task_repository(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()
        session = SessionLocal()
        msg_repo = ProjectDirectorMessageRepository(session)
        sess_repo = ProjectDirectorSessionRepository(session)
        svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
            session_repository=sess_repo,
            message_repository=msg_repo,
            task_repository=None,
        )
        with pytest.raises(ValueError, match="disposition handoff dependencies"):
            svc.prepare_candidate_diff_review_disposition_handoff(
                session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
            )
        session.close()

    def test_blocked_return_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
        )
        assert result.result.handoff_status == "blocked"
        assert result.message is None
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 7. TestSourceC2MessageValidation
# ══════════════════════════════════════════════════════════════════════


class TestSourceC2MessageValidation:
    def test_missing_message(self, seeded_session) -> None:
        SessionLocal, _ = seeded_session
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=uuid4()
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_missing" in result.result.blocked_reasons
        session.close()

    def test_session_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)

        foreign_session_id = uuid4()
        session.add(
            ProjectDirectorSessionTable(
                id=foreign_session_id,
                project_id=PROJECT_ID,
                goal_text="Foreign session",
                constraints="",
                status="confirmed",
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, c2_msg_id)
        row.session_id = foreign_session_id
        session.commit()
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_session_mismatch" in result.result.blocked_reasons
        session.close()

    def test_task_mismatch(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)

        foreign_task_id = uuid4()
        acceptance = json.dumps(["safe_dry_run_task=true"])
        session.add(
            TaskTable(
                id=foreign_task_id,
                project_id=PROJECT_ID,
                title="Foreign task",
                status="pending",
                priority="normal",
                input_summary="FOREIGN TASK",
                risk_level="normal",
                human_status="none",
                source_draft_id="p12-foreign",
                acceptance_criteria=acceptance,
            )
        )
        session.flush()
        row = session.get(ProjectDirectorMessageTable, c2_msg_id)
        row.related_task_id = foreign_task_id
        session.commit()
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_task_mismatch" in result.result.blocked_reasons
        session.close()

    def test_wrong_role(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        row.role = "user"
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_source_invalid" in result.result.blocked_reasons
        session.close()

    def test_wrong_source(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        row.source = "ai"
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_source_invalid" in result.result.blocked_reasons
        session.close()

    def test_confirmation_not_false(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        row.requires_confirmation = True
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_confirmation_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_wrong_risk_level(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        row.risk_level = "low"
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_risk_invalid" in result.result.blocked_reasons
        session.close()

    def test_wrong_source_detail(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        row.source_detail = "wrong_detail"
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_message_is_not_p21_d_c2_consumption" in result.result.blocked_reasons
        session.close()

    def test_empty_actions(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        row.suggested_actions_json = "[]"
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "p21_d_c2_consumption_record_missing" in result.result.blocked_reasons
        session.close()

    def test_two_actions(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        actions = json.loads(row.suggested_actions_json)
        row.suggested_actions_json = json.dumps([actions[0], actions[0]])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "p21_d_c2_consumption_record_missing" in result.result.blocked_reasons
        session.close()

    def test_wrong_action_type(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["type"] = "wrong_type"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "p21_d_c2_consumption_record_missing" in result.result.blocked_reasons
        session.close()



# ══════════════════════════════════════════════════════════════════════
# 8. TestC2SchemaAndBinding
# ══════════════════════════════════════════════════════════════════════


class TestC2SchemaAndBinding:
    def test_wrong_schema_version(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["schema_version"] = "wrong-version"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_schema_version_mismatch" in result.result.blocked_reasons
        session.close()

    def test_session_binding_mismatch(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["session_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_binding_invalid" in result.result.blocked_reasons
        session.close()

    def test_task_binding_mismatch(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_task_id"] = str(uuid4())
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_binding_invalid" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 9. TestC2UuidAndFingerprint
# ══════════════════════════════════════════════════════════════════════


class TestC2UuidAndFingerprint:
    @pytest.mark.parametrize(
        "field",
        [
            "consumption_id",
            "source_consumption_preflight_message_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_diff_message_id",
            "disposition_id",
        ],
    )
    def test_invalid_uuid_field(self, seeded_session, field: str) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action[field] = "not-a-uuid"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_binding_invalid" in result.result.blocked_reasons
        session.close()

    @pytest.mark.parametrize(
        "field",
        [
            "review_result_fingerprint",
            "revalidated_review_result_fingerprint",
            "reviewed_diff_sha256",
            "persisted_source_diff_sha256",
            "current_diff_sha256",
            "review_prompt_sha256",
        ],
    )
    def test_invalid_sha_field(self, seeded_session, field: str) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action[field] = "not_a_sha"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_fingerprint_invalid" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 10. TestC2DomainReconstruction
# ══════════════════════════════════════════════════════════════════════


class TestC2DomainReconstruction:
    def test_invalid_consumption_status(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["consumption_status"] = "invalid_status"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_invalid_disposition_type(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["disposition_type"] = "INVALID_TYPE"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_missing_workspace_path(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["workspace_path"] = ""
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_workspace_outside_root(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["workspace_path_within_root"] = False
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_empty_scopes(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["reviewed_scope_paths"] = []
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_scope_mismatch(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["current_scope_paths"] = ["src/other.py"]
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_diff_sha_mismatch(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["current_diff_sha256"] = "f" * 64
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_fingerprint_mismatch(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["revalidated_review_result_fingerprint"] = "b" * 64
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_consumption_not_consumed(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["consumption_status"] = "blocked"
        action["blocked_reasons"] = ["some_reason"]
        action["evidence_fresh"] = False
        action["continuation_eligible"] = False
        action["rework_eligible"] = False
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        session.close()

    def test_evidence_not_fresh(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["evidence_fresh"] = False
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_prior_consumption_detected(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["prior_consumption_detected"] = True
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_replay_not_completed(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["replay_check_completed"] = False
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_contract_invalid" in result.result.blocked_reasons
        session.close()

    def test_invalid_review_verdict(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_review_verdict"] = "invalid_verdict"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_binding_invalid" in result.result.blocked_reasons
        session.close()

    def test_invalid_risk_level(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["source_review_risk_level"] = "invalid"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_binding_invalid" in result.result.blocked_reasons
        session.close()

    def test_empty_disposition_reason(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["disposition_reason"] = ""
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_binding_invalid" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 11. TestC2NoWriteBoundary
# ══════════════════════════════════════════════════════════════════════


class TestC2NoWriteBoundary:
    @pytest.mark.parametrize("flag", _C2_FALSE_FLAGS)
    def test_c2_flag_set_true_blocks(self, seeded_session, flag: str) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action[flag] = True
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_write_boundary_violated" in result.result.blocked_reasons
        session.close()

    def test_c2_total_loop_not_partial(self, seeded_session) -> None:
        SessionLocal, c2_msg_id = seeded_session
        sess = SessionLocal()
        row = sess.get(ProjectDirectorMessageTable, c2_msg_id)
        action = json.loads(row.suggested_actions_json)[0]
        action["ai_project_director_total_loop"] = "Full"
        row.suggested_actions_json = json.dumps([action])
        sess.commit()
        sess.close()
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=c2_msg_id
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_write_boundary_violated" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 12. TestAutoContinueSuccess
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueSuccess:
    def test_auto_continue_prepared(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, consumption_id = _seed_c2_consumed_message(
            session, disposition_type="AUTO_CONTINUE"
        )
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        assert result.result.disposition_type == "AUTO_CONTINUE"
        assert result.result.handoff_kind == "automatic_continuation"
        assert result.result.continuation_handoff_prepared is True
        assert result.result.rework_handoff_prepared is False
        assert result.result.rework_attempt_number == 0
        assert result.result.source_consumption_validated is True
        assert result.result.replay_check_completed is True
        assert result.result.prior_handoff_detected is False
        assert result.result.blocked_reasons == []
        assert result.result.bounded_rework_budget_exhausted is False
        assert result.result.rework_non_convergence_detected is False
        assert result.message is not None
        assert result.message.source_detail == (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
        )
        session.close()

    def test_auto_continue_result_fields(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, consumption_id = _seed_c2_consumed_message(
            session, disposition_type="AUTO_CONTINUE"
        )
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        r = result.result
        assert r.source_consumption_message_id == c2_msg_id
        assert r.source_consumption_id == consumption_id
        assert r.handoff_id is not None
        assert UUID(str(r.handoff_id))
        assert r.prepared_at is not None
        assert r.prepared_at.tzinfo is not None
        assert r.disposition_reason == "review_has_no_blocking_findings"
        assert r.workspace_path == "/tmp/ws"
        assert r.workspace_path_within_root is True
        assert r.replay_check_completed is True
        assert r.prior_handoff_detected is False
        assert r.rework_attempt_limit == MAX_AUTOMATIC_REWORK_HANDOFFS_PER_REVIEW_LINEAGE
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 13. TestAutoReworkSuccess
# ══════════════════════════════════════════════════════════════════════


class TestAutoReworkSuccess:
    def test_auto_rework_prepared(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, consumption_id = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK"
        )
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        assert result.result.disposition_type == "AUTO_REWORK"
        assert result.result.handoff_kind == "bounded_automatic_rework"
        assert result.result.continuation_handoff_prepared is False
        assert result.result.rework_handoff_prepared is True
        assert result.result.rework_attempt_number == 1
        assert result.result.rework_attempt_limit == 1
        assert result.result.prior_rework_handoff_count == 0
        assert result.result.bounded_rework_budget_exhausted is False
        assert result.result.disposition_reason == (
            "review_changes_required_within_automatic_rework_boundary"
        )
        assert result.message is not None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 14. TestAppendOnlyPersistence
# ══════════════════════════════════════════════════════════════════════


class TestAppendOnlyPersistence:
    def test_old_records_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        pre_sess = SessionLocal()
        c2_row_before = pre_sess.get(ProjectDirectorMessageTable, c2_msg_id)
        c2_snapshot = {
            "id": str(c2_row_before.id),
            "session_id": str(c2_row_before.session_id),
            "role": c2_row_before.role,
            "content": c2_row_before.content,
            "sequence_no": c2_row_before.sequence_no,
            "intent": c2_row_before.intent,
            "source": c2_row_before.source,
            "source_detail": c2_row_before.source_detail,
            "suggested_actions_json": c2_row_before.suggested_actions_json,
            "requires_confirmation": c2_row_before.requires_confirmation,
            "risk_level": c2_row_before.risk_level,
            "related_project_id": str(c2_row_before.related_project_id),
            "related_task_id": str(c2_row_before.related_task_id),
            "forbidden_actions_detected_json": c2_row_before.forbidden_actions_detected_json,
            "created_at": c2_row_before.created_at,
        }
        pre_sess.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

        post_sess = SessionLocal()
        c2_row_after = post_sess.get(ProjectDirectorMessageTable, c2_msg_id)
        assert str(c2_row_after.id) == c2_snapshot["id"]
        assert str(c2_row_after.session_id) == c2_snapshot["session_id"]
        assert c2_row_after.role == c2_snapshot["role"]
        assert c2_row_after.content == c2_snapshot["content"]
        assert c2_row_after.sequence_no == c2_snapshot["sequence_no"]
        assert c2_row_after.intent == c2_snapshot["intent"]
        assert c2_row_after.source == c2_snapshot["source"]
        assert c2_row_after.source_detail == c2_snapshot["source_detail"]
        assert c2_row_after.suggested_actions_json == c2_snapshot["suggested_actions_json"]
        assert c2_row_after.requires_confirmation == c2_snapshot["requires_confirmation"]
        assert c2_row_after.risk_level == c2_snapshot["risk_level"]
        assert str(c2_row_after.related_project_id) == c2_snapshot["related_project_id"]
        assert str(c2_row_after.related_task_id) == c2_snapshot["related_task_id"]
        assert c2_row_after.forbidden_actions_detected_json == c2_snapshot["forbidden_actions_detected_json"]
        assert c2_row_after.created_at == c2_snapshot["created_at"]
        post_sess.close()

    def test_task_and_session_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        pre_sess = SessionLocal()
        task_before = pre_sess.get(TaskTable, TASK_ID)
        task_snapshot = {
            "id": str(task_before.id),
            "project_id": str(task_before.project_id),
            "title": task_before.title,
            "status": task_before.status,
            "priority": task_before.priority,
            "input_summary": task_before.input_summary,
            "risk_level": task_before.risk_level,
            "human_status": task_before.human_status,
            "source_draft_id": task_before.source_draft_id,
            "acceptance_criteria": task_before.acceptance_criteria,
        }
        sess_before = pre_sess.get(ProjectDirectorSessionTable, SESSION_ID)
        sess_snapshot = {
            "id": str(sess_before.id),
            "project_id": str(sess_before.project_id),
            "goal_text": sess_before.goal_text,
            "constraints": sess_before.constraints,
            "status": sess_before.status,
        }
        pre_sess.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

        post_sess = SessionLocal()
        task_after = post_sess.get(TaskTable, TASK_ID)
        assert str(task_after.id) == task_snapshot["id"]
        assert str(task_after.project_id) == task_snapshot["project_id"]
        assert task_after.title == task_snapshot["title"]
        assert task_after.status == task_snapshot["status"]
        assert task_after.priority == task_snapshot["priority"]
        assert task_after.input_summary == task_snapshot["input_summary"]
        assert task_after.risk_level == task_snapshot["risk_level"]
        assert task_after.human_status == task_snapshot["human_status"]
        assert task_after.source_draft_id == task_snapshot["source_draft_id"]
        assert task_after.acceptance_criteria == task_snapshot["acceptance_criteria"]

        sess_after = post_sess.get(ProjectDirectorSessionTable, SESSION_ID)
        assert str(sess_after.id) == sess_snapshot["id"]
        assert str(sess_after.project_id) == sess_snapshot["project_id"]
        assert sess_after.goal_text == sess_snapshot["goal_text"]
        assert sess_after.constraints == sess_snapshot["constraints"]
        assert sess_after.status == sess_snapshot["status"]
        post_sess.close()

    def test_handoff_action_complete(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, consumption_id = _seed_c2_consumed_message(session)

        c2_row = session.get(ProjectDirectorMessageTable, c2_msg_id)
        source_action = copy.deepcopy(json.loads(c2_row.suggested_actions_json)[0])
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.message is not None
        action = result.message.suggested_actions[0]

        assert action["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE
        assert action["schema_version"] == DISPOSITION_HANDOFF_SCHEMA_VERSION
        assert action["handoff_status"] == "prepared"
        assert UUID(action["handoff_id"])
        assert action["handoff_kind"] == "automatic_continuation"
        assert action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == str(TASK_ID)
        assert action["source_consumption_message_id"] == str(c2_msg_id)
        assert action["source_consumption_id"] == str(consumption_id)
        assert action["disposition_type"] == "AUTO_CONTINUE"
        assert action["disposition_reason"] == "review_has_no_blocking_findings"
        assert action["review_output_schema_version"] == REVIEW_OUTPUT_SCHEMA_VERSION
        assert action["source_review_verdict"] == "no_blocking_findings"
        assert action["source_review_risk_level"] == "low"
        assert action["source_consumption_validated"] is True
        assert action["replay_check_completed"] is True
        assert action["prior_handoff_detected"] is False
        assert action["bounded_rework_budget_exhausted"] is False
        assert action["rework_non_convergence_detected"] is False
        assert action["continuation_handoff_prepared"] is True
        assert action["rework_handoff_prepared"] is False
        assert action["blocked_reasons"] == []

        for flag in _HANDOFF_FALSE_FLAGS:
            assert action.get(flag) is False, f"{flag} should be False"

        assert action["ai_project_director_total_loop"] == "Partial"

        assert action["handoff_id"] == str(result.result.handoff_id)
        assert action["prepared_at"] == result.result.prepared_at.isoformat()
        assert action["handoff_kind"] == result.result.handoff_kind
        assert action["handoff_status"] == result.result.handoff_status
        prepared_at = datetime.fromisoformat(action["prepared_at"])
        assert prepared_at.tzinfo is not None
        assert prepared_at.utcoffset() is not None

        assert action["source_consumption_id"] == source_action["consumption_id"]
        assert action["source_consumption_preflight_message_id"] == source_action["source_consumption_preflight_message_id"]
        assert action["source_disposition_message_id"] == source_action["source_disposition_message_id"]
        assert action["source_review_message_id"] == source_action["source_review_message_id"]
        assert action["source_diff_message_id"] == source_action["source_diff_message_id"]
        assert action["disposition_id"] == source_action["disposition_id"]
        assert action["source_consumption_message_id"] == str(c2_msg_id)
        assert action["session_id"] == source_action["session_id"] == str(SESSION_ID)
        assert action["source_task_id"] == source_action["source_task_id"] == str(TASK_ID)
        for uuid_key in [
            "source_consumption_id",
            "source_consumption_preflight_message_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_diff_message_id",
            "disposition_id",
        ]:
            assert UUID(action[uuid_key])

        assert action["disposition_type"] == source_action["disposition_type"]
        assert action["disposition_reason"] == source_action["disposition_reason"]
        assert action["review_result_fingerprint"] == source_action["review_result_fingerprint"] == "a" * 64
        assert action["revalidated_review_result_fingerprint"] == source_action["revalidated_review_result_fingerprint"] == "a" * 64
        assert action["reviewed_diff_sha256"] == source_action["reviewed_diff_sha256"] == "b" * 64
        assert action["persisted_source_diff_sha256"] == source_action["persisted_source_diff_sha256"] == "b" * 64
        assert action["current_diff_sha256"] == source_action["current_diff_sha256"] == "b" * 64
        assert action["review_prompt_sha256"] == source_action["review_prompt_sha256"] == "c" * 64
        assert action["reviewed_scope_paths"] == source_action["reviewed_scope_paths"]
        assert action["persisted_source_scope_paths"] == source_action["persisted_source_scope_paths"]
        assert action["current_scope_paths"] == source_action["current_scope_paths"]
        assert action["review_output_schema_version"] == source_action["review_output_schema_version"]
        assert action["source_review_verdict"] == source_action["source_review_verdict"]
        assert action["source_review_risk_level"] == source_action["source_review_risk_level"]
        assert action["workspace_path"] == source_action["workspace_path"]
        assert action["workspace_path_within_root"] == source_action["workspace_path_within_root"]

        assert action["source_consumption_validated"] is True
        assert action["replay_check_completed"] is True
        assert action["prior_handoff_detected"] is False
        assert action["prior_rework_handoff_count"] == 0
        assert action["rework_attempt_number"] == 0
        assert action["rework_attempt_limit"] == 1
        assert action["continuation_handoff_prepared"] is True
        assert action["rework_handoff_prepared"] is False
        assert action["blocked_reasons"] == []
        assert action["bounded_rework_budget_exhausted"] is False
        assert action["rework_non_convergence_detected"] is False

        session2 = SessionLocal()
        count = session2.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL},
        ).scalar()
        assert count == 1
        session2.close()
        session.close()

    def test_c3_message_and_action_from_db(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, consumption_id = _seed_c2_consumed_message(session)

        c2_row = session.get(ProjectDirectorMessageTable, c2_msg_id)
        source_action = copy.deepcopy(json.loads(c2_row.suggested_actions_json)[0])
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.message is not None

        message = result.message
        assert message.id == result.message.id
        assert message.session_id == SESSION_ID
        assert message.role == ProjectDirectorMessageRole.ASSISTANT
        assert message.source == ProjectDirectorMessageSource.SYSTEM
        assert message.requires_confirmation is False
        assert message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert message.related_project_id == PROJECT_ID
        assert message.related_task_id == TASK_ID
        assert message.intent == "sandbox_candidate_diff_review_disposition_handoff"
        assert message.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
        assert len(message.suggested_actions) == 1
        assert message.created_at.tzinfo is not None
        assert message.created_at.utcoffset() is not None

        content_lower = message.content.lower()
        assert "prepared only" in content_lower
        assert "no continuation or rework execution" in content_lower
        assert "no task" in content_lower
        assert ", run," in content_lower
        assert ", worker," in content_lower
        assert "worktree was created" in content_lower
        assert "no file" in content_lower
        assert "no patch" in content_lower
        assert "no git write" in content_lower
        assert "total loop remains partial" in content_lower
        assert "continuation completed" not in content_lower
        assert "rework started" not in content_lower
        assert "task created" not in content_lower
        assert "worker dispatched" not in content_lower
        assert "write authorized" not in content_lower

        forbidden = message.forbidden_actions_detected
        for required in [
            "no_continuation_start",
            "no_rework_start",
            "no_human_escalation_package",
            "no_human_decision",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_manifest_write",
            "no_diff_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_worker_dispatch",
            "no_task_creation",
            "no_run_creation",
            "no_worktree_creation",
        ]:
            assert required in forbidden

        verify = SessionLocal()
        c3_row = verify.get(ProjectDirectorMessageTable, result.message.id)
        assert c3_row is not None

        assert c3_row.role == "assistant"
        assert c3_row.source == "system"
        assert c3_row.requires_confirmation is False
        assert c3_row.risk_level == "high"
        assert c3_row.related_project_id == PROJECT_ID
        assert c3_row.related_task_id == TASK_ID
        assert c3_row.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
        assert c3_row.created_at is not None
        assert c3_row.intent == "sandbox_candidate_diff_review_disposition_handoff"

        repo_msg = ProjectDirectorMessageRepository(verify).get_by_id(result.message.id)
        assert repo_msg is not None
        assert repo_msg.id == result.message.id
        assert repo_msg.session_id == SESSION_ID
        assert repo_msg.role == ProjectDirectorMessageRole.ASSISTANT
        assert repo_msg.source == ProjectDirectorMessageSource.SYSTEM
        assert repo_msg.requires_confirmation is False
        assert repo_msg.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        assert repo_msg.related_project_id == PROJECT_ID
        assert repo_msg.related_task_id == TASK_ID
        assert repo_msg.created_at.tzinfo is not None
        assert repo_msg.created_at.utcoffset() is not None

        actions = json.loads(c3_row.suggested_actions_json)
        assert len(actions) == 1
        act = actions[0]

        assert act["type"] == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE
        assert act["schema_version"] == DISPOSITION_HANDOFF_SCHEMA_VERSION
        assert act["handoff_status"] == "prepared"
        assert UUID(act["handoff_id"])
        assert act["prepared_at"] is not None
        assert act["handoff_kind"] == "automatic_continuation"
        assert act["session_id"] == str(SESSION_ID)
        assert act["source_task_id"] == str(TASK_ID)
        assert act["source_consumption_message_id"] == str(c2_msg_id)
        assert act["source_consumption_id"] == str(consumption_id)
        assert UUID(act["source_consumption_preflight_message_id"])
        assert UUID(act["source_disposition_message_id"])
        assert UUID(act["source_review_message_id"])
        assert UUID(act["source_diff_message_id"])
        assert UUID(act["disposition_id"])
        assert act["disposition_type"] == "AUTO_CONTINUE"
        assert act["disposition_reason"] == "review_has_no_blocking_findings"

        assert act["handoff_id"] == str(result.result.handoff_id)
        assert act["prepared_at"] == result.result.prepared_at.isoformat()
        assert act["handoff_kind"] == result.result.handoff_kind
        assert act["handoff_status"] == result.result.handoff_status
        prepared_at = datetime.fromisoformat(act["prepared_at"])
        assert prepared_at.tzinfo is not None
        assert prepared_at.utcoffset() is not None

        assert act["source_consumption_id"] == source_action["consumption_id"]
        assert act["source_consumption_preflight_message_id"] == source_action["source_consumption_preflight_message_id"]
        assert act["source_disposition_message_id"] == source_action["source_disposition_message_id"]
        assert act["source_review_message_id"] == source_action["source_review_message_id"]
        assert act["source_diff_message_id"] == source_action["source_diff_message_id"]
        assert act["disposition_id"] == source_action["disposition_id"]
        assert act["source_consumption_message_id"] == str(c2_msg_id)
        assert act["session_id"] == source_action["session_id"] == str(SESSION_ID)
        assert act["source_task_id"] == source_action["source_task_id"] == str(TASK_ID)
        for uuid_key in [
            "source_consumption_id",
            "source_consumption_preflight_message_id",
            "source_disposition_message_id",
            "source_review_message_id",
            "source_diff_message_id",
            "disposition_id",
        ]:
            assert UUID(act[uuid_key])

        assert act["disposition_type"] == source_action["disposition_type"]
        assert act["disposition_reason"] == source_action["disposition_reason"]
        assert act["review_result_fingerprint"] == source_action["review_result_fingerprint"] == "a" * 64
        assert act["revalidated_review_result_fingerprint"] == source_action["revalidated_review_result_fingerprint"] == "a" * 64
        assert act["reviewed_diff_sha256"] == source_action["reviewed_diff_sha256"] == "b" * 64
        assert act["persisted_source_diff_sha256"] == source_action["persisted_source_diff_sha256"] == "b" * 64
        assert act["current_diff_sha256"] == source_action["current_diff_sha256"] == "b" * 64
        assert act["review_prompt_sha256"] == source_action["review_prompt_sha256"] == "c" * 64
        assert act["reviewed_scope_paths"] == source_action["reviewed_scope_paths"]
        assert act["persisted_source_scope_paths"] == source_action["persisted_source_scope_paths"]
        assert act["current_scope_paths"] == source_action["current_scope_paths"]
        assert act["review_output_schema_version"] == source_action["review_output_schema_version"]
        assert act["source_review_verdict"] == source_action["source_review_verdict"]
        assert act["source_review_risk_level"] == source_action["source_review_risk_level"]
        assert act["workspace_path"] == source_action["workspace_path"]
        assert act["workspace_path_within_root"] == source_action["workspace_path_within_root"]

        assert act["source_consumption_validated"] is True
        assert act["replay_check_completed"] is True
        assert act["prior_handoff_detected"] is False
        assert act["prior_rework_handoff_count"] == 0
        assert act["rework_attempt_number"] == 0
        assert act["rework_attempt_limit"] == MAX_AUTOMATIC_REWORK_HANDOFFS_PER_REVIEW_LINEAGE
        assert act["continuation_handoff_prepared"] is True
        assert act["rework_handoff_prepared"] is False
        assert act["blocked_reasons"] == []
        assert act["bounded_rework_budget_exhausted"] is False
        assert act["rework_non_convergence_detected"] is False

        for flag in _HANDOFF_FALSE_FLAGS:
            assert act[flag] is False
        assert act["ai_project_director_total_loop"] == "Partial"

        c3_count = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE json_extract(suggested_actions_json, '$[0].source_consumption_message_id') = :cid"
            ),
            {"cid": str(c2_msg_id)},
        ).scalar()
        assert c3_count == 1

        verify.close()
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 15. TestSequentialReplay
# ══════════════════════════════════════════════════════════════════════


class TestSequentialReplay:
    def test_second_call_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        svc1, session1 = _make_c3_service(SessionLocal)
        r1 = svc1.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert r1.result.handoff_status == "prepared"
        session1.close()

        svc2, session2 = _make_c3_service(SessionLocal)
        r2 = svc2.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert r2.result.handoff_status == "blocked"
        assert "handoff_already_prepared" in r2.result.blocked_reasons
        assert r2.result.prior_handoff_detected is True
        assert r2.result.replay_check_completed is True
        assert r2.message is None
        session2.close()


# ══════════════════════════════════════════════════════════════════════
# 16. TestCrossPageReplay
# ══════════════════════════════════════════════════════════════════════


class TestCrossPageReplay:
    def test_replay_detected_across_pages(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, consumption_id = _seed_c2_consumed_message(session)
        session.close()

        handoff_msg_id, handoff_seq_no = _c3_prepare_handoff(SessionLocal, c2_msg_id)

        session = SessionLocal()
        _seed_filler_messages(session, handoff_seq_no + 1, 105)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        assert result.result.replay_check_completed is True
        assert "handoff_already_prepared" in result.result.blocked_reasons
        assert "bounded_rework_budget_exhausted" not in result.result.blocked_reasons
        assert "rework_non_convergence" not in result.result.blocked_reasons
        assert result.message is None

        c3_count = session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd "
                "AND json_extract(suggested_actions_json, '$[0].source_consumption_message_id') = :cid"
            ),
            {
                "sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
                "cid": str(c2_msg_id),
            },
        ).scalar()
        assert c3_count == 1
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 17. TestAutoReworkBudget
# ══════════════════════════════════════════════════════════════════════


class TestAutoReworkBudget:
    def test_same_lineage_replay_blocked(self, db_engine) -> None:
        """Same lineage (same C2): second call blocked with handoff_already_prepared."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        # First call: creates handoff
        _c3_prepare_handoff(SessionLocal, c2_msg_id)

        # Second call: same C2 → same lineage → replay blocked
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        assert "handoff_already_prepared" in result.result.blocked_reasons
        assert result.message is None
        session.close()

    def test_different_lineage_not_blocked(self, db_engine) -> None:
        """Different lineage (different C2): each gets its own handoff."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_1, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        c2_msg_2, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        # First handoff via real service
        _c3_prepare_handoff(SessionLocal, c2_msg_1)

        # Second handoff: different lineage → succeeds
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_2,
        )
        assert result.result.handoff_status == "prepared"
        assert result.result.prior_handoff_detected is False
        assert result.message is not None

        # Both handoffs persisted
        count = session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL},
        ).scalar()
        assert count == 2
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 18. TestCrossPageBudget
# ══════════════════════════════════════════════════════════════════════


class TestCrossPageBudget:
    def test_same_lineage_replay_across_pages(self, db_engine) -> None:
        """Same lineage replay detected even across pages."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        _, handoff_seq_no = _c3_prepare_handoff(SessionLocal, c2_msg_id)

        session = SessionLocal()
        _seed_filler_messages(session, handoff_seq_no + 1, 105)
        session.close()

        # Same C2 → same lineage → replay blocked across pages
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        assert result.message is None
        session.close()

    def test_different_lineage_across_pages(self, db_engine) -> None:
        """Different lineage: each gets its own handoff across pages."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_a, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        _, handoff_seq_no = _c3_prepare_handoff(SessionLocal, c2_msg_a)

        session = SessionLocal()
        _seed_filler_messages(session, handoff_seq_no + 1, 105)
        session.close()

        c2_msg_b, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK",
        )

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_b,
        )
        assert result.result.handoff_status == "prepared"
        assert result.result.prior_handoff_detected is False
        assert result.message is not None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 19. TestBudgetCounting
# ══════════════════════════════════════════════════════════════════════


def _seed_non_matching_handoff(
    SessionLocal,
    *,
    source_task_id: UUID = TASK_ID,
    disposition_type: str = "AUTO_REWORK",
    handoff_status: str = "prepared",
    rework_handoff_prepared: bool = True,
    source_detail: str = P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
    action_type: str = P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
) -> None:
    session = SessionLocal()
    sha = hashlib.sha256(b"other").hexdigest()
    if action_type == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE:
        action: dict[str, Any] = {
            "type": action_type,
            "schema_version": DISPOSITION_HANDOFF_SCHEMA_VERSION,
            "handoff_status": handoff_status,
            "handoff_id": str(uuid4()),
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "handoff_kind": (
                "automatic_continuation"
                if disposition_type == "AUTO_CONTINUE"
                else "bounded_automatic_rework"
            ),
            "session_id": str(SESSION_ID),
            "source_task_id": str(source_task_id),
            "source_consumption_message_id": str(uuid4()),
            "source_consumption_id": str(uuid4()),
            "source_consumption_preflight_message_id": str(uuid4()),
            "source_disposition_message_id": str(uuid4()),
            "source_review_message_id": str(uuid4()),
            "source_diff_message_id": str(uuid4()),
            "disposition_id": str(uuid4()),
            "disposition_type": disposition_type,
            "disposition_reason": (
                "review_has_no_blocking_findings"
                if disposition_type == "AUTO_CONTINUE"
                else "review_changes_required"
            ),
            "review_result_fingerprint": sha,
            "revalidated_review_result_fingerprint": sha,
            "reviewed_diff_sha256": sha,
            "persisted_source_diff_sha256": sha,
            "current_diff_sha256": sha,
            "review_prompt_sha256": sha,
            "reviewed_scope_paths": ["src/example.py"],
            "persisted_source_scope_paths": ["src/example.py"],
            "current_scope_paths": ["src/example.py"],
            "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
            "source_review_verdict": "changes_required",
            "source_review_risk_level": "low",
            "workspace_path": "/tmp/ws",
            "workspace_path_within_root": True,
            "source_consumption_validated": True,
            "replay_check_completed": True,
            "prior_handoff_detected": False,
            "prior_rework_handoff_count": 0,
            "rework_attempt_number": 0 if disposition_type == "AUTO_CONTINUE" else 1,
            "rework_attempt_limit": MAX_AUTOMATIC_REWORK_HANDOFFS_PER_REVIEW_LINEAGE,
            "bounded_rework_budget_exhausted": False,
            "rework_non_convergence_detected": False,
            "continuation_handoff_prepared": disposition_type == "AUTO_CONTINUE",
            "rework_handoff_prepared": rework_handoff_prepared if disposition_type != "AUTO_CONTINUE" else False,
            "blocked_reasons": [],
            "continuation_started": False,
            "rework_started": False,
            "human_escalation_package_created": False,
            "human_decision_recorded": False,
            "main_project_file_written": False,
            "sandbox_file_written": False,
            "manifest_file_written": False,
            "diff_file_written": False,
            "patch_applied": False,
            "git_write_performed": False,
            "worktree_created": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "gate_allows_write": False,
            "ai_project_director_total_loop": "Partial",
        }
    else:
        action = {"type": action_type, "handoff_status": handoff_status}
    _HANDOFF_CONTENT = (
        "A bounded disposition handoff was prepared only. No continuation or "
        "rework execution was started, no Task, Run, Worker, or worktree was "
        "created, no file was written, no patch was applied, and no Git write "
        "was performed. AI Project Director total loop remains Partial."
    )
    _HANDOFF_FORBIDDEN_ACTIONS = [
        "no_continuation_start", "no_rework_start",
        "no_human_escalation_package", "no_human_decision",
        "no_workspace_write", "no_main_project_file_write",
        "no_manifest_write", "no_diff_file_write",
        "no_patch_apply", "no_product_runtime_git_write",
        "no_worker_dispatch", "no_task_creation",
        "no_run_creation", "no_worktree_creation",
    ]
    session.add(
        ProjectDirectorMessageTable(
            id=uuid4(),
            session_id=SESSION_ID,
            role="assistant",
            content=_HANDOFF_CONTENT,
            sequence_no=500,
            source="system",
            source_detail=source_detail,
            intent="sandbox_candidate_diff_review_disposition_handoff",
            suggested_actions_json=json.dumps([action]),
            requires_confirmation=False,
            risk_level="high",
            related_project_id=PROJECT_ID,
            related_task_id=source_task_id,
            forbidden_actions_detected_json=json.dumps(_HANDOFF_FORBIDDEN_ACTIONS),
            token_count=None,
        )
    )
    session.commit()
    session.close()


class TestBudgetCounting:
    def test_non_matching_handoffs_not_counted(self, db_engine) -> None:
        """Handoff for different task does not block current task's handoff."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)

        other_task_id = uuid4()
        acceptance = json.dumps(["safe_dry_run_task=true"])
        session.add(
            TaskTable(
                id=other_task_id,
                project_id=PROJECT_ID,
                title="Other task",
                status="pending",
                priority="normal",
                input_summary="OTHER TASK",
                risk_level="normal",
                human_status="none",
                source_draft_id="p12-other",
                acceptance_criteria=acceptance,
            )
        )
        session.commit()
        other_c2_msg, _ = _seed_c2_consumed_message(
            session,
            source_task_id=other_task_id,
            disposition_type="AUTO_REWORK",
        )
        session.close()

        _c3_prepare_handoff(
            SessionLocal,
            other_c2_msg,
            source_task_id=other_task_id,
        )

        new_c2_msg, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK",
        )

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=new_c2_msg,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

    def test_different_source_task_id(self, db_engine) -> None:
        """Handoff for different task has different lineage → ignored."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        other_task_id = uuid4()
        acceptance = json.dumps(["safe_dry_run_task=true"])
        session.add(
            TaskTable(
                id=other_task_id,
                project_id=PROJECT_ID,
                title="Other task",
                status="pending",
                priority="normal",
                input_summary="OTHER TASK",
                risk_level="normal",
                human_status="none",
                source_draft_id="p12-other",
                acceptance_criteria=acceptance,
            )
        )
        session.commit()
        other_c2, _ = _seed_c2_consumed_message(
            session,
            source_task_id=other_task_id,
            disposition_type="AUTO_REWORK",
        )
        session.close()
        _c3_prepare_handoff(
            SessionLocal,
            other_c2,
            source_task_id=other_task_id,
        )

        new_c2, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK",
        )
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=new_c2,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

    def test_auto_continue_disposition(self, db_engine) -> None:
        """Handoff with AUTO_CONTINUE disposition has different lineage → ignored."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        continue_c2, _ = _seed_c2_consumed_message(
            session,
            disposition_type="AUTO_CONTINUE",
        )
        session.close()
        _c3_prepare_handoff(SessionLocal, continue_c2)

        new_c2, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK",
        )
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=new_c2,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

    def test_blocked_action_status_causes_conflict(self, db_engine) -> None:
        """Malformed marker (blocked status with prepared fields) → history conflict."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.commit()
        session.close()
        _seed_non_matching_handoff(SessionLocal, handoff_status="blocked")

        new_c2, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK",
        )
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=new_c2,
        )
        assert result.result.handoff_status == "blocked"
        assert "handoff_history_conflict" in result.result.blocked_reasons
        session.close()

    def test_rework_not_prepared_causes_conflict(self, db_engine) -> None:
        """Malformed marker (prepared but rework_handoff_prepared=false) → conflict."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.commit()
        session.close()
        _seed_non_matching_handoff(SessionLocal, rework_handoff_prepared=False)

        new_c2, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK",
        )
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=new_c2,
        )
        assert result.result.handoff_status == "blocked"
        assert "handoff_history_conflict" in result.result.blocked_reasons
        session.close()

    def test_wrong_c3_source_detail_causes_conflict(self, db_engine) -> None:
        """Malformed handoff marker (wrong source_detail) causes history conflict."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.commit()
        session.close()
        _seed_non_matching_handoff(SessionLocal, source_detail="wrong_c3_source_detail")

        new_c2, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK", c2_msg_id=uuid4()
        )
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=new_c2,
        )
        assert result.result.handoff_status == "blocked"
        assert "handoff_history_conflict" in result.result.blocked_reasons
        session.close()

    def test_wrong_c3_action_type_causes_conflict(self, db_engine) -> None:
        """Malformed handoff marker (wrong action_type) causes history conflict."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        session.commit()
        session.close()
        _seed_non_matching_handoff(SessionLocal, action_type="wrong_action_type")

        new_c2, _ = _seed_c2_consumed_message(
            SessionLocal(), disposition_type="AUTO_REWORK", c2_msg_id=uuid4()
        )
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID, source_task_id=TASK_ID, source_message_id=new_c2,
        )
        assert result.result.handoff_status == "blocked"
        assert "handoff_history_conflict" in result.result.blocked_reasons
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 20. TestAutoContinueAfterRework
# ══════════════════════════════════════════════════════════════════════


class TestAutoContinueAfterRework:
    def test_continue_not_blocked_by_rework_handoff(self, db_engine) -> None:
        """AUTO_CONTINUE lineage not blocked by prior AUTO_REWORK handoff (different lineage)."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_rework, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        c2_continue, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_CONTINUE",
        )
        session.close()

        # Create AUTO_REWORK handoff via real service
        _c3_prepare_handoff(SessionLocal, c2_rework)

        # AUTO_CONTINUE lineage should succeed (different lineage)
        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_continue,
        )
        assert result.result.handoff_status == "prepared"
        assert result.result.disposition_type == "AUTO_CONTINUE"
        assert result.result.handoff_kind == "automatic_continuation"
        assert result.result.continuation_handoff_prepared is True
        assert result.result.rework_handoff_prepared is False
        assert result.result.blocked_reasons == []
        assert result.message is not None
        session.close()


# ══════════════════════════════════════════════════════════════════════
# 21. TestConcurrentSameConsumption
# ══════════════════════════════════════════════════════════════════════


class HoldingImmediateTransactionRepository(ProjectDirectorMessageRepository):
    """Test-only repo: acquires BEGIN IMMEDIATE then holds until released."""

    def __init__(self, session, writer_lock_acquired, release_writer):
        super().__init__(session)
        self._writer_lock_acquired = writer_lock_acquired
        self._release_writer = release_writer

    @contextmanager
    def sqlite_immediate_transaction(self):
        with super().sqlite_immediate_transaction():
            self._writer_lock_acquired.set()
            if not self._release_writer.wait(timeout=10):
                raise TimeoutError("writer release timeout")
            yield


class AttemptSignalingRepository(ProjectDirectorMessageRepository):
    """Test-only repo: signals before and after entering BEGIN IMMEDIATE."""

    def __init__(self, session, second_writer_attempted, second_writer_entered):
        super().__init__(session)
        self._second_writer_attempted = second_writer_attempted
        self._second_writer_entered = second_writer_entered

    @contextmanager
    def sqlite_immediate_transaction(self):
        self._second_writer_attempted.set()
        with super().sqlite_immediate_transaction():
            self._second_writer_entered.set()
            yield


class TestConcurrentSameConsumption:
    def test_two_threads_one_prepared_one_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        writer_lock_acquired = threading.Event()
        release_writer = threading.Event()
        second_writer_attempted = threading.Event()
        second_writer_entered = threading.Event()

        results = []
        errors = []

        def worker_a():
            session = SessionLocal()
            msg_repo = HoldingImmediateTransactionRepository(
                session, writer_lock_acquired, release_writer
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_handoff(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=c2_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-a:{type(e).__name__}:{e}")
            finally:
                session.close()

        def worker_b():
            session = SessionLocal()
            msg_repo = AttemptSignalingRepository(
                session, second_writer_attempted, second_writer_entered
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_handoff(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=c2_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-b:{type(e).__name__}:{e}")
            finally:
                session.close()

        t_a = threading.Thread(target=worker_a)
        t_a.start()

        if not writer_lock_acquired.wait(timeout=30):
            raise TimeoutError("thread A did not acquire writer lock")

        t_b = threading.Thread(target=worker_b)
        t_b.start()

        if not second_writer_attempted.wait(timeout=30):
            raise TimeoutError("thread B did not attempt writer lock")

        assert not second_writer_entered.wait(timeout=0.25), (
            "thread B entered SQLite immediate transaction while A still holds lock"
        )

        release_writer.set()

        t_a.join(timeout=30)
        t_b.join(timeout=30)

        assert second_writer_entered.wait(timeout=0), (
            "thread B never entered SQLite immediate transaction after A released"
        )
        assert not t_a.is_alive(), "thread A did not finish"
        assert not t_b.is_alive(), "thread B did not finish"
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 2

        statuses = [r.result.handoff_status for r in results]
        assert statuses.count("prepared") == 1
        assert statuses.count("blocked") == 1

        prepared_result = next(r for r in results if r.result.handoff_status == "prepared")
        blocked_result = next(r for r in results if r.result.handoff_status == "blocked")
        assert prepared_result.message is not None
        assert blocked_result.message is None
        assert blocked_result.result.prior_handoff_detected is True
        assert blocked_result.result.replay_check_completed is True
        assert "handoff_already_prepared" in blocked_result.result.blocked_reasons
        assert "bounded_rework_budget_exhausted" not in blocked_result.result.blocked_reasons
        assert "rework_non_convergence" not in blocked_result.result.blocked_reasons

        verify_session = SessionLocal()
        count = verify_session.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd "
                "AND json_extract(suggested_actions_json, '$[0].source_consumption_message_id') = :cid"
            ),
            {
                "sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
                "cid": str(c2_msg_id),
            },
        ).scalar()
        assert count == 1
        verify_session.execute(text("BEGIN IMMEDIATE"))
        verify_session.commit()
        verify_session.close()


# ══════════════════════════════════════════════════════════════════════
# 22. TestConcurrentReworkConsumptions
# ══════════════════════════════════════════════════════════════════════


class TestConcurrentReworkConsumptions:
    def test_same_lineage_concurrent_one_prepared_one_blocked(self, db_engine) -> None:
        """Same lineage concurrent: one prepared, one blocked (replay)."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        writer_lock_acquired = threading.Event()
        release_writer = threading.Event()
        second_writer_attempted = threading.Event()
        second_writer_entered = threading.Event()

        results = []
        errors = []

        def worker_a():
            session = SessionLocal()
            msg_repo = HoldingImmediateTransactionRepository(
                session, writer_lock_acquired, release_writer
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_handoff(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=c2_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-a:{type(e).__name__}:{e}")
            finally:
                session.close()

        def worker_b():
            session = SessionLocal()
            msg_repo = AttemptSignalingRepository(
                session, second_writer_attempted, second_writer_entered
            )
            sess_repo = ProjectDirectorSessionRepository(session)
            task_repo = TaskRepository(session)
            svc = ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
                session_repository=sess_repo,
                message_repository=msg_repo,
                task_repository=task_repo,
            )
            try:
                result = svc.prepare_candidate_diff_review_disposition_handoff(
                    session_id=SESSION_ID,
                    source_task_id=TASK_ID,
                    source_message_id=c2_msg_id,
                )
                results.append(result)
            except Exception as e:
                errors.append(f"thread-b:{type(e).__name__}:{e}")
            finally:
                session.close()

        t_a = threading.Thread(target=worker_a)
        t_a.start()

        if not writer_lock_acquired.wait(timeout=30):
            raise TimeoutError("thread A did not acquire writer lock")

        t_b = threading.Thread(target=worker_b)
        t_b.start()

        if not second_writer_attempted.wait(timeout=30):
            raise TimeoutError("thread B did not attempt writer lock")

        assert not second_writer_entered.wait(timeout=0.25), (
            "thread B entered SQLite immediate transaction while A still holds lock"
        )

        release_writer.set()

        t_a.join(timeout=30)
        t_b.join(timeout=30)

        assert second_writer_entered.wait(timeout=0)
        assert not t_a.is_alive()
        assert not t_b.is_alive()
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 2

        statuses = [r.result.handoff_status for r in results]
        assert statuses.count("prepared") == 1
        assert statuses.count("blocked") == 1

        prepared_result = next(r for r in results if r.result.handoff_status == "prepared")
        blocked_result = next(r for r in results if r.result.handoff_status == "blocked")

        assert prepared_result.result.handoff_kind == "bounded_automatic_rework"
        assert prepared_result.message is not None

        assert blocked_result.result.prior_handoff_detected is True
        assert "handoff_already_prepared" in blocked_result.result.blocked_reasons
        assert blocked_result.message is None

        verify = SessionLocal()
        total_c3 = verify.execute(
            text(
                "SELECT COUNT(*) FROM project_director_messages "
                "WHERE source_detail = :sd"
            ),
            {"sd": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL},
        ).scalar()
        assert total_c3 == 1
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 23. TestLockRelease
# ══════════════════════════════════════════════════════════════════════


class TestLockRelease:
    def test_blocked_missing_session_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=uuid4(),
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert "session_missing" in result.result.blocked_reasons
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_blocked_missing_task_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=uuid4(),
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert "source_task_missing" in result.result.blocked_reasons
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_blocked_missing_message_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        _seed_c2_consumed_message(session)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=uuid4(),
        )
        assert result.result.handoff_status == "blocked"
        assert "source_consumption_message_missing" in result.result.blocked_reasons
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_prepared_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_replay_blocked_releases_lock(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        _c3_prepare_handoff(SessionLocal, c2_msg_id)

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()

    def test_replay_blocked_releases_lock(self, db_engine) -> None:
        """Same-lineage replay blocked releases SQLite lock."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        _c3_prepare_handoff(SessionLocal, c2_msg_id)

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        session.close()

        verify = SessionLocal()
        verify.execute(text("BEGIN IMMEDIATE"))
        verify.commit()
        verify.close()


# ══════════════════════════════════════════════════════════════════════
# 24. TestNoSideEffects
# ══════════════════════════════════════════════════════════════════════


class TestNoSideEffects:
    def test_task_count_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        pre_sess = SessionLocal()
        task_count_before = pre_sess.execute(
            text("SELECT COUNT(*) FROM tasks")
        ).scalar()
        pre_sess.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

        post_sess = SessionLocal()
        task_count_after = post_sess.execute(
            text("SELECT COUNT(*) FROM tasks")
        ).scalar()
        assert task_count_after == task_count_before
        post_sess.close()

    def test_run_count_unchanged(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "prepared"
        session.close()

        post_sess = SessionLocal()
        run_count = post_sess.execute(
            text("SELECT COUNT(*) FROM runs")
        ).scalar()
        assert run_count == 0
        post_sess.close()

    def test_task_and_run_count_unchanged_after_replay_blocked(self, db_engine) -> None:
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(session)
        session.close()

        _c3_prepare_handoff(SessionLocal, c2_msg_id)

        pre_sess = SessionLocal()
        task_count_before = pre_sess.execute(
            text("SELECT COUNT(*) FROM tasks")
        ).scalar()
        run_count_before = pre_sess.execute(
            text("SELECT COUNT(*) FROM runs")
        ).scalar()
        pre_sess.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        session.close()

        post_sess = SessionLocal()
        assert post_sess.execute(text("SELECT COUNT(*) FROM tasks")).scalar() == task_count_before
        assert post_sess.execute(text("SELECT COUNT(*) FROM runs")).scalar() == run_count_before
        post_sess.close()

    def test_task_and_run_count_unchanged_after_replay_blocked(self, db_engine) -> None:
        """Same-lineage replay blocked does not create tasks or runs."""
        SessionLocal = _make_session_factory(db_engine)
        session = SessionLocal()
        _seed_base_records(session)
        c2_msg_id, _ = _seed_c2_consumed_message(
            session, disposition_type="AUTO_REWORK",
        )
        session.close()

        _c3_prepare_handoff(SessionLocal, c2_msg_id)

        pre_sess = SessionLocal()
        task_count_before = pre_sess.execute(
            text("SELECT COUNT(*) FROM tasks")
        ).scalar()
        run_count_before = pre_sess.execute(
            text("SELECT COUNT(*) FROM runs")
        ).scalar()
        pre_sess.close()

        svc, session = _make_c3_service(SessionLocal)
        result = svc.prepare_candidate_diff_review_disposition_handoff(
            session_id=SESSION_ID,
            source_task_id=TASK_ID,
            source_message_id=c2_msg_id,
        )
        assert result.result.handoff_status == "blocked"
        assert result.result.prior_handoff_detected is True
        session.close()

        post_sess = SessionLocal()
        assert post_sess.execute(text("SELECT COUNT(*) FROM tasks")).scalar() == task_count_before
        assert post_sess.execute(text("SELECT COUNT(*) FROM runs")).scalar() == run_count_before
        post_sess.close()
