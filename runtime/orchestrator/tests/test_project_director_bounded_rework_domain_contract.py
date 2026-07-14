"""Targeted contract tests for the P25-B bounded rework domain."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain.project_director_bounded_rework_contract import (
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    ProjectDirectorBoundedReworkCorrection,
    ProjectDirectorBoundedReworkFinding,
    ProjectDirectorBoundedReworkModelSelection,
    ProjectDirectorBoundedReworkRepositoryBinding,
    ProjectDirectorBoundedReworkRoleSelection,
    ProjectDirectorBoundedReworkSkillSelection,
    ProjectDirectorBoundedReworkVerificationRequirement,
    ProjectDirectorBoundedReworkWorkspaceBinding,
    canonicalize_p25_contract_value,
    compute_p25_contract_sha256,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_attempt_reservation import (
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_invocation_claim import (
    ProjectDirectorBoundedReworkInvocationClaim,
)
from app.domain.project_director_bounded_rework_invocation_outcome import (
    ProjectDirectorBoundedReworkInvocationOutcome,
)


UTC_NOW = datetime(2026, 7, 14, 6, 0, tzinfo=timezone.utc)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64
COMMIT_A = "1" * 40


def _ids(count: int) -> tuple[UUID, ...]:
    return tuple(uuid4() for _ in range(count))


def authority_data() -> dict[str, object]:
    (
        session_id,
        project_id,
        source_task_id,
        source_run_id,
        review_id,
        disposition_id,
        summary_id,
        intent_id,
        consumption_id,
    ) = _ids(9)
    return {
        "session_id": session_id,
        "project_id": project_id,
        "source_task_id": source_task_id,
        "target_task_id": source_task_id,
        "source_run_id": source_run_id,
        "source_review_message_id": review_id,
        "source_review_fingerprint": SHA_A,
        "source_review_semantic_fingerprint": SHA_B,
        "source_disposition_message_id": disposition_id,
        "source_p22_summary_message_id": summary_id,
        "source_p23_dispatch_intent_id": intent_id,
        "source_p23_dispatch_intent_fingerprint": SHA_C,
        "source_p23_dispatch_consumption_id": consumption_id,
        "source_p23_dispatch_consumption_fingerprint": SHA_D,
        "disposition_type": "AUTO_REWORK",
        "route": "bounded_automatic_rework",
        "transition_kind": "BOUNDED_REWORK_GUARDRAIL",
        "transition_authority": "AUTOMATED_DISPOSITION",
    }


def authority(**overrides: object) -> ProjectDirectorBoundedReworkAuthorityEnvelope:
    data = authority_data()
    data.update(overrides)
    return ProjectDirectorBoundedReworkAuthorityEnvelope(**data)


def prepared_package_data(*, attempt_index: int = 0) -> dict[str, object]:
    auth = authority()
    previous = (
        {
            "previous_attempt_id": uuid4(),
            "previous_outcome_id": uuid4(),
            "previous_rework_attempt_index": attempt_index - 1,
            "previous_candidate_diff_sha256": SHA_E,
            "previous_review_semantic_fingerprint": SHA_F,
        }
        if attempt_index
        else {}
    )
    return {
        "package_id": uuid4(),
        "package_status": "prepared",
        "package_fingerprint": SHA_A,
        "package_replay_key": SHA_A,
        "created_at": UTC_NOW,
        "authority": auth,
        "review_verdict": "changes_required",
        "review_risk_level": "high",
        "review_summary": "The candidate requires a bounded correction.",
        "blocking_findings": (
            ProjectDirectorBoundedReworkFinding(
                finding_id="finding-1",
                severity="high",
                title="Unsafe state transition",
                summary="The transition is not guarded.",
                evidence_paths=("runtime/orchestrator/app/domain/example.py",),
                recommended_action="Add the missing guard.",
            ),
        ),
        "required_corrections": (
            ProjectDirectorBoundedReworkCorrection(
                correction_id="correction-1",
                source_finding_id="finding-1",
                instruction="Add and validate the missing transition guard.",
            ),
        ),
        "recommended_next_step_context": "Rework only the reviewed candidate.",
        "confirmed_acceptance_criteria": ("The transition rejects invalid state.",),
        "verification_requirements": (
            ProjectDirectorBoundedReworkVerificationRequirement(
                requirement_id="verify-1",
                description="Run the bounded contract test.",
            ),
        ),
        "allowed_scope_paths": ("runtime/orchestrator/app/domain/example.py",),
        "forbidden_scope_paths": ("runtime/orchestrator/app/services",),
        "repository_binding": ProjectDirectorBoundedReworkRepositoryBinding(
            repository_binding_id=uuid4(),
            project_id=auth.project_id,
            repository_root="/repo",
            repository_binding_fingerprint=SHA_E,
        ),
        "workspace_binding": ProjectDirectorBoundedReworkWorkspaceBinding(
            workspace_binding_id=uuid4(),
            project_id=auth.project_id,
            workspace_path="/sandbox/session/workspace",
            workspace_root="/sandbox",
            workspace_binding_fingerprint=SHA_F,
        ),
        "base_commit_sha": COMMIT_A,
        "base_snapshot_fingerprint": SHA_A,
        "source_candidate_diff_message_id": uuid4(),
        "source_candidate_diff_sha256": SHA_B,
        "source_candidate_diff_fingerprint": SHA_C,
        "selected_model": ProjectDirectorBoundedReworkModelSelection(
            model_name="codex",
            model_tier="reasoning",
        ),
        "selected_skills": (
            ProjectDirectorBoundedReworkSkillSelection(
                skill_code="backend",
                skill_name="Backend",
            ),
        ),
        "selected_role": ProjectDirectorBoundedReworkRoleSelection(
            role_code="programmer",
        ),
        "rework_attempt_index": attempt_index,
        "rework_attempt_limit": 3,
        "non_convergence_evidence": (),
        **previous,
    }


def prepared_package(**overrides: object) -> ProjectDirectorBoundedReworkInstructionPackage:
    data = prepared_package_data(
        attempt_index=int(overrides.pop("rework_attempt_index", 0))
    )
    data.update(overrides)
    data["package_replay_key"] = (
        ProjectDirectorBoundedReworkInstructionPackage.compute_package_replay_key(
            authority=data["authority"],
            source_candidate_diff_sha256=data["source_candidate_diff_sha256"],
            repository_binding_fingerprint=data[
                "repository_binding"
            ].repository_binding_fingerprint,
            workspace_binding_fingerprint=data[
                "workspace_binding"
            ].workspace_binding_fingerprint,
            base_commit_sha=data["base_commit_sha"],
            rework_attempt_index=data["rework_attempt_index"],
        )
    )
    draft = ProjectDirectorBoundedReworkInstructionPackage.model_construct(**data)
    data["package_fingerprint"] = draft.compute_fingerprint()
    return ProjectDirectorBoundedReworkInstructionPackage(**data)


def blocked_package() -> ProjectDirectorBoundedReworkInstructionPackage:
    data: dict[str, object] = {
        "package_id": uuid4(),
        "package_status": "blocked",
        "package_fingerprint": SHA_A,
        "package_replay_key": None,
        "created_at": UTC_NOW,
        "blocked_reasons": ("authority_invalid",),
        "blocked_summary": "The exact authority could not be reconstructed.",
    }
    draft = ProjectDirectorBoundedReworkInstructionPackage.model_construct(**data)
    data["package_fingerprint"] = draft.compute_fingerprint()
    return ProjectDirectorBoundedReworkInstructionPackage(**data)


def reservation_data(package: ProjectDirectorBoundedReworkInstructionPackage) -> dict[str, object]:
    auth = package.authority
    assert auth is not None
    return {
        "reservation_id": uuid4(),
        "reservation_fingerprint": SHA_A,
        "reservation_replay_key": SHA_A,
        "reservation_token": SHA_B,
        "created_at": UTC_NOW,
        "reservation_status": "reserved",
        "replay_state": "new",
        "package_id": package.package_id,
        "package_fingerprint": package.package_fingerprint,
        "package_replay_key": package.package_replay_key,
        "authority": auth,
        "exact_task_id": auth.source_task_id,
        "exact_run_id": auth.source_run_id,
        "rework_attempt_index": package.rework_attempt_index,
        "rework_attempt_limit": package.rework_attempt_limit,
        "workspace_binding_fingerprint": package.workspace_binding.workspace_binding_fingerprint,
        "base_commit_sha": package.base_commit_sha,
        "source_candidate_diff_sha256": package.source_candidate_diff_sha256,
    }


def reservation(package: ProjectDirectorBoundedReworkInstructionPackage | None = None, **overrides: object) -> ProjectDirectorBoundedReworkAttemptReservation:
    package = package or prepared_package()
    data = reservation_data(package)
    data.update(overrides)
    data["reservation_replay_key"] = (
        ProjectDirectorBoundedReworkAttemptReservation.compute_reservation_replay_key(
            package_id=data["package_id"],
            package_fingerprint=data["package_fingerprint"],
            authority=data["authority"],
            exact_task_id=data["exact_task_id"],
            exact_run_id=data["exact_run_id"],
            rework_attempt_index=data["rework_attempt_index"],
        )
    )
    draft = ProjectDirectorBoundedReworkAttemptReservation.model_construct(**data)
    data["reservation_fingerprint"] = draft.compute_fingerprint()
    return ProjectDirectorBoundedReworkAttemptReservation(**data)


def claim(res: ProjectDirectorBoundedReworkAttemptReservation | None = None, **overrides: object) -> ProjectDirectorBoundedReworkInvocationClaim:
    res = res or reservation()
    data: dict[str, object] = {
        "claim_id": uuid4(),
        "claim_fingerprint": SHA_A,
        "claim_replay_key": SHA_A,
        "claim_token": SHA_C,
        "created_at": UTC_NOW,
        "claim_status": "claimed",
        "reservation_id": res.reservation_id,
        "reservation_fingerprint": res.reservation_fingerprint,
        "reservation_token": res.reservation_token,
        "package_id": res.package_id,
        "package_fingerprint": res.package_fingerprint,
        "authority": res.authority,
        "exact_task_id": res.exact_task_id,
        "exact_run_id": res.exact_run_id,
        "rework_attempt_index": res.rework_attempt_index,
        "rework_attempt_limit": res.rework_attempt_limit,
        "executor_adapter_kind": "codex_sandbox",
        "selected_model": ProjectDirectorBoundedReworkModelSelection(
            model_name="codex", model_tier="reasoning"
        ),
        "selected_skills": (
            ProjectDirectorBoundedReworkSkillSelection(
                skill_code="backend", skill_name="Backend"
            ),
        ),
        "selected_role": ProjectDirectorBoundedReworkRoleSelection(
            role_code="programmer"
        ),
        "workspace_before_manifest_fingerprint": SHA_D,
        "workspace_before_content_fingerprint": SHA_E,
        "invocation_ordinal": 0,
    }
    data.update(overrides)
    data["claim_replay_key"] = (
        ProjectDirectorBoundedReworkInvocationClaim.compute_claim_replay_key(
            reservation_id=data["reservation_id"],
            reservation_token=data["reservation_token"],
            package_id=data["package_id"],
            exact_task_id=data["exact_task_id"],
            exact_run_id=data["exact_run_id"],
            invocation_ordinal=data["invocation_ordinal"],
        )
    )
    draft = ProjectDirectorBoundedReworkInvocationClaim.model_construct(**data)
    data["claim_fingerprint"] = draft.compute_fingerprint()
    return ProjectDirectorBoundedReworkInvocationClaim(**data)


def outcome(invocation_claim: ProjectDirectorBoundedReworkInvocationClaim | None = None, **overrides: object) -> ProjectDirectorBoundedReworkInvocationOutcome:
    invocation_claim = invocation_claim or claim()
    data: dict[str, object] = {
        "outcome_id": uuid4(),
        "outcome_fingerprint": SHA_A,
        "outcome_replay_key": SHA_A,
        "created_at": UTC_NOW,
        "outcome_status": "returned",
        "claim_id": invocation_claim.claim_id,
        "claim_fingerprint": invocation_claim.claim_fingerprint,
        "claim_token": invocation_claim.claim_token,
        "reservation_id": invocation_claim.reservation_id,
        "reservation_fingerprint": invocation_claim.reservation_fingerprint,
        "package_id": invocation_claim.package_id,
        "package_fingerprint": invocation_claim.package_fingerprint,
        "authority": invocation_claim.authority,
        "exact_task_id": invocation_claim.exact_task_id,
        "exact_run_id": invocation_claim.exact_run_id,
        "rework_attempt_index": invocation_claim.rework_attempt_index,
        "rework_attempt_limit": invocation_claim.rework_attempt_limit,
        "invocation_ordinal": invocation_claim.invocation_ordinal,
        "executor_attempted": True,
        "executor_started": True,
        "executor_returned": True,
        "executor_raised": False,
        "executor_result_valid": True,
        "safe_error_code": None,
        "redacted_error_summary": None,
        "workspace_before_manifest_fingerprint": SHA_D,
        "workspace_before_content_fingerprint": SHA_E,
        "workspace_after_manifest_fingerprint": SHA_A,
        "workspace_after_content_fingerprint": SHA_B,
        "declared_changed_paths": ("runtime/orchestrator/app/domain/example.py",),
        "observed_changed_paths": ("runtime/orchestrator/app/domain/example.py",),
        "scope_validation_status": "valid",
        "git_activity_detected": False,
        "git_activity_kinds": (),
        "side_effect_state": "observed",
        "candidate_manifest_id": uuid4(),
        "candidate_manifest_fingerprint": SHA_C,
        "candidate_files_changed": True,
        "recovery_required": False,
        "human_escalation_required": False,
    }
    data.update(overrides)
    data["outcome_replay_key"] = (
        ProjectDirectorBoundedReworkInvocationOutcome.compute_outcome_replay_key(
            claim_id=data["claim_id"],
            claim_token=data["claim_token"],
            reservation_id=data["reservation_id"],
            package_id=data["package_id"],
            exact_task_id=data["exact_task_id"],
            exact_run_id=data["exact_run_id"],
        )
    )
    draft = ProjectDirectorBoundedReworkInvocationOutcome.model_construct(**data)
    data["outcome_fingerprint"] = draft.compute_fingerprint()
    return ProjectDirectorBoundedReworkInvocationOutcome(**data)


def test_prepared_and_blocked_packages_construct_and_are_frozen() -> None:
    package = prepared_package()
    blocked = blocked_package()

    assert package.package_status == "prepared"
    assert blocked.package_status == "blocked"
    assert blocked.authority is None
    with pytest.raises(ValidationError):
        package.review_summary = "mutated"  # type: ignore[misc]


def test_reservation_claim_and_outcome_are_frozen() -> None:
    records = (reservation(), claim(), outcome())
    for record in records:
        with pytest.raises(ValidationError):
            record.created_at = UTC_NOW + timedelta(seconds=1)  # type: ignore[misc]


def test_authority_requires_exact_source_task_and_rejects_non_p25_inputs() -> None:
    data = authority_data()
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkAuthorityEnvelope(
            **{**data, "target_task_id": uuid4()}
        )
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkAuthorityEnvelope(
            **{**data, "disposition_type": "AUTO_CONTINUE"}
        )
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkAuthorityEnvelope(
            **{**data, "next_task_id": uuid4()}
        )
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkAuthorityEnvelope(
            **{**data, "p24_continuation_id": uuid4()}
        )


def test_authority_rejects_missing_and_duplicate_lineage() -> None:
    data = authority_data()
    data.pop("source_p22_summary_message_id")
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkAuthorityEnvelope(**data)

    data = authority_data()
    data["source_disposition_message_id"] = data["source_review_message_id"]
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkAuthorityEnvelope(**data)


@pytest.mark.parametrize("field", ["source_review_fingerprint", "base_snapshot_fingerprint"])
def test_hashes_must_be_lowercase_sha256(field: str) -> None:
    if field == "source_review_fingerprint":
        with pytest.raises(ValidationError):
            authority(**{field: "A" * 64})
    else:
        with pytest.raises(ValidationError):
            prepared_package(**{field: "A" * 64})


@pytest.mark.parametrize("value", ["A" * 40, "a" * 39, "g" * 40])
def test_base_commit_requires_lowercase_40_hex(value: str) -> None:
    with pytest.raises(ValidationError):
        prepared_package(base_commit_sha=value)


def test_replay_key_is_exact_and_fingerprint_is_recomputed() -> None:
    package = prepared_package()
    assert package.package_replay_key == package.compute_package_replay_key(
        authority=package.authority,
        source_candidate_diff_sha256=package.source_candidate_diff_sha256,
        repository_binding_fingerprint=package.repository_binding.repository_binding_fingerprint,
        workspace_binding_fingerprint=package.workspace_binding.workspace_binding_fingerprint,
        base_commit_sha=package.base_commit_sha,
        rework_attempt_index=package.rework_attempt_index,
    )
    assert package.package_fingerprint == package.compute_fingerprint()

    data = package.model_dump(mode="python")
    data["package_replay_key"] = SHA_F
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkInstructionPackage(**data)
    data = package.model_dump(mode="python")
    data["package_fingerprint"] = SHA_F
    with pytest.raises(ValidationError):
        ProjectDirectorBoundedReworkInstructionPackage(**data)


def test_semantic_change_changes_fingerprint_but_id_and_timestamp_do_not() -> None:
    package = prepared_package()
    changed_summary = package.model_copy(update={"review_summary": "Changed semantics"})
    changed_id = package.model_copy(update={"package_id": uuid4()})
    changed_time = package.model_copy(update={"created_at": UTC_NOW + timedelta(hours=1)})

    assert changed_summary.compute_fingerprint() != package.package_fingerprint
    assert changed_id.compute_fingerprint() == package.package_fingerprint
    assert changed_time.compute_fingerprint() == package.package_fingerprint


@pytest.mark.parametrize("index", [0, 1, 2])
def test_valid_attempt_indexes(index: int) -> None:
    assert prepared_package(rework_attempt_index=index).rework_attempt_index == index


@pytest.mark.parametrize("index", [-1, 3])
def test_invalid_attempt_indexes(index: int) -> None:
    with pytest.raises(ValidationError):
        prepared_package(rework_attempt_index=index)


def test_attempt_limit_and_previous_lineage_are_strict() -> None:
    with pytest.raises(ValidationError):
        prepared_package(rework_attempt_limit=4)
    with pytest.raises(ValidationError):
        prepared_package(rework_attempt_index=1, previous_outcome_id=None)
    with pytest.raises(ValidationError):
        prepared_package(rework_attempt_index=0, previous_attempt_id=uuid4())
    with pytest.raises(ValidationError):
        prepared_package(
            rework_attempt_index=2,
            previous_rework_attempt_index=0,
        )


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.py",
        "../escape.py",
        "src\\windows.py",
        ".git/config",
        "https://example.com/code.py",
        "src/code.py;rm",
    ],
)
def test_invalid_scope_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValidationError):
        prepared_package(allowed_scope_paths=(path,))


def test_duplicate_and_conflicting_scope_paths_are_rejected() -> None:
    path = "runtime/orchestrator/app/domain/example.py"
    with pytest.raises(ValidationError):
        prepared_package(allowed_scope_paths=(path, path))
    with pytest.raises(ValidationError):
        prepared_package(forbidden_scope_paths=("services", "services"))
    with pytest.raises(ValidationError):
        prepared_package(
            allowed_scope_paths=("runtime/orchestrator",),
            forbidden_scope_paths=("runtime/orchestrator/app/services",),
        )


def test_finding_correction_binding_and_evidence_scope_are_strict() -> None:
    correction = ProjectDirectorBoundedReworkCorrection(
        correction_id="correction-1",
        source_finding_id="unknown",
        instruction="Fix it.",
    )
    with pytest.raises(ValidationError):
        prepared_package(required_corrections=(correction,))

    finding = ProjectDirectorBoundedReworkFinding(
        finding_id="finding-1",
        severity="high",
        title="Outside scope",
        summary="Evidence is outside the effective scope.",
        evidence_paths=("apps/web/outside.ts",),
        recommended_action="Do not broaden scope.",
    )
    with pytest.raises(ValidationError):
        prepared_package(blocking_findings=(finding,))


def test_review_risk_and_previous_lineage_aliases_are_consistent() -> None:
    with pytest.raises(ValidationError):
        prepared_package(review_risk_level="medium")

    duplicate_id = uuid4()
    with pytest.raises(ValidationError):
        prepared_package(
            rework_attempt_index=1,
            previous_attempt_id=duplicate_id,
            previous_outcome_id=duplicate_id,
        )


def test_prepared_package_requires_blocking_findings() -> None:
    with pytest.raises(ValidationError):
        prepared_package(blocking_findings=(), required_corrections=())


def test_reservation_binds_exact_package_task_and_run() -> None:
    package = prepared_package()
    res = reservation(package)
    assert res.package_id == package.package_id
    assert res.exact_task_id == package.authority.source_task_id
    assert res.exact_run_id == package.authority.source_run_id
    with pytest.raises(ValidationError):
        reservation(package, exact_task_id=uuid4())
    with pytest.raises(ValidationError):
        reservation(package, exact_run_id=uuid4())


def test_claim_rejects_nonzero_invocation_ordinal() -> None:
    with pytest.raises(ValidationError):
        claim(invocation_ordinal=1)


def test_outcome_rejects_returned_raised_conflict() -> None:
    with pytest.raises(ValidationError):
        outcome(executor_raised=True)


def test_successful_outcome_rejects_git_activity() -> None:
    with pytest.raises(ValidationError):
        outcome(git_activity_detected=True, git_activity_kinds=("git_commit",))


def test_git_violation_requires_recovery_and_human_escalation() -> None:
    with pytest.raises(ValidationError):
        outcome(
            outcome_status="human_escalation_required",
            executor_result_valid=False,
            git_activity_detected=True,
            git_activity_kinds=("git_commit",),
            recovery_required=False,
            human_escalation_required=False,
        )

    escalated = outcome(
        outcome_status="human_escalation_required",
        executor_result_valid=False,
        git_activity_detected=True,
        git_activity_kinds=("git_commit",),
        recovery_required=True,
        human_escalation_required=True,
        safe_error_code="git_boundary_violation",
        redacted_error_summary="Repository control activity was detected.",
    )
    assert escalated.recovery_required
    assert escalated.human_escalation_required


def test_indeterminate_side_effect_requires_recovery() -> None:
    with pytest.raises(ValidationError):
        outcome(
            outcome_status="invalid_result",
            executor_result_valid=False,
            side_effect_state="indeterminate",
            recovery_required=False,
            safe_error_code="execution_result_invalid",
            redacted_error_summary="The result could not be validated.",
        )


@pytest.mark.parametrize(
    "factory,field",
    [
        (prepared_package, "product_runtime_git_write_allowed"),
        (prepared_package, "main_project_write_allowed"),
        (reservation, "git_commit_allowed"),
        (claim, "main_project_write_allowed"),
        (outcome, "git_push_allowed"),
    ],
)
def test_write_authority_flags_can_never_be_true(factory: object, field: str) -> None:
    with pytest.raises(ValidationError):
        factory(**{field: True})  # type: ignore[operator]


class CanonicalEnum(str, Enum):
    VALUE = "value"


def test_canonicalization_is_stable_for_uuid_enum_datetime_and_tuple() -> None:
    identity = UUID("12345678-1234-5678-1234-567812345678")
    instant = datetime(2026, 7, 14, 14, 0, tzinfo=timezone(timedelta(hours=8)))
    payload = {
        "identity": identity,
        "enum": CanonicalEnum.VALUE,
        "instant": instant,
        "items": ("alpha", "beta"),
    }
    assert canonicalize_p25_contract_value(payload) == {
        "identity": str(identity),
        "enum": "value",
        "instant": "2026-07-14T06:00:00Z",
        "items": ["alpha", "beta"],
    }
    assert compute_p25_contract_sha256(payload) == compute_p25_contract_sha256(
        dict(reversed(tuple(payload.items())))
    )
