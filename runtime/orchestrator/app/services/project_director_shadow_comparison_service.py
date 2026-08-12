"""Non-writing shadow comparison between the Legacy Director and the runtime.

This service compares the governed Legacy DirectorResponseEnvelope with a
DirectorRuntimeSupervisionOutcome and returns a bounded, diagnostic-only
summary. It is pure and side-effect free: it never admits, applies, reduces,
or executes a candidate, it performs no state mutation, and a runtime failure
never becomes a Legacy failure. The Legacy chain remains the sole serving and
authoritative path; a shadow result is an observation only.
"""

from __future__ import annotations

from typing import Any

from app.domain.project_director_conversation_intelligence import (
    DirectorResponseEnvelope,
)
from app.domain.project_director_discussion import DiscussionDeltaOperationType
from app.domain.project_director_shadow_comparison import (
    DirectorShadowComparisonResult,
    LegacyShadowObservationMetadata,
    ShadowComparisonDifference,
    ShadowComparisonDimensionStatus,
    ShadowComparisonError,
    ShadowRuntimeFailureSummary,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeSupervisionOutcome,
)

_DIMENSION_ORDER: tuple[str, ...] = (
    "conversation_mode",
    "formal_action_requested",
    "hypothetical_action",
    "discussion_lifecycle",
    "discussion_delta",
    "formalization",
    "response",
    "runtime_attempt_state",
    "duration",
    "usage",
)

_KNOWN_DELTA_OPERATION_TYPES: frozenset[str] = frozenset(
    member.value for member in DiscussionDeltaOperationType
)

_SUMMARY_LIMIT = 250
_DELTA_TYPE_SUMMARY_LIMIT = 16
_UNKNOWN_DELTA_OP = "unknown_op"
_ABSENT = "absent"


class ProjectDirectorShadowComparisonService:
    """Compare one Legacy envelope with one supervised runtime outcome.

    The comparison is deterministic and diagnostic only. ``semantic_match``
    merely states that every comparable dimension matched; it does not mean
    the runtime output is correct, approved, or allowed to write. Missing
    optional metadata marks a dimension not comparable instead of forcing a
    mismatch, and request correlation fails closed.
    """

    def compare(
        self,
        *,
        expected_request_id: str,
        legacy_envelope: DirectorResponseEnvelope,
        runtime_outcome: DirectorRuntimeSupervisionOutcome,
        legacy_observation: LegacyShadowObservationMetadata | None = None,
    ) -> DirectorShadowComparisonResult:
        """Return one bounded shadow diagnostic without any state mutation."""

        if (
            not isinstance(expected_request_id, str)
            or not expected_request_id.strip()
            or len(expected_request_id) > 256
        ):
            raise ShadowComparisonError("shadow_comparison_request_id_invalid")
        if not isinstance(legacy_envelope, DirectorResponseEnvelope):
            raise ShadowComparisonError("shadow_comparison_input_invalid")
        if not isinstance(runtime_outcome, DirectorRuntimeSupervisionOutcome):
            raise ShadowComparisonError("shadow_comparison_input_invalid")
        if runtime_outcome.request_id != expected_request_id:
            raise ShadowComparisonError("shadow_comparison_request_id_mismatch")

        if runtime_outcome.candidate is None or runtime_outcome.error is not None:
            return self._failure_result(runtime_outcome)
        return self._comparison_result(
            expected_request_id=expected_request_id,
            legacy_envelope=legacy_envelope,
            runtime_outcome=runtime_outcome,
            legacy_observation=legacy_observation,
        )

    @staticmethod
    def _failure_result(
        outcome: DirectorRuntimeSupervisionOutcome,
    ) -> DirectorShadowComparisonResult:
        """Describe a supervised runtime failure without unsafe detail."""

        error = outcome.error
        if error is not None:
            failure_summary = ShadowRuntimeFailureSummary(
                attempt_state=str(outcome.attempt_state.value),
                code=error.code[:128],
                stage=str(error.stage),
                retryable=error.retryable,
            )
        else:
            failure_summary = ShadowRuntimeFailureSummary(
                attempt_state=str(outcome.attempt_state.value),
                code="shadow_comparison_runtime_candidate_unsupervised",
                stage="runtime",
                retryable=False,
            )
        return DirectorShadowComparisonResult(
            request_id=outcome.request_id,
            runtime_failed=True,
            semantic_match=False,
            differences=(),
            compared_dimensions=(),
            unavailable_dimensions=_DIMENSION_ORDER,
            runtime_failure_summary=failure_summary,
        )

    @classmethod
    def _comparison_result(
        cls,
        *,
        expected_request_id: str,
        legacy_envelope: DirectorResponseEnvelope,
        runtime_outcome: DirectorRuntimeSupervisionOutcome,
        legacy_observation: LegacyShadowObservationMetadata | None,
    ) -> DirectorShadowComparisonResult:
        outcome_candidate = runtime_outcome.candidate
        assert outcome_candidate is not None  # guaranteed by the caller

        differences: list[ShadowComparisonDifference] = []
        compared: list[str] = []
        unavailable: list[str] = []

        def record(
            dimension: str,
            matches: bool,
            legacy_summary: str,
            runtime_summary: str,
        ) -> None:
            compared.append(dimension)
            if not matches:
                differences.append(
                    ShadowComparisonDifference(
                        dimension=dimension,
                        status=ShadowComparisonDimensionStatus.MISMATCH,
                        legacy_summary=_bounded(legacy_summary),
                        runtime_summary=_bounded(runtime_summary),
                    )
                )

        interpretation = legacy_envelope.turn_interpretation
        legacy_mode = interpretation.conversation_mode.value
        runtime_mode = outcome_candidate.turn_semantics.conversation_mode.strip()
        record(
            "conversation_mode",
            legacy_mode == runtime_mode,
            legacy_mode,
            runtime_mode,
        )
        record(
            "formal_action_requested",
            interpretation.formal_action_requested
            == outcome_candidate.turn_semantics.formal_action_requested,
            _flag(interpretation.formal_action_requested),
            _flag(outcome_candidate.turn_semantics.formal_action_requested),
        )
        record(
            "hypothetical_action",
            interpretation.hypothetical_action
            == outcome_candidate.turn_semantics.hypothetical_action,
            _flag(interpretation.hypothetical_action),
            _flag(outcome_candidate.turn_semantics.hypothetical_action),
        )

        if (
            legacy_observation is None
            or legacy_observation.discussion_observed_status is None
            or legacy_observation.discussion_suggested_next_status is None
        ):
            unavailable.append("discussion_lifecycle")
        else:
            legacy_observed = legacy_observation.discussion_observed_status.strip()
            legacy_next = legacy_observation.discussion_suggested_next_status.strip()
            runtime_observed = _normalize_status(
                outcome_candidate.discussion_lifecycle.observed_status
            )
            runtime_next = _normalize_status(
                outcome_candidate.discussion_lifecycle.suggested_next_status
            )
            record(
                "discussion_lifecycle",
                (legacy_observed, legacy_next) == (runtime_observed, runtime_next),
                f"observed={legacy_observed};next={legacy_next}",
                f"observed={runtime_observed or _ABSENT};"
                f"next={runtime_next or _ABSENT}",
            )

        legacy_operations = legacy_envelope.discussion_delta.operations
        legacy_count = len(legacy_operations)
        legacy_types = tuple(operation.op.value for operation in legacy_operations)
        runtime_kind, runtime_count, runtime_types = _summarize_runtime_delta(
            outcome_candidate.discussion_delta_candidate
        )
        if runtime_kind == "unknown_shape":
            unavailable.append("discussion_delta")
        else:
            record(
                "discussion_delta",
                legacy_count == runtime_count
                and (legacy_count == 0 or legacy_types == runtime_types),
                _delta_summary(legacy_count, legacy_types),
                _delta_summary(runtime_count, runtime_types),
            )

        legacy_formalization_state = _legacy_formalization_state(legacy_envelope)
        runtime_formalization_state = _runtime_formalization_state(outcome_candidate)
        record(
            "formalization",
            legacy_formalization_state == runtime_formalization_state,
            legacy_formalization_state,
            runtime_formalization_state,
        )

        legacy_response_bucket = _response_length_bucket(legacy_envelope.answer)
        runtime_response_bucket = _response_length_bucket(
            outcome_candidate.response_text
        )
        record(
            "response",
            legacy_response_bucket == runtime_response_bucket,
            f"length_bucket={legacy_response_bucket}",
            f"length_bucket={runtime_response_bucket}",
        )

        runtime_attempt_state = str(runtime_outcome.attempt_state.value)
        if legacy_observation is not None and legacy_observation.attempt_state is not None:
            legacy_attempt_state = legacy_observation.attempt_state.strip()
            record(
                "runtime_attempt_state",
                legacy_attempt_state == runtime_attempt_state,
                legacy_attempt_state,
                runtime_attempt_state,
            )
        else:
            unavailable.append("runtime_attempt_state")

        if legacy_observation is not None and legacy_observation.duration_ms is not None:
            legacy_duration_bucket = _duration_bucket(legacy_observation.duration_ms)
            runtime_duration_bucket = _duration_bucket(
                outcome_candidate.runtime_metadata.duration_ms
            )
            record(
                "duration",
                legacy_duration_bucket == runtime_duration_bucket,
                f"duration_bucket={legacy_duration_bucket}",
                f"duration_bucket={runtime_duration_bucket}",
            )
        else:
            unavailable.append("duration")

        if legacy_observation is not None and legacy_observation.usage_keys is not None:
            legacy_usage_keys = tuple(
                sorted(key.strip().lower() for key in legacy_observation.usage_keys)
            )
            runtime_usage_keys = tuple(
                sorted(
                    key.strip().lower()
                    for key in outcome_candidate.runtime_metadata.usage
                )
            )
            record(
                "usage",
                legacy_usage_keys == runtime_usage_keys,
                f"usage_keys={','.join(legacy_usage_keys) or 'none'}",
                f"usage_keys={','.join(runtime_usage_keys) or 'none'}",
            )
        else:
            unavailable.append("usage")

        return DirectorShadowComparisonResult(
            request_id=expected_request_id,
            runtime_failed=False,
            semantic_match=not differences,
            differences=tuple(differences),
            compared_dimensions=tuple(compared),
            unavailable_dimensions=tuple(unavailable),
            runtime_failure_summary=None,
        )


def _bounded(value: str) -> str:
    return value[:_SUMMARY_LIMIT]


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _normalize_status(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return _bounded(stripped)
    return None


def _response_length_bucket(text: str) -> str:
    """Fixed deterministic buckets; full text never leaves the comparison."""

    length = len(text)
    if length == 0:
        return "empty"
    if length <= 512:
        return "short"
    if length <= 4096:
        return "medium"
    return "long"


def _duration_bucket(duration_ms: float) -> str:
    if duration_ms < 1000:
        return "under_1s"
    if duration_ms < 10000:
        return "under_10s"
    return "at_least_10s"


def _legacy_formalization_state(envelope: DirectorResponseEnvelope) -> str:
    if envelope.formalization_proposal is not None:
        return "proposal_requires_confirmation"
    if envelope.requires_confirmation:
        return "confirmation_without_proposal"
    return "no_proposal"


def _runtime_formalization_state(candidate: Any) -> str:
    formalization = candidate.formalization
    proposal_present = formalization.proposal_candidate is not None
    readiness = formalization.readiness
    if readiness == "not_ready" and not proposal_present:
        return "no_proposal"
    if readiness == "requires_confirmation" and proposal_present:
        return "proposal_requires_confirmation"
    if readiness == "candidate" and proposal_present:
        return "candidate_only"
    return "inconsistent_shape"


def _summarize_runtime_delta(candidate: Any) -> tuple[str, int, tuple[str, ...]]:
    """Summarize the runtime delta candidate shape without admitting it.

    Returns (kind, operation_count, operation_types) where kind is one of
    ``absent``, ``no_operations``, ``operations``, or ``unknown_shape``.
    """

    if candidate is None:
        return ("absent", 0, ())
    if not isinstance(candidate, dict):
        return ("unknown_shape", 0, ())
    if "operations" not in candidate:
        return ("no_operations", 0, ())
    operations = candidate["operations"]
    if not isinstance(operations, list):
        return ("unknown_shape", 0, ())
    types: list[str] = []
    for item in operations:
        if isinstance(item, dict):
            op = item.get("op")
            if isinstance(op, str) and op in _KNOWN_DELTA_OPERATION_TYPES:
                types.append(op)
                continue
        types.append(_UNKNOWN_DELTA_OP)
    return ("operations", len(operations), tuple(types))


def _delta_summary(count: int, types: tuple[str, ...]) -> str:
    shown = ",".join(types[:_DELTA_TYPE_SUMMARY_LIMIT]) or "none"
    if len(types) > _DELTA_TYPE_SUMMARY_LIMIT:
        shown += ",..."
    return _bounded(f"operations={count};types={shown}")


__all__ = ("ProjectDirectorShadowComparisonService",)
