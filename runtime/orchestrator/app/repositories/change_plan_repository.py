"""Persistence helpers for Day06 change-plan heads and immutable versions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db_tables import ChangePlanTable, ChangePlanVersionTable
from app.domain._base import ensure_utc_datetime
from app.domain.change_plan import ChangePlan, ChangePlanTargetFile, ChangePlanVersion
from app.domain.repository_verification import (
    RepositoryVerificationTemplateReference,
)


@dataclass(slots=True, frozen=True)
class ChangePlanRecord:
    """One change-plan head together with its ordered immutable versions."""

    change_plan: ChangePlan
    versions: list[ChangePlanVersion]


class ChangePlanRepository:
    """Encapsulate change-plan persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_with_initial_version(
        self,
        *,
        change_plan: ChangePlan,
        initial_version: ChangePlanVersion,
    ) -> ChangePlanRecord:
        """Persist one change-plan head together with its first draft version."""

        if change_plan.id != initial_version.change_plan_id:
            raise ValueError("Initial change-plan version must target the new head record.")

        plan_row = ChangePlanTable(
            id=change_plan.id,
            project_id=change_plan.project_id,
            task_id=change_plan.task_id,
            primary_deliverable_id=change_plan.primary_deliverable_id,
            status=change_plan.status,
            title=change_plan.title,
            current_version_number=change_plan.current_version_number,
            created_at=change_plan.created_at,
            updated_at=change_plan.updated_at,
        )
        plan_row.versions.append(self._build_version_row(initial_version))

        self.session.add(plan_row)
        self.session.commit()

        persisted_record = self.get_record_by_id(change_plan.id)
        if persisted_record is None:
            raise ValueError(f"Change plan not found after initial persistence: {change_plan.id}")

        return persisted_record

    def add_version(
        self,
        *,
        change_plan_id: UUID,
        version: ChangePlanVersion,
        title: str | None = None,
        primary_deliverable_id: UUID | None = None,
    ) -> ChangePlanRecord:
        """Append one immutable draft version and update the head pointer."""

        if change_plan_id != version.change_plan_id:
            raise ValueError("Change-plan version change_plan_id does not match the target.")

        plan_row = self.session.get(ChangePlanTable, change_plan_id)
        if plan_row is None:
            raise ValueError(f"Change plan not found: {change_plan_id}")

        plan_row.current_version_number = version.version_number
        plan_row.updated_at = version.created_at
        if title is not None:
            plan_row.title = title
        if primary_deliverable_id is not None:
            plan_row.primary_deliverable_id = primary_deliverable_id

        self.session.add(self._build_version_row(version))
        self.session.commit()

        persisted_record = self.get_record_by_id(change_plan_id)
        if persisted_record is None:
            raise ValueError(f"Change plan not found after version append: {change_plan_id}")

        return persisted_record

    def get_record_by_id(self, change_plan_id: UUID) -> ChangePlanRecord | None:
        """Return one change-plan head plus all persisted versions."""

        statement = (
            select(ChangePlanTable)
            .options(selectinload(ChangePlanTable.versions))
            .where(ChangePlanTable.id == change_plan_id)
        )
        plan_row = self.session.execute(statement).scalar_one_or_none()
        if plan_row is None:
            return None

        return self._to_record(plan_row)

    def list_records_by_project_id(
        self,
        project_id: UUID,
        *,
        task_id: UUID | None = None,
    ) -> list[ChangePlanRecord]:
        """Return project-scoped change plans ordered by latest activity."""

        statement = (
            select(ChangePlanTable)
            .options(selectinload(ChangePlanTable.versions))
            .where(ChangePlanTable.project_id == project_id)
        )
        if task_id is not None:
            statement = statement.where(ChangePlanTable.task_id == task_id)

        statement = statement.order_by(
            ChangePlanTable.updated_at.desc(),
            ChangePlanTable.created_at.desc(),
        )
        plan_rows = self.session.execute(statement).scalars().all()
        return [self._to_record(plan_row) for plan_row in plan_rows]

    def _to_record(self, plan_row: ChangePlanTable) -> ChangePlanRecord:
        """Convert one ORM bundle into a typed change-plan record."""

        versions = sorted(
            (self._to_version(version_row) for version_row in plan_row.versions),
            key=lambda item: (item.version_number, item.created_at),
            reverse=True,
        )
        return ChangePlanRecord(
            change_plan=self._to_change_plan(plan_row),
            versions=versions,
        )

    @staticmethod
    def _build_version_row(version: ChangePlanVersion) -> ChangePlanVersionTable:
        """Convert one domain draft version into an ORM row."""

        return ChangePlanVersionTable(
            id=version.id,
            change_plan_id=version.change_plan_id,
            version_number=version.version_number,
            intent_summary=version.intent_summary,
            source_summary=version.source_summary,
            focus_terms_json=ChangePlanRepository._serialize_string_list(version.focus_terms),
            target_files_json=ChangePlanRepository._serialize_target_files(version.target_files),
            expected_actions_json=ChangePlanRepository._serialize_string_list(
                version.expected_actions
            ),
            risk_notes_json=ChangePlanRepository._serialize_string_list(version.risk_notes),
            verification_commands_json=ChangePlanRepository._serialize_string_list(
                version.verification_commands
            ),
            verification_templates_json=ChangePlanRepository._serialize_verification_templates(
                version.verification_templates
            ),
            related_deliverable_ids_json=ChangePlanRepository._serialize_uuid_list(
                version.related_deliverable_ids
            ),
            context_pack_generated_at=version.context_pack_generated_at,
            created_at=version.created_at,
        )

    @staticmethod
    def _to_change_plan(plan_row: ChangePlanTable) -> ChangePlan:
        """Convert one persisted head row into its domain model."""

        return ChangePlan(
            id=plan_row.id,
            project_id=plan_row.project_id,
            task_id=plan_row.task_id,
            primary_deliverable_id=plan_row.primary_deliverable_id,
            status=plan_row.status,
            title=plan_row.title,
            current_version_number=plan_row.current_version_number,
            created_at=ensure_utc_datetime(plan_row.created_at),
            updated_at=ensure_utc_datetime(plan_row.updated_at),
        )

    @staticmethod
    def _to_version(version_row: ChangePlanVersionTable) -> ChangePlanVersion:
        """Convert one persisted version row into its domain model."""

        return ChangePlanVersion(
            id=version_row.id,
            change_plan_id=version_row.change_plan_id,
            version_number=version_row.version_number,
            intent_summary=version_row.intent_summary,
            source_summary=version_row.source_summary,
            focus_terms=ChangePlanRepository._deserialize_string_list(
                version_row.focus_terms_json
            ),
            target_files=ChangePlanRepository._deserialize_target_files(
                version_row.target_files_json
            ),
            expected_actions=ChangePlanRepository._deserialize_string_list(
                version_row.expected_actions_json
            ),
            risk_notes=ChangePlanRepository._deserialize_string_list(
                version_row.risk_notes_json
            ),
            verification_commands=ChangePlanRepository._deserialize_string_list(
                version_row.verification_commands_json
            ),
            verification_templates=ChangePlanRepository._deserialize_verification_templates(
                version_row.verification_templates_json
            ),
            related_deliverable_ids=ChangePlanRepository._deserialize_uuid_list(
                version_row.related_deliverable_ids_json
            ),
            context_pack_generated_at=ensure_utc_datetime(
                version_row.context_pack_generated_at
            ),
            created_at=ensure_utc_datetime(version_row.created_at),
        )

    @staticmethod
    def _serialize_string_list(values: list[str]) -> str:
        """Persist one string list as JSON text."""

        return json.dumps(values, ensure_ascii=False)

    @staticmethod
    def _deserialize_string_list(raw_value: str | None) -> list[str]:
        """Read one JSON-encoded string list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[str] = []
        for item in decoded_value:
            if not isinstance(item, str):
                continue
            normalized_item = item.strip()
            if normalized_item:
                normalized_items.append(normalized_item)

        return normalized_items

    @staticmethod
    def _serialize_uuid_list(values: list[UUID]) -> str:
        """Persist one UUID list as JSON text."""

        return json.dumps([str(value) for value in values], ensure_ascii=False)

    @staticmethod
    def _deserialize_uuid_list(raw_value: str | None) -> list[UUID]:
        """Read one JSON-encoded UUID list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[UUID] = []
        seen_items: set[UUID] = set()
        for item in decoded_value:
            if not isinstance(item, str):
                continue
            try:
                normalized_uuid = UUID(item)
            except ValueError:
                continue
            if normalized_uuid in seen_items:
                continue
            normalized_items.append(normalized_uuid)
            seen_items.add(normalized_uuid)

        return normalized_items

    @staticmethod
    def _serialize_target_files(values: list[ChangePlanTargetFile]) -> str:
        """Persist structured target-file items as JSON text."""

        return json.dumps(
            [value.model_dump(mode="json") for value in values],
            ensure_ascii=False,
        )

    @staticmethod
    def _serialize_verification_templates(
        values: list[RepositoryVerificationTemplateReference],
    ) -> str:
        """Persist structured Day09 verification-template references as JSON text."""

        return json.dumps(
            [value.model_dump(mode="json") for value in values],
            ensure_ascii=False,
        )

    @staticmethod
    def _deserialize_target_files(raw_value: str | None) -> list[ChangePlanTargetFile]:
        """Read one JSON-encoded target-file list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[ChangePlanTargetFile] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue
            try:
                normalized_items.append(ChangePlanTargetFile.model_validate(item))
            except ValidationError:
                continue

        return normalized_items

    @staticmethod
    def _deserialize_verification_templates(
        raw_value: str | None,
    ) -> list[RepositoryVerificationTemplateReference]:
        """Read one JSON-encoded Day09 verification-template list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[RepositoryVerificationTemplateReference] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue
            try:
                normalized_items.append(
                    RepositoryVerificationTemplateReference.model_validate(item)
                )
            except ValidationError:
                continue

        return normalized_items
