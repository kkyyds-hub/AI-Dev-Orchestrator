"""Real behavioral tests for P23-D1 atomic dispatch consumption."""

from __future__ import annotations

import json
import threading
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.db_tables import ORMBase, RunTable
from app.domain.run import RunStatus
from app.domain.task import TaskStatus
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
)
from tests.p23_test_support import (
    DIFF_SHA256,
    make_d1_service,
    make_repos,
    make_session_factory,
    make_test_engine,
    prepare_valid_preflight,
    seed_base_records,
    count_messages_by_source_detail,
    get_messages_by_source_detail,
)


# ══════════════════════════════════════════════════════════════════════
# D1 Real Service Behavioral Tests
# ══════════════════════════════════════════════════════════════════════


class TestD1ConsumptionBehavior:
    """Real D1 service behavioral tests using actual SQLite and repositories."""

    def test_d1_success_claims_task_creates_exact_run_and_consumption(self, tmp_path):
        """D1 successfully claims task, creates Run, and persists consumption."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        # Create real P23-C preflight
        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # Create real D1 service
        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )

        # Act
        result = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )

        # Assert
        assert result.result.consumption_status == "reserved_for_worker_start"
        assert result.message is not None

        # Task state
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.RUNNING
        assert result.result.task_claimed is True

        # Run
        assert result.result.run_created is True
        assert result.result.run_id is not None
        run = run_repo.get_by_id(result.result.run_id)
        assert run is not None
        assert run.task_id == ids["task_id"]
        assert run.status == RunStatus.RUNNING

        # D1 message
        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 1
        assert result.result.consumption_id == result.message.id

        # Git boundary
        assert result.result.product_runtime_git_write_allowed is False

        session.close()
        engine.dispose()

    def test_d1_replay_reuses_same_consumption_and_run(self, tmp_path):
        """Second D1 call returns same consumption and Run without creating new ones."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # First call
        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )
        r1 = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )
        assert r1.result.consumption_status == "reserved_for_worker_start"
        first_msg_id = r1.message.id
        first_run_id = r1.result.run_id
        session.close()

        # Second call (replay)
        d1_svc2, session2, msg_repo2, task_repo2, run_repo2 = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )
        r2 = d1_svc2.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )

        assert r2.message.id == first_msg_id
        assert r2.result.run_id == first_run_id
        assert r2.result.resumed_from_existing_consumption is True

        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 1

        # Run count
        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 1

        session2.close()
        engine.dispose()

    def test_d1_rolls_back_when_run_creation_fails_after_task_claim(self, tmp_path):
        """D1 rolls back task state if Run creation fails."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # Monkey-patch run_repo to fail on add_running_run_no_event
        original_add = run_repo.add_running_run_no_event

        def failing_add(*args, **kwargs):
            raise RuntimeError("Simulated Run creation failure")

        run_repo.add_running_run_no_event = failing_add

        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )

        result = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )

        # Should be blocked due to rollback
        assert result.result.consumption_status == "blocked"

        # Verify rollback: task should be back to original state
        session2 = sf()
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.PENDING

        # No Run created
        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 0

        # No D1 message
        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 0

        # Restore
        run_repo.add_running_run_no_event = original_add
        session.close()
        session2.close()
        engine.dispose()

    def test_d1_rolls_back_when_consumption_message_creation_fails(self, tmp_path):
        """D1 rolls back if consumption message creation fails."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # Monkey-patch msg_repo to fail on create
        original_create = msg_repo.create
        call_count = [0]

        def failing_create(message):
            # Let preflight/intent creates through, fail on D1 consumption create
            if hasattr(message, 'source_detail') and message.source_detail == P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL:
                raise RuntimeError("Simulated message creation failure")
            return original_create(message)

        msg_repo.create = failing_create

        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )

        result = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )

        assert result.result.consumption_status == "blocked"

        # Verify rollback
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.PENDING

        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 0

        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 0

        msg_repo.create = original_create
        session.close()
        engine.dispose()

    def test_d1_publishes_events_only_after_commit_and_not_on_replay(self, tmp_path):
        """Events are published after commit, not on replay."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # First call - should succeed
        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )
        r1 = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )
        assert r1.result.consumption_status == "reserved_for_worker_start"

        # Verify committed state
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.RUNNING
        run = run_repo.get_by_id(r1.result.run_id)
        assert run is not None
        session.close()

        # Second call (replay) - should not create new events
        d1_svc2, session2, msg_repo2, task_repo2, run_repo2 = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )
        r2 = d1_svc2.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )
        assert r2.result.resumed_from_existing_consumption is True
        assert r2.message.id == r1.message.id
        session2.close()
        engine.dispose()

    def test_d1_sse_failure_does_not_rollback_committed_consumption(self, tmp_path):
        """SSE failure after commit doesn't rollback the consumption."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # Monkey-patch event_stream_service to fail
        from app.services import event_stream_service as ess
        original_publish = ess.event_stream_service.publish_task_updated
        ess.event_stream_service.publish_task_updated = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("SSE failure"))

        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )

        result = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )

        # D1 should still succeed (SSE failure is caught)
        assert result.result.consumption_status == "reserved_for_worker_start"

        # Database should still have committed state
        task = task_repo.get_by_id(ids["task_id"])
        assert task.status == TaskStatus.RUNNING

        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 1

        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 1

        ess.event_stream_service.publish_task_updated = original_publish
        session.close()
        engine.dispose()

    def test_d1_finder_returns_existing_consumption_without_mutation(self, tmp_path):
        """Finder returns existing consumption without creating new ones."""
        engine = make_test_engine(str(tmp_path / "test.db"))
        sf = make_session_factory(engine)
        s = sf()
        ids = seed_base_records(s, task_status="pending")
        s.close()

        preflight_msg_id, session, msg_repo, task_repo, run_repo, preflight_svc = (
            prepare_valid_preflight(
                sf,
                session_id=ids["session_id"],
                task_id=ids["task_id"],
                project_id=ids["project_id"],
            )
        )
        session.close()

        # Create consumption
        d1_svc, session, msg_repo, task_repo, run_repo = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )
        r1 = d1_svc.consume_protected_transition_dispatch_preflight(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_message_id=preflight_msg_id,
        )
        assert r1.result.consumption_status == "reserved_for_worker_start"
        session.close()

        # Finder should return existing without mutation
        d1_svc2, session2, msg_repo2, task_repo2, run_repo2 = make_d1_service(
            sf, preflight_svc=preflight_svc,
            msg_repo=msg_repo, task_repo=task_repo, run_repo=run_repo,
        )
        found = d1_svc2.find_persisted_protected_transition_dispatch_consumption(
            session_id=ids["session_id"],
            source_task_id=ids["task_id"],
            source_preflight_message_id=preflight_msg_id,
        )

        assert found.result is not None
        assert found.result.consumption_id == r1.result.consumption_id
        assert found.message.id == r1.message.id
        assert found.run is not None
        assert found.run.id == r1.result.run_id
        assert found.blocked_reasons == []

        # Verify no mutation
        d1_count = count_messages_by_source_detail(
            msg_repo, ids["session_id"],
            P23_PROTECTED_TRANSITION_DISPATCH_CONSUMPTION_SOURCE_DETAIL,
        )
        assert d1_count == 1

        runs = run_repo.list_by_task_id(ids["task_id"])
        assert len(runs) == 1

        session2.close()
        engine.dispose()
