"""Persistence for exact Project Director formalization proposals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorFormalizationProposalTable
from app.domain._base import ensure_utc_datetime
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)
from app.domain.project_director_conversation_intelligence import FormalizationTarget


class ProjectDirectorFormalizationProposalRepository:
    """Read and write proposals without owning the caller transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_no_commit(
        self,
        proposal: ProjectDirectorFormalizationProposal,
    ) -> ProjectDirectorFormalizationProposal:
        """Insert an exact proposal, allowing only an equivalent replay."""

        existing = self.get_by_id(proposal.proposal_id)
        if existing is not None:
            self._ensure_equivalent(existing, proposal)
            return existing

        row = self._to_row(proposal)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_id(
        self,
        proposal_id: UUID,
    ) -> ProjectDirectorFormalizationProposal | None:
        row = self._session.get(ProjectDirectorFormalizationProposalTable, proposal_id)
        return self._to_domain(row) if row is not None else None

    def get_active_for_session(
        self,
        *,
        session_id: UUID,
    ) -> ProjectDirectorFormalizationProposal | None:
        row = self._session.execute(
            select(ProjectDirectorFormalizationProposalTable)
            .where(
                ProjectDirectorFormalizationProposalTable.session_id == session_id,
                ProjectDirectorFormalizationProposalTable.status
                == FormalizationProposalStatus.PROPOSED.value,
            )
            .order_by(
                ProjectDirectorFormalizationProposalTable.workspace_version.desc(),
                ProjectDirectorFormalizationProposalTable.created_at.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    def get_by_session_workspace_target(
        self,
        *,
        session_id: UUID,
        workspace_version: int,
        target: FormalizationTarget,
        status: FormalizationProposalStatus | None = None,
    ) -> list[ProjectDirectorFormalizationProposal]:
        statement = select(ProjectDirectorFormalizationProposalTable).where(
            ProjectDirectorFormalizationProposalTable.session_id == session_id,
            ProjectDirectorFormalizationProposalTable.workspace_version
            == workspace_version,
            ProjectDirectorFormalizationProposalTable.target == target.value,
        )
        if status is not None:
            statement = statement.where(
                ProjectDirectorFormalizationProposalTable.status == status.value
            )
        rows = self._session.execute(
            statement.order_by(ProjectDirectorFormalizationProposalTable.created_at.asc())
        ).scalars().all()
        return [self._to_domain(row) for row in rows]

    def mark_confirmed_no_commit(
        self,
        *,
        proposal_id: UUID,
        confirmed_plan_version_id: UUID,
        confirmed_at: datetime | None = None,
    ) -> ProjectDirectorFormalizationProposal:
        proposal = self.get_by_id(proposal_id)
        if proposal is None:
            raise ValueError("project_director_formalization_proposal_not_found")
        if proposal.status == FormalizationProposalStatus.CONFIRMED:
            if proposal.confirmed_plan_version_id != confirmed_plan_version_id:
                raise ValueError(
                    "project_director_formalization_proposal_already_confirmed_conflict"
                )
            return proposal
        if proposal.status != FormalizationProposalStatus.PROPOSED:
            raise ValueError("project_director_formalization_proposal_not_active")

        now = confirmed_at or datetime.now(timezone.utc)
        self._session.execute(
            update(ProjectDirectorFormalizationProposalTable)
            .where(
                ProjectDirectorFormalizationProposalTable.proposal_id == proposal_id,
                ProjectDirectorFormalizationProposalTable.status
                == FormalizationProposalStatus.PROPOSED.value,
            )
            .values(
                status=FormalizationProposalStatus.CONFIRMED.value,
                confirmed_plan_version_id=confirmed_plan_version_id,
                confirmed_at=now,
                updated_at=now,
            )
        )
        self._session.flush()
        return self.get_by_id(proposal_id) or proposal

    def mark_superseded_no_commit(
        self,
        *,
        session_id: UUID,
        workspace_version: int,
        target: FormalizationTarget,
        except_proposal_id: UUID,
    ) -> None:
        """Supersede prior active proposals only after the replacement exists."""

        now = datetime.now(timezone.utc)
        self._session.execute(
            update(ProjectDirectorFormalizationProposalTable)
            .where(
                ProjectDirectorFormalizationProposalTable.session_id == session_id,
                ProjectDirectorFormalizationProposalTable.workspace_version
                == workspace_version,
                ProjectDirectorFormalizationProposalTable.target == target.value,
                ProjectDirectorFormalizationProposalTable.status
                == FormalizationProposalStatus.PROPOSED.value,
                ProjectDirectorFormalizationProposalTable.proposal_id != except_proposal_id,
            )
            .values(
                status=FormalizationProposalStatus.SUPERSEDED.value,
                updated_at=now,
            )
        )
        self._session.flush()

    @staticmethod
    def _proposal_json(proposal: ProjectDirectorFormalizationProposal) -> str:
        return json.dumps(
            proposal.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def _to_row(
        cls,
        proposal: ProjectDirectorFormalizationProposal,
    ) -> ProjectDirectorFormalizationProposalTable:
        return ProjectDirectorFormalizationProposalTable(
            proposal_id=proposal.proposal_id,
            session_id=proposal.session_id,
            project_id=proposal.project_id,
            assistant_message_id=proposal.assistant_message_id,
            workspace_version=proposal.workspace_version,
            target=proposal.target.value,
            proposal_json=cls._proposal_json(proposal),
            source_message_ids_json=json.dumps(
                [str(item) for item in proposal.source_message_ids],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            source_event_ids_json=json.dumps(
                [str(item) for item in proposal.source_event_ids],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            status=proposal.status.value,
            confirmed_plan_version_id=proposal.confirmed_plan_version_id,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
            confirmed_at=proposal.confirmed_at,
        )

    @classmethod
    def _to_domain(
        cls,
        row: ProjectDirectorFormalizationProposalTable,
    ) -> ProjectDirectorFormalizationProposal:
        try:
            payload = json.loads(row.proposal_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"invalid_formalization_proposal_json:{row.proposal_id}"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid_formalization_proposal_json:{row.proposal_id}")
        try:
            proposal = ProjectDirectorFormalizationProposal.model_validate(
                {
                    **payload,
                    "proposal_id": row.proposal_id,
                    "session_id": row.session_id,
                    "project_id": row.project_id,
                    "assistant_message_id": row.assistant_message_id,
                    "workspace_version": row.workspace_version,
                    "target": row.target,
                    "status": row.status,
                    "confirmed_plan_version_id": row.confirmed_plan_version_id,
                    "created_at": ensure_utc_datetime(row.created_at),
                    "updated_at": ensure_utc_datetime(row.updated_at),
                    "confirmed_at": ensure_utc_datetime(row.confirmed_at),
                }
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid_formalization_proposal_row:{row.proposal_id}"
            ) from exc
        if (
            json.loads(row.source_message_ids_json) != [str(item) for item in proposal.source_message_ids]
            or json.loads(row.source_event_ids_json) != [str(item) for item in proposal.source_event_ids]
        ):
            raise ValueError(
                f"formalization_proposal_lineage_storage_mismatch:{row.proposal_id}"
            )
        return proposal

    @classmethod
    def _ensure_equivalent(
        cls,
        existing: ProjectDirectorFormalizationProposal,
        incoming: ProjectDirectorFormalizationProposal,
    ) -> None:
        comparable_fields = (
            "proposal_id",
            "session_id",
            "project_id",
            "assistant_message_id",
            "workspace_version",
            "target",
            "summary",
            "changes",
            "source_message_ids",
            "source_event_ids",
            "risk_summary",
            "requires_confirmation",
        )
        if any(
            getattr(existing, field_name) != getattr(incoming, field_name)
            for field_name in comparable_fields
        ):
            raise ValueError("project_director_formalization_proposal_id_conflict")
