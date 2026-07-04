"""Strict in-memory validation for P21-C-H readonly reviewer output."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError

from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffReviewFinding,
    ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult,
    ProjectDirectorSandboxCandidateDiffValidatedReviewOutput,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


TOP_LEVEL_KEYS = {
    "review_status",
    "verdict",
    "risk_level",
    "summary",
    "findings",
    "recommended_next_step",
}
FINDING_KEYS = {
    "finding_id",
    "severity",
    "title",
    "summary",
    "evidence_paths",
    "recommended_action",
}
MARKDOWN_FENCE = "```"


class DuplicateJsonKeyError(ValueError):
    """Raised when a JSON object contains duplicate keys at any depth."""


class ProjectDirectorSandboxCandidateDiffReviewOutputValidationService:
    """Validate raw reviewer stdout text without starting reviewers or providers."""

    def validate_raw_review_output(
        self,
        *,
        raw_output_text: str,
        review_scope_paths: list[str],
        review_output_schema_version: str = REVIEW_OUTPUT_SCHEMA_VERSION,
        max_review_output_bytes: int = 200_000,
    ) -> ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult:
        """Return trusted structured output only when every contract check passes."""

        raw_text = raw_output_text if isinstance(raw_output_text, str) else ""
        raw_bytes = raw_text.encode("utf-8")
        raw_output_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        raw_output_bytes = len(raw_bytes)
        blocked_reasons: list[str] = []

        if max_review_output_bytes <= 0:
            raise ValueError("max_review_output_bytes must be positive")

        if review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION:
            self._append_reason(
                blocked_reasons,
                "review_output_schema_version_mismatch",
            )
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                blocked_reasons=blocked_reasons,
            )

        if not raw_text.strip():
            self._append_reason(blocked_reasons, "review_output_missing")
        if not self._review_scope_paths_valid(review_scope_paths):
            self._append_reason(blocked_reasons, "review_scope_paths_invalid")
        if raw_output_bytes > max_review_output_bytes:
            self._append_reason(blocked_reasons, "review_output_too_large")

        if blocked_reasons:
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                blocked_reasons=blocked_reasons,
            )

        stripped_output = raw_text.strip()
        if MARKDOWN_FENCE in stripped_output:
            self._append_reason(
                blocked_reasons,
                "review_output_markdown_fence_forbidden",
            )
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                blocked_reasons=blocked_reasons,
            )

        strict_json_valid = False
        try:
            parsed_output = json.loads(
                stripped_output,
                object_pairs_hook=self._reject_duplicate_json_keys,
            )
            strict_json_valid = True
        except DuplicateJsonKeyError:
            self._append_reason(
                blocked_reasons,
                "review_output_duplicate_json_key",
            )
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                blocked_reasons=blocked_reasons,
            )
        except json.JSONDecodeError:
            self._append_reason(
                blocked_reasons,
                "review_output_not_strict_json",
            )
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                blocked_reasons=blocked_reasons,
            )

        if not isinstance(parsed_output, dict):
            self._append_reason(
                blocked_reasons,
                "review_output_top_level_not_object",
            )
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                strict_json_valid=strict_json_valid,
                blocked_reasons=blocked_reasons,
            )

        self._validate_top_level_schema(parsed_output, blocked_reasons)
        self._validate_findings_schema(parsed_output, blocked_reasons)

        if blocked_reasons:
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                strict_json_valid=strict_json_valid,
                blocked_reasons=blocked_reasons,
            )

        try:
            validated_output = (
                ProjectDirectorSandboxCandidateDiffValidatedReviewOutput
                .model_validate(parsed_output)
            )
            schema_valid = True
        except ValidationError:
            self._append_reason(
                blocked_reasons,
                "review_output_schema_invalid",
            )
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                strict_json_valid=strict_json_valid,
                blocked_reasons=blocked_reasons,
            )

        semantics_valid = self._validate_review_semantics(
            validated_output,
            blocked_reasons,
        )
        evidence_scope_valid = self._validate_evidence_scope(
            validated_output,
            review_scope_paths,
            blocked_reasons,
        )

        if blocked_reasons:
            return self._blocked_result(
                review_output_schema_version=review_output_schema_version,
                raw_output_sha256=raw_output_sha256,
                raw_output_bytes=raw_output_bytes,
                strict_json_valid=strict_json_valid,
                schema_valid=schema_valid,
                semantics_valid=semantics_valid,
                evidence_scope_valid=evidence_scope_valid,
                blocked_reasons=blocked_reasons,
            )

        return ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult(
            validation_status="validated",
            review_output_schema_version=review_output_schema_version,
            raw_output_sha256=raw_output_sha256,
            raw_output_bytes=raw_output_bytes,
            strict_json_valid=True,
            schema_valid=True,
            semantics_valid=True,
            evidence_scope_valid=True,
            review_status=validated_output.review_status,
            verdict=validated_output.verdict,
            risk_level=validated_output.risk_level,
            summary=validated_output.summary,
            findings=validated_output.findings,
            recommended_next_step=validated_output.recommended_next_step,
            blocked_reasons=[],
        )

    @staticmethod
    def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise DuplicateJsonKeyError(key)
            seen.add(key)
            output[key] = value
        return output

    @staticmethod
    def _append_reason(blocked_reasons: list[str], reason: str) -> None:
        if reason not in blocked_reasons:
            blocked_reasons.append(reason)

    @staticmethod
    def _review_scope_paths_valid(review_scope_paths: list[str]) -> bool:
        if not isinstance(review_scope_paths, list) or not review_scope_paths:
            return False
        seen: set[str] = set()
        for review_scope_path in review_scope_paths:
            if (
                not isinstance(review_scope_path, str)
                or not review_scope_path
                or review_scope_path in seen
            ):
                return False
            seen.add(review_scope_path)
        return True

    def _validate_top_level_schema(
        self,
        parsed_output: dict[str, Any],
        blocked_reasons: list[str],
    ) -> None:
        output_keys = set(parsed_output)
        if output_keys - TOP_LEVEL_KEYS:
            self._append_reason(blocked_reasons, "review_output_extra_fields")
        if TOP_LEVEL_KEYS - output_keys:
            self._append_reason(blocked_reasons, "review_output_schema_invalid")

    def _validate_findings_schema(
        self,
        parsed_output: dict[str, Any],
        blocked_reasons: list[str],
    ) -> None:
        findings = parsed_output.get("findings")
        if not isinstance(findings, list):
            self._append_reason(blocked_reasons, "review_output_finding_invalid")
            return
        if len(findings) > 20:
            self._append_reason(blocked_reasons, "review_output_finding_invalid")

        finding_ids: set[str] = set()
        for finding in findings:
            if not isinstance(finding, dict):
                self._append_reason(
                    blocked_reasons,
                    "review_output_finding_invalid",
                )
                continue

            finding_keys = set(finding)
            if finding_keys - FINDING_KEYS:
                self._append_reason(
                    blocked_reasons,
                    "review_output_finding_extra_fields",
                )
            if FINDING_KEYS - finding_keys:
                self._append_reason(
                    blocked_reasons,
                    "review_output_finding_invalid",
                )

            finding_id = finding.get("finding_id")
            if isinstance(finding_id, str) and finding_id:
                if finding_id in finding_ids:
                    self._append_reason(
                        blocked_reasons,
                        "review_output_finding_id_duplicate",
                    )
                finding_ids.add(finding_id)

            evidence_paths = finding.get("evidence_paths")
            if not isinstance(evidence_paths, list) or not evidence_paths:
                self._append_reason(
                    blocked_reasons,
                    "review_output_evidence_paths_missing",
                )
            elif len(evidence_paths) > 12:
                self._append_reason(
                    blocked_reasons,
                    "review_output_finding_invalid",
                )

    def _validate_review_semantics(
        self,
        validated_output: ProjectDirectorSandboxCandidateDiffValidatedReviewOutput,
        blocked_reasons: list[str],
    ) -> bool:
        findings = validated_output.findings
        if validated_output.verdict == "non_blocking_findings" and not findings:
            self._append_reason(
                blocked_reasons,
                "review_output_findings_required_for_verdict",
            )
        if validated_output.verdict == "changes_required":
            if not findings:
                self._append_reason(
                    blocked_reasons,
                    "review_output_findings_required_for_verdict",
                )
            elif not any(
                finding.severity in {"medium", "high"} for finding in findings
            ):
                self._append_reason(
                    blocked_reasons,
                    "review_output_changes_required_severity_missing",
                )
        return not any(
            reason
            in {
                "review_output_findings_required_for_verdict",
                "review_output_changes_required_severity_missing",
            }
            for reason in blocked_reasons
        )

    def _validate_evidence_scope(
        self,
        validated_output: ProjectDirectorSandboxCandidateDiffValidatedReviewOutput,
        review_scope_paths: list[str],
        blocked_reasons: list[str],
    ) -> bool:
        review_scope_path_set = set(review_scope_paths)
        for finding in validated_output.findings:
            if not finding.evidence_paths:
                self._append_reason(
                    blocked_reasons,
                    "review_output_evidence_paths_missing",
                )
                continue

            seen_evidence_paths: set[str] = set()
            for evidence_path in finding.evidence_paths:
                if evidence_path in seen_evidence_paths:
                    self._append_reason(
                        blocked_reasons,
                        "review_output_evidence_path_duplicate",
                    )
                seen_evidence_paths.add(evidence_path)
                if evidence_path not in review_scope_path_set:
                    self._append_reason(
                        blocked_reasons,
                        "review_output_evidence_path_out_of_scope",
                    )
        return not any(
            reason
            in {
                "review_output_evidence_paths_missing",
                "review_output_evidence_path_duplicate",
                "review_output_evidence_path_out_of_scope",
            }
            for reason in blocked_reasons
        )

    @staticmethod
    def _blocked_result(
        *,
        review_output_schema_version: str,
        raw_output_sha256: str,
        raw_output_bytes: int,
        blocked_reasons: list[str],
        strict_json_valid: bool = False,
        schema_valid: bool = False,
        semantics_valid: bool = False,
        evidence_scope_valid: bool = False,
    ) -> ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult:
        return ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult(
            validation_status="blocked",
            review_output_schema_version=review_output_schema_version,
            raw_output_sha256=raw_output_sha256,
            raw_output_bytes=raw_output_bytes,
            strict_json_valid=strict_json_valid,
            schema_valid=schema_valid,
            semantics_valid=semantics_valid,
            evidence_scope_valid=evidence_scope_valid,
            review_status=None,
            verdict=None,
            risk_level=None,
            summary="",
            findings=[],
            recommended_next_step="",
            blocked_reasons=blocked_reasons,
        )


__all__ = (
    "ProjectDirectorSandboxCandidateDiffReviewOutputValidationService",
)
