"""Readonly reviewer adapter service for P21-C-H-B2-A.

Validates prompt integrity, invokes transport, and pipes raw output
through the H-B1 strict validator. Never starts real reviewers or providers.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportProtocol,
    ReadonlyReviewerTransportRequest,
    ReadonlyReviewerTransportRawResult,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)
from app.services.project_director_sandbox_candidate_diff_review_output_validation_service import (
    ProjectDirectorSandboxCandidateDiffReviewOutputValidationService,
)


_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_TRANSPORT_ERROR_TO_REASON = {
    "blocked": "reviewer_transport_blocked",
    "timeout": "reviewer_transport_timeout",
    "failed": "reviewer_transport_failed",
}


class ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService:
    """Validate prompt, invoke transport, and validate output through H-B1."""

    def __init__(
        self,
        *,
        output_validation_service: ProjectDirectorSandboxCandidateDiffReviewOutputValidationService
        | None = None,
    ) -> None:
        self._output_validation_service = (
            output_validation_service
            or ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
        )

    def validate_review_output_through_transport(
        self,
        *,
        requested_reviewer_executor: str,
        review_prompt_text: str,
        expected_review_prompt_sha256: str,
        expected_review_prompt_bytes: int,
        review_scope_paths: list[str],
        review_output_schema_version: str = REVIEW_OUTPUT_SCHEMA_VERSION,
        transport: ReadonlyReviewerTransportProtocol | None = None,
    ) -> ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult:
        """Full adapter seam: prompt check → transport → H-B1 validation."""

        blocked_reasons: list[str] = []

        # ── Prompt integrity ──────────────────────────────────────────

        prompt_verified = False
        actual_prompt_sha256 = ""
        actual_prompt_bytes = 0

        if not review_prompt_text or not isinstance(review_prompt_text, str):
            blocked_reasons.append("review_prompt_missing")
        else:
            prompt_bytes = review_prompt_text.encode("utf-8")
            actual_prompt_bytes = len(prompt_bytes)
            actual_prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()

            if actual_prompt_bytes != expected_review_prompt_bytes:
                blocked_reasons.append("review_prompt_bytes_mismatch")
            if not _LOWER_HEX_SHA256.match(expected_review_prompt_sha256):
                blocked_reasons.append("review_prompt_sha256_invalid")
            elif actual_prompt_sha256 != expected_review_prompt_sha256:
                blocked_reasons.append("review_prompt_sha256_mismatch")

            if not blocked_reasons:
                prompt_verified = True

        # ── Review scope ──────────────────────────────────────────────

        if not self._review_scope_paths_valid(review_scope_paths):
            blocked_reasons.append("review_scope_paths_invalid")

        # ── Schema version ────────────────────────────────────────────

        if review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION:
            blocked_reasons.append("review_output_schema_version_mismatch")

        # ── Transport configured ──────────────────────────────────────

        if transport is None:
            blocked_reasons.append("reviewer_transport_not_configured")

        if blocked_reasons:
            return self._blocked_result(
                requested_reviewer_executor=requested_reviewer_executor,
                prompt_verified=prompt_verified,
                actual_prompt_sha256=actual_prompt_sha256,
                actual_prompt_bytes=actual_prompt_bytes,
                review_scope_paths=review_scope_paths,
                review_output_schema_version=review_output_schema_version,
                blocked_reasons=blocked_reasons,
            )

        # ── Transport call ────────────────────────────────────────────

        assert transport is not None  # already checked above
        transport_request = ReadonlyReviewerTransportRequest(
            requested_reviewer_executor=requested_reviewer_executor,
            review_prompt_text=review_prompt_text,
            review_prompt_sha256=actual_prompt_sha256,
            review_prompt_bytes=actual_prompt_bytes,
            review_scope_paths=list(review_scope_paths),
            review_output_schema_version=review_output_schema_version,
        )
        transport_result = transport.execute(transport_request)

        # ── Transport status ──────────────────────────────────────────

        if transport_result.transport_status != "completed":
            reason = _TRANSPORT_ERROR_TO_REASON.get(
                transport_result.transport_status, "reviewer_transport_failed"
            )
            blocked_reasons.append(reason)
            return self._blocked_result(
                requested_reviewer_executor=requested_reviewer_executor,
                prompt_verified=prompt_verified,
                actual_prompt_sha256=actual_prompt_sha256,
                actual_prompt_bytes=actual_prompt_bytes,
                review_scope_paths=review_scope_paths,
                review_output_schema_version=review_output_schema_version,
                transport_invoked=transport_result.transport_invoked,
                transport_status=transport_result.transport_status,
                transport_error_code=transport_result.transport_error_code,
                blocked_reasons=blocked_reasons,
            )

        # ── H-B1 validation ───────────────────────────────────────────

        validation_result = self._output_validation_service.validate_raw_review_output(
            raw_output_text=transport_result.raw_output_text,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
        )

        if validation_result.validation_status == "blocked":
            blocked_reasons.append("review_output_validation_blocked")
            return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
                adapter_status="blocked",
                execution_mode="fake_transport",
                requested_reviewer_executor=requested_reviewer_executor,
                review_prompt_verified=prompt_verified,
                review_prompt_sha256=actual_prompt_sha256,
                review_prompt_bytes=actual_prompt_bytes,
                review_scope_paths=list(review_scope_paths),
                review_output_schema_version=review_output_schema_version,
                transport_invoked=transport_result.transport_invoked,
                transport_status=transport_result.transport_status,
                transport_error_code=transport_result.transport_error_code,
                output_validation_status="blocked",
                raw_output_sha256=validation_result.raw_output_sha256,
                raw_output_bytes=validation_result.raw_output_bytes,
                strict_json_valid=validation_result.strict_json_valid,
                schema_valid=validation_result.schema_valid,
                semantics_valid=validation_result.semantics_valid,
                evidence_scope_valid=validation_result.evidence_scope_valid,
                output_validation_blocked_reasons=list(
                    validation_result.blocked_reasons
                ),
                blocked_reasons=blocked_reasons,
            )

        # ── Validated ─────────────────────────────────────────────────

        return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
            adapter_status="validated_output",
            execution_mode="fake_transport",
            requested_reviewer_executor=requested_reviewer_executor,
            review_prompt_verified=prompt_verified,
            review_prompt_sha256=actual_prompt_sha256,
            review_prompt_bytes=actual_prompt_bytes,
            review_scope_paths=list(review_scope_paths),
            review_output_schema_version=review_output_schema_version,
            transport_invoked=transport_result.transport_invoked,
            transport_status=transport_result.transport_status,
            transport_error_code=transport_result.transport_error_code,
            output_validation_status="validated",
            raw_output_sha256=validation_result.raw_output_sha256,
            raw_output_bytes=validation_result.raw_output_bytes,
            strict_json_valid=validation_result.strict_json_valid,
            schema_valid=validation_result.schema_valid,
            semantics_valid=validation_result.semantics_valid,
            evidence_scope_valid=validation_result.evidence_scope_valid,
            review_status=validation_result.review_status,
            verdict=validation_result.verdict,
            risk_level=validation_result.risk_level,
            summary=validation_result.summary,
            findings=validation_result.findings,
            recommended_next_step=validation_result.recommended_next_step,
            output_validation_blocked_reasons=[],
            blocked_reasons=[],
        )

    @staticmethod
    def _review_scope_paths_valid(review_scope_paths: list[str]) -> bool:
        if not isinstance(review_scope_paths, list) or not review_scope_paths:
            return False
        seen: set[str] = set()
        for path in review_scope_paths:
            if not isinstance(path, str) or not path or path in seen:
                return False
            seen.add(path)
        return True

    @staticmethod
    def _review_scope_paths_for_blocked_result(
        review_scope_paths: list[str],
    ) -> list[str]:
        if not isinstance(review_scope_paths, list):
            return []
        return [path for path in review_scope_paths if isinstance(path, str)]

    @staticmethod
    def _blocked_result(
        *,
        requested_reviewer_executor: str,
        prompt_verified: bool,
        actual_prompt_sha256: str,
        actual_prompt_bytes: int,
        review_scope_paths: list[str],
        review_output_schema_version: str,
        transport_invoked: bool = False,
        transport_status: str = "",
        transport_error_code: str | None = None,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult:
        return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
            adapter_status="blocked",
            execution_mode="fake_transport",
            requested_reviewer_executor=requested_reviewer_executor,
            review_prompt_verified=prompt_verified,
            review_prompt_sha256=actual_prompt_sha256,
            review_prompt_bytes=actual_prompt_bytes,
            review_scope_paths=(
                ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService
                ._review_scope_paths_for_blocked_result(review_scope_paths)
            ),
            review_output_schema_version=review_output_schema_version,
            transport_invoked=transport_invoked,
            transport_status=transport_status,
            transport_error_code=transport_error_code,
            output_validation_status=None,
            review_status=None,
            verdict=None,
            risk_level=None,
            summary="",
            findings=[],
            recommended_next_step="",
            blocked_reasons=blocked_reasons,
        )


__all__ = ("ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService",)
