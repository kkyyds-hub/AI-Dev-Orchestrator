"""Readonly adapter for exact persisted completion-delivery evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.domain._base import ensure_utc_datetime
from app.domain.deliverable import Deliverable, DeliverableVersion
from app.domain.project_director_source_completion_delivery_evidence import (
    ProjectDirectorSourceCompletionDeliveryEvidence,
    SOURCE_COMPLETION_DELIVERY_EVIDENCE_KIND,
    SOURCE_COMPLETION_DELIVERY_EVIDENCE_SCHEMA_VERSION,
    SourceCompletionDeliveryEvidenceResolution,
)
from app.repositories.deliverable_repository import DeliverableRepository


_FORBIDDEN_ACTIONS = [
    "no_deliverable_creation_or_mutation",
    "no_deliverable_version_creation_or_mutation",
    "no_task_run_or_agent_session_write",
    "no_worker_or_provider_call",
    "no_product_runtime_git_write",
]


class ProjectDirectorSourceCompletionDeliveryEvidenceAdapter:
    """Reconstruct one caller-declared DeliverableVersion without selection."""

    def __init__(self, *, deliverable_repository: DeliverableRepository) -> None:
        self._deliverable_repository = deliverable_repository

    def resolve_required_completion_delivery(
        self,
        *,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        declared_delivery_evidence_ids: list[UUID],
        allowed_delivery_evidence_kinds: list[str],
    ) -> SourceCompletionDeliveryEvidenceResolution:
        """Resolve an exact project/Task/Run-bound immutable version."""

        allowed_kinds = list(allowed_delivery_evidence_kinds)
        if (
            allowed_kinds != [SOURCE_COMPLETION_DELIVERY_EVIDENCE_KIND]
            or len(allowed_kinds) != len(set(allowed_kinds))
        ):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_evidence_kind_unsupported"
            )
        if not declared_delivery_evidence_ids:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_evidence_missing"
            )
        if (
            len(declared_delivery_evidence_ids) != 2
            or any(
                not isinstance(value, UUID)
                for value in declared_delivery_evidence_ids
            )
            or (
                all(
                    isinstance(value, UUID)
                    for value in declared_delivery_evidence_ids
                )
                and len(set(declared_delivery_evidence_ids)) != 2
            )
        ):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_evidence_id_invalid"
            )

        deliverable_id, version_id = declared_delivery_evidence_ids
        try:
            record = self._deliverable_repository.get_record_by_id(deliverable_id)
        except (TypeError, ValueError, ValidationError):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )
        if record is None:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_deliverable_missing"
            )
        try:
            exact_version = self._deliverable_repository.get_version_by_id(
                version_id=version_id
            )
        except (TypeError, ValueError, ValidationError):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )
        if exact_version is None:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_missing"
            )
        if exact_version.deliverable_id != deliverable_id:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_mismatch"
            )

        deliverable = record.deliverable
        version_id_matches = [
            version for version in record.versions if version.id == version_id
        ]
        if len(version_id_matches) != 1 or version_id_matches[0] != exact_version:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )
        if len({version.id for version in record.versions}) != len(record.versions):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )
        if len({version.version_number for version in record.versions}) != len(
            record.versions
        ):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )
        if deliverable.id != deliverable_id:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_evidence_conflict"
            )
        if deliverable.project_id != project_id:
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_project_mismatch"
            )
        if (
            exact_version.source_task_id is None
            or exact_version.source_run_id is None
            or exact_version.source_task_id != source_task_id
            or exact_version.source_run_id != source_run_id
        ):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_task_run_mismatch"
            )

        deliverable_created_at = ensure_utc_datetime(deliverable.created_at)
        version_created_at = ensure_utc_datetime(exact_version.created_at)
        if (
            deliverable_created_at is None
            or version_created_at is None
            or deliverable_created_at > version_created_at
            or deliverable.current_version_number < exact_version.version_number
        ):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )

        content_bytes = exact_version.content.encode("utf-8")
        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        version_fingerprint = self._build_deliverable_version_fingerprint(
            deliverable=deliverable,
            version=exact_version,
        )
        try:
            snapshot = ProjectDirectorSourceCompletionDeliveryEvidence(
                delivery_evidence_kind=SOURCE_COMPLETION_DELIVERY_EVIDENCE_KIND,
                deliverable_id=deliverable.id,
                deliverable_version_id=exact_version.id,
                deliverable_version_fingerprint=version_fingerprint,
                project_id=deliverable.project_id,
                source_task_id=exact_version.source_task_id,
                source_run_id=exact_version.source_run_id,
                deliverable_type=deliverable.type.value,
                deliverable_title=deliverable.title,
                deliverable_stage=deliverable.stage.value,
                deliverable_created_by_role_code=(
                    deliverable.created_by_role_code.value
                ),
                version_number=exact_version.version_number,
                version_author_role_code=exact_version.author_role_code.value,
                version_summary=exact_version.summary,
                version_content_sha256=content_sha256,
                version_content_bytes=len(content_bytes),
                version_content_format=exact_version.content_format.value,
                version_created_at=version_created_at,
                deliverable_current_version_number_at_validation=(
                    deliverable.current_version_number
                ),
                declared_delivery_evidence_ids=list(
                    declared_delivery_evidence_ids
                ),
                product_runtime_git_write_allowed=False,
                forbidden_actions=list(_FORBIDDEN_ACTIONS),
            )
        except (TypeError, ValueError, ValidationError):
            return SourceCompletionDeliveryEvidenceResolution.blocked(
                "source_completion_delivery_version_lineage_invalid"
            )
        return SourceCompletionDeliveryEvidenceResolution(
            status="resolved",
            snapshot=snapshot,
        )

    @classmethod
    def _build_deliverable_version_fingerprint(
        cls,
        *,
        deliverable: Deliverable,
        version: DeliverableVersion,
    ) -> str:
        payload = {
            "schema_version": SOURCE_COMPLETION_DELIVERY_EVIDENCE_SCHEMA_VERSION,
            "deliverable_id": deliverable.id,
            "deliverable_version_id": version.id,
            "project_id": deliverable.project_id,
            "deliverable_type": deliverable.type.value,
            "deliverable_title": deliverable.title,
            "deliverable_stage": deliverable.stage.value,
            "deliverable_created_by_role_code": (
                deliverable.created_by_role_code.value
            ),
            "deliverable_created_at": deliverable.created_at,
            "version_number": version.version_number,
            "version_author_role_code": version.author_role_code.value,
            "version_summary": version.summary,
            "version_content": version.content,
            "version_content_format": version.content_format.value,
            "version_source_task_id": version.source_task_id,
            "version_source_run_id": version.source_run_id,
            "version_created_at": version.created_at,
        }
        canonical = json.dumps(
            cls._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): cls._canonicalize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
        if isinstance(value, UUID):
            return str(value).lower()
        if isinstance(value, datetime):
            normalized = ensure_utc_datetime(value)
            if normalized is None:
                raise ValueError("fingerprint datetime is required")
            return normalized.isoformat().replace("+00:00", "Z")
        return value


__all__ = ("ProjectDirectorSourceCompletionDeliveryEvidenceAdapter",)
