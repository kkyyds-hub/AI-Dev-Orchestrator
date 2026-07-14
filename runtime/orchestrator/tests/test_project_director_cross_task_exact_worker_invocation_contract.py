"""P24-G Domain contract tests for Claim and Outcome models."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_cross_task_exact_worker_invocation_claim import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION,
    ProjectDirectorCrossTaskExactWorkerInvocationClaim,
    ProjectDirectorCrossTaskExactWorkerInvocationClaimResult,
)
from app.domain.project_director_cross_task_exact_worker_invocation_outcome import (
    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcome,
    ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult,
)
from app.domain.project_director_next_task_instruction_package import (
    compute_p24_contract_sha256,
)

from tests.p24_test_support import (
    build_p24_chain,
    build_valid_outcome,
)


# ── Claim Domain Tests ──────────────────────────────────────────────


class TestClaimContract:
    """7.1 Claim Contract tests."""

    def test_normal_construction(self):
        """Claim can be constructed with valid data."""
        chain = build_p24_chain()
        claim = chain.claim
        assert claim.exact_worker_invocation_claim_id == chain.claim_id
        assert claim.status == "worker_invocation_claimed"
        assert claim.worker_invocation_claimed is True
        assert claim.single_use_worker_call_authorized is True
        assert claim.worker_called is False
        assert claim.worker_call_attempted is False

    def test_frozen_immutability(self):
        """Claim is frozen and cannot be modified."""
        chain = build_p24_chain()
        claim = chain.claim
        with pytest.raises(ValidationError):
            claim.worker_called = True

    def test_tuple_immutability(self):
        """Tuple fields on Claim are deeply immutable."""
        chain = build_p24_chain()
        claim = chain.claim
        with pytest.raises((TypeError, AttributeError)):
            claim.active_run_ids_before.append(uuid4())
        with pytest.raises((TypeError, AttributeError)):
            claim.worker_selected_skills.append(None)

    def test_json_round_trip(self):
        """Claim survives JSON serialization round-trip."""
        chain = build_p24_chain()
        claim = chain.claim
        dumped = claim.model_dump(mode="json")
        restored = ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(dumped)
        assert restored == claim

    def test_replay_key_stable(self):
        """Replay key is deterministic for same inputs."""
        chain = build_p24_chain()
        claim = chain.claim
        computed = ProjectDirectorCrossTaskExactWorkerInvocationClaim.compute_worker_invocation_claim_replay_key(
            continuation_id=claim.continuation_id,
            exact_worker_start_reservation_id=claim.exact_worker_start_reservation_id,
            exact_run_reservation_id=claim.exact_run_reservation_id,
            instruction_package_id=claim.instruction_package_id,
            next_task_id=claim.next_task_id,
            exact_run_id=claim.exact_run_id,
        )
        assert computed == claim.worker_invocation_claim_replay_key

    def test_claim_token_stable(self):
        """Claim token is deterministic for same inputs."""
        chain = build_p24_chain()
        claim = chain.claim
        computed = ProjectDirectorCrossTaskExactWorkerInvocationClaim.compute_worker_invocation_claim_token(
            exact_worker_invocation_claim_id=claim.exact_worker_invocation_claim_id,
            worker_invocation_claim_replay_key=claim.worker_invocation_claim_replay_key,
            exact_worker_start_reservation_id=claim.exact_worker_start_reservation_id,
            exact_worker_start_reservation_fingerprint=claim.exact_worker_start_reservation_fingerprint,
            exact_run_id=claim.exact_run_id,
        )
        assert computed == claim.worker_invocation_claim_token

    def test_fingerprint_stable(self):
        """Fingerprint is deterministic for same data."""
        chain = build_p24_chain()
        claim = chain.claim
        computed = claim.compute_fingerprint()
        assert computed == claim.worker_invocation_claim_fingerprint

    def test_invalid_sha_rejected(self):
        """Claim rejects invalid SHA-256 hashes."""
        chain = build_p24_chain()
        data = chain.claim.model_dump(mode="python")
        data["worker_invocation_claim_fingerprint"] = "not-a-sha"
        data["exact_worker_invocation_claim_id"] = uuid4()
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(data)

    def test_wrong_previous_record_id_rejected(self):
        """Claim rejects wrong previous_record_id."""
        chain = build_p24_chain()
        data = chain.claim.model_dump(mode="python")
        data["previous_record_id"] = uuid4()
        data["exact_worker_invocation_claim_id"] = uuid4()
        data["worker_invocation_claim_replay_key"] = "a" * 64
        data["worker_invocation_claim_token"] = "a" * 64
        data["worker_invocation_claim_fingerprint"] = "a" * 64
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(data)

    def test_wrong_active_run_tuple_rejected(self):
        """Claim rejects wrong active_run_ids_before."""
        chain = build_p24_chain()
        data = chain.claim.model_dump(mode="python")
        data["active_run_ids_before"] = (uuid4(), uuid4())
        data["exact_worker_invocation_claim_id"] = uuid4()
        data["worker_invocation_claim_replay_key"] = "a" * 64
        data["worker_invocation_claim_token"] = "a" * 64
        data["worker_invocation_claim_fingerprint"] = "a" * 64
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(data)

    def test_non_empty_active_agent_session_rejected(self):
        """Claim rejects non-empty active_agent_session_ids_before."""
        chain = build_p24_chain()
        data = chain.claim.model_dump(mode="python")
        data["active_agent_session_ids_before"] = (uuid4(),)
        data["exact_worker_invocation_claim_id"] = uuid4()
        data["worker_invocation_claim_replay_key"] = "a" * 64
        data["worker_invocation_claim_token"] = "a" * 64
        data["worker_invocation_claim_fingerprint"] = "a" * 64
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(data)

    def test_worker_called_true_rejected(self):
        """Claim rejects worker_called=True."""
        chain = build_p24_chain()
        data = chain.claim.model_dump(mode="python")
        data["worker_called"] = True
        data["exact_worker_invocation_claim_id"] = uuid4()
        data["worker_invocation_claim_replay_key"] = "a" * 64
        data["worker_invocation_claim_token"] = "a" * 64
        data["worker_invocation_claim_fingerprint"] = "a" * 64
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(data)

    def test_worker_call_attempted_true_rejected(self):
        """Claim rejects worker_call_attempted=True."""
        chain = build_p24_chain()
        data = chain.claim.model_dump(mode="python")
        data["worker_call_attempted"] = True
        data["exact_worker_invocation_claim_id"] = uuid4()
        data["worker_invocation_claim_replay_key"] = "a" * 64
        data["worker_invocation_claim_token"] = "a" * 64
        data["worker_invocation_claim_fingerprint"] = "a" * 64
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaim.model_validate(data)


class TestClaimResult:
    """Claim Result contract tests."""

    def test_created_result(self):
        """created result has automatic_worker_call_allowed=True."""
        chain = build_p24_chain()
        result = ProjectDirectorCrossTaskExactWorkerInvocationClaimResult(
            status="invocation_claim_created",
            claim=chain.claim,
            blocked_reasons=(),
            invocation_claim_created=True,
            invocation_claim_replayed=False,
            automatic_worker_call_allowed=True,
            worker_called=False,
            product_runtime_git_write_allowed=False,
        )
        assert result.automatic_worker_call_allowed is True
        assert result.claim is not None

    def test_replayed_result(self):
        """replayed result has automatic_worker_call_allowed=False."""
        chain = build_p24_chain()
        result = ProjectDirectorCrossTaskExactWorkerInvocationClaimResult(
            status="invocation_claim_replayed",
            claim=chain.claim,
            blocked_reasons=(),
            invocation_claim_created=False,
            invocation_claim_replayed=True,
            automatic_worker_call_allowed=False,
            worker_called=False,
            product_runtime_git_write_allowed=False,
        )
        assert result.automatic_worker_call_allowed is False
        assert result.claim is not None

    def test_blocked_result(self):
        """blocked result has Claim=None and reason."""
        result = ProjectDirectorCrossTaskExactWorkerInvocationClaimResult(
            status="blocked",
            claim=None,
            blocked_reasons=("exact_worker_invocation_claim_history_invalid",),
            invocation_claim_created=False,
            invocation_claim_replayed=False,
            automatic_worker_call_allowed=False,
            worker_called=False,
            product_runtime_git_write_allowed=False,
        )
        assert result.claim is None
        assert len(result.blocked_reasons) > 0

    def test_invalid_boolean_combination_rejected(self):
        """Invalid boolean combinations are rejected."""
        chain = build_p24_chain()
        with pytest.raises(ValidationError):
            ProjectDirectorCrossTaskExactWorkerInvocationClaimResult(
                status="invocation_claim_created",
                claim=chain.claim,
                blocked_reasons=(),
                invocation_claim_created=True,
                invocation_claim_replayed=True,  # invalid: both true
                automatic_worker_call_allowed=True,
                worker_called=False,
                product_runtime_git_write_allowed=False,
            )


# ── Outcome Domain Tests ────────────────────────────────────────────


class TestOutcomeContract:
    """7.2 Outcome Contract tests."""

    def test_not_invoked_construction(self):
        """not_invoked outcome can be constructed."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="not_invoked")
        assert outcome.status == "not_invoked"
        assert outcome.worker_call_attempted is False
        assert outcome.worker_returned is False
        assert outcome.worker_raised is False
        assert outcome.human_recovery_required is True

    def test_returned_valid_construction(self):
        """returned+valid outcome can be constructed."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned", contract_valid=True)
        assert outcome.status == "returned"
        assert outcome.worker_call_attempted is True
        assert outcome.worker_returned is True
        assert outcome.worker_result_contract_valid is True
        assert outcome.human_recovery_required is False

    def test_returned_invalid_construction(self):
        """returned+invalid outcome can be constructed."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned", contract_valid=False)
        assert outcome.status == "returned"
        assert outcome.worker_call_attempted is True
        assert outcome.worker_returned is True
        assert outcome.worker_result_contract_valid is False
        assert outcome.human_recovery_required is True

    def test_raised_construction(self):
        """raised outcome can be constructed."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="raised")
        assert outcome.status == "raised"
        assert outcome.worker_call_attempted is True
        assert outcome.worker_raised is True
        assert outcome.human_recovery_required is True

    def test_frozen_immutability(self):
        """Outcome is frozen and cannot be modified."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        with pytest.raises(ValidationError):
            outcome.status = "raised"

    def test_tuple_deep_immutability(self):
        """Tuple fields on Outcome are deeply immutable."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        with pytest.raises((TypeError, AttributeError)):
            outcome.blocked_reasons.append("test")

    def test_json_round_trip(self):
        """Outcome survives JSON serialization round-trip."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        dumped = outcome.model_dump(mode="json")
        restored = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.model_validate(dumped)
        assert restored == outcome

    def test_replay_key_stable(self):
        """Outcome replay key is deterministic."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        computed = ProjectDirectorCrossTaskExactWorkerInvocationOutcome.compute_worker_invocation_outcome_replay_key(
            continuation_id=outcome.continuation_id,
            exact_worker_invocation_claim_id=outcome.exact_worker_invocation_claim_id,
            exact_worker_invocation_claim_token=outcome.exact_worker_invocation_claim_token,
            exact_worker_start_reservation_id=outcome.exact_worker_start_reservation_id,
            next_task_id=outcome.next_task_id,
            exact_run_id=outcome.exact_run_id,
        )
        assert computed == outcome.worker_invocation_outcome_replay_key

    def test_fingerprint_stable(self):
        """Outcome fingerprint is deterministic."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        computed = outcome.compute_fingerprint()
        assert computed == outcome.worker_invocation_outcome_fingerprint

    def test_sequence_no_5(self):
        """Outcome has continuation_sequence_no=5."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        assert outcome.continuation_sequence_no == 5

    def test_previous_record_id_is_claim_id(self):
        """Outcome previous_record_id equals Claim ID."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        assert outcome.previous_record_id == chain.claim.exact_worker_invocation_claim_id

    def test_worker_call_state_indeterminate_false(self):
        """Outcome has worker_call_state_indeterminate=False."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        assert outcome.worker_call_state_indeterminate is False


class TestOutcomeResult:
    """Outcome Result contract tests - four states."""

    def test_outcome_recorded(self):
        """outcome_recorded result is valid."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        result = ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="outcome_recorded",
            exact_worker_invocation_claim_id=chain.claim_id,
            outcome=outcome,
            blocked_reasons=(),
            outcome_recorded=True,
            outcome_replayed=False,
            resumed_from_existing_outcome=False,
            recovery_required=False,
            automatic_worker_call_allowed=False,
            worker_call_attempted=True,
            worker_call_state_indeterminate=False,
            product_runtime_git_write_allowed=False,
        )
        assert result.status == "outcome_recorded"
        assert result.outcome is not None

    def test_outcome_replayed(self):
        """outcome_replayed result is valid."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(chain, status="returned")
        result = ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="outcome_replayed",
            exact_worker_invocation_claim_id=chain.claim_id,
            outcome=outcome,
            blocked_reasons=(),
            outcome_recorded=False,
            outcome_replayed=True,
            resumed_from_existing_outcome=True,
            recovery_required=False,
            automatic_worker_call_allowed=False,
            worker_call_attempted=True,
            worker_call_state_indeterminate=False,
            product_runtime_git_write_allowed=False,
        )
        assert result.status == "outcome_replayed"
        assert result.resumed_from_existing_outcome is True

    def test_recovery_required(self):
        """recovery_required result is valid."""
        chain = build_p24_chain()
        result = ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="recovery_required",
            exact_worker_invocation_claim_id=chain.claim_id,
            outcome=None,
            blocked_reasons=("exact_worker_invocation_outcome_claim_without_outcome_recovery_required",),
            outcome_recorded=False,
            outcome_replayed=False,
            resumed_from_existing_outcome=False,
            recovery_required=True,
            automatic_worker_call_allowed=False,
            worker_call_attempted=None,
            worker_call_state_indeterminate=True,
            product_runtime_git_write_allowed=False,
        )
        assert result.status == "recovery_required"
        assert result.outcome is None
        assert result.worker_call_state_indeterminate is True

    def test_blocked(self):
        """blocked result is valid."""
        result = ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(
            status="blocked",
            exact_worker_invocation_claim_id=None,
            outcome=None,
            blocked_reasons=("exact_worker_invocation_outcome_claim_invalid",),
            outcome_recorded=False,
            outcome_replayed=False,
            resumed_from_existing_outcome=False,
            recovery_required=False,
            automatic_worker_call_allowed=False,
            worker_call_attempted=False,
            worker_call_state_indeterminate=False,
            product_runtime_git_write_allowed=False,
        )
        assert result.status == "blocked"
        assert result.recovery_required is False


# ── Sensitive Text Tests ────────────────────────────────────────────


class TestSensitiveText:
    """Sensitive text rejection tests."""

    def test_bearer_token_rejected(self):
        """Outcome rejects Bearer token in text fields."""
        chain = build_p24_chain()
        with pytest.raises(ValidationError, match="sensitive"):
            build_valid_outcome(
                chain,
                status="returned",
                worker_result_message="Authorization: Bearer secret-value-12345",
            )

    def test_api_key_rejected(self):
        """Outcome rejects api_key in text fields."""
        chain = build_p24_chain()
        with pytest.raises(ValidationError, match="sensitive"):
            build_valid_outcome(
                chain,
                status="returned",
                worker_result_message="api_key=abc123def456",
            )

    def test_password_rejected(self):
        """Outcome rejects password in text fields."""
        chain = build_p24_chain()
        with pytest.raises(ValidationError, match="sensitive"):
            build_valid_outcome(
                chain,
                status="returned",
                worker_result_message="password=secret123",
            )

    def test_token_rejected(self):
        """Outcome rejects token assignment in text fields."""
        chain = build_p24_chain()
        with pytest.raises(ValidationError, match="sensitive"):
            build_valid_outcome(
                chain,
                status="returned",
                worker_result_message="token=abc123",
            )

    def test_provider_credential_rejected(self):
        """Outcome rejects provider_credential in text fields."""
        chain = build_p24_chain()
        with pytest.raises(ValidationError, match="sensitive"):
            build_valid_outcome(
                chain,
                status="returned",
                worker_result_message="provider_credential=abc123",
            )

    def test_safe_text_accepted(self):
        """Outcome accepts safe text."""
        chain = build_p24_chain()
        outcome = build_valid_outcome(
            chain,
            status="returned",
            worker_result_message="Worker completed successfully",
        )
        assert outcome.worker_result_message == "Worker completed successfully"
