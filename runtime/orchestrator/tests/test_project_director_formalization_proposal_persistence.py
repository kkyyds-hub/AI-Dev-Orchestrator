"""P26-H2-T3-M6-R1 — F4 top-level ``source_event_ids`` lineage contract.

This is the first minimal batch. It covers ONLY the F4 lineage contract at the
pure-domain level (no database, no repository, no API):

  A. Provider omits the top-level field  → deterministic auto-derivation.
  B. Provider supplies a correct field    → accepted unchanged.
  C. Illegal explicit fields              → rejected (empty / duplicate /
     missing / extra / wrong-order / all-change-sources-empty).
  D. Persistence Domain consistency       → ``ProjectDirectorFormalizationProposal``
     must match its changes exactly and must NOT recompute-and-mask corruption.
  E. ``to_response_proposal()``           → lossless conversion, top-level
     ``source_event_ids`` identical to the persisted object.

Later batches will extend this file with Repository round-trip, SQLite upgrade,
transaction-atomicity, exact-confirmation and API/Resume coverage.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.domain.project_director_conversation_intelligence import (
    FormalizationChange,
    FormalizationChangeType,
    FormalizationProposal,
    FormalizationTarget,
    ordered_unique_formalization_source_event_ids,
)
from app.domain.project_director_formalization_proposal import (
    FormalizationProposalStatus,
    ProjectDirectorFormalizationProposal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _change(
    event_ids: list[UUID],
    *,
    change_type: FormalizationChangeType = FormalizationChangeType.UPDATE,
    subject_key: str | None = None,
    summary: str = "变更",
) -> FormalizationChange:
    return FormalizationChange(
        change_type=change_type,
        subject_key=subject_key or f"subject-{uuid4().hex[:6]}",
        summary=summary,
        source_event_ids=event_ids,
    )


def _provider_proposal_kwargs(
    *,
    changes: list[FormalizationChange],
    source_message_ids: list[UUID] | None = None,
) -> dict:
    """Minimal valid kwargs for the Provider/API ``FormalizationProposal``."""
    return {
        "proposal_id": uuid4(),
        "target": FormalizationTarget.PLAN_REVISION,
        "workspace_version": 1,
        "summary": "测试草案",
        "changes": changes,
        "source_message_ids": source_message_ids or [uuid4()],
        "risk_summary": "低风险",
    }


def _persisted_proposal_kwargs(
    *,
    changes: list[FormalizationChange],
    source_event_ids: list[UUID],
    source_message_ids: list[UUID] | None = None,
) -> dict:
    """Minimal valid kwargs for the persistence ``ProjectDirectorFormalizationProposal``."""
    return {
        "proposal_id": uuid4(),
        "session_id": uuid4(),
        "project_id": uuid4(),
        "assistant_message_id": uuid4(),
        "workspace_version": 1,
        "target": FormalizationTarget.PLAN_REVISION,
        "summary": "测试草案",
        "changes": changes,
        "source_message_ids": source_message_ids or [uuid4()],
        "source_event_ids": source_event_ids,
        "risk_summary": "低风险",
    }


# ===========================================================================
# A. Provider omits the top-level field → deterministic auto-derivation
# ===========================================================================


class TestProviderOmittedTopLevelLineage:
    """A. When the Provider does not send ``source_event_ids``, the contract
    derives it from the changes: change order, then intra-change order, keeping
    only the first occurrence of each event."""

    def test_omitted_field_is_derived_from_changes(self):
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        changes = [_change([e1, e2]), _change([e3])]
        proposal = FormalizationProposal(**_provider_proposal_kwargs(changes=changes))
        assert proposal.source_event_ids == [e1, e2, e3]

    def test_derivation_is_non_empty(self):
        e1 = uuid4()
        proposal = FormalizationProposal(
            **_provider_proposal_kwargs(changes=[_change([e1])])
        )
        assert proposal.source_event_ids
        assert proposal.source_event_ids == [e1]

    def test_derivation_preserves_change_then_internal_order(self):
        e1, e2, e3, e4 = uuid4(), uuid4(), uuid4(), uuid4()
        changes = [_change([e2, e1]), _change([e4, e3])]
        proposal = FormalizationProposal(**_provider_proposal_kwargs(changes=changes))
        assert proposal.source_event_ids == [e2, e1, e4, e3]

    def test_derivation_keeps_first_occurrence_of_duplicate(self):
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        # e2 appears in both changes; only its first occurrence (change 0) counts.
        changes = [_change([e1, e2]), _change([e2, e3])]
        proposal = FormalizationProposal(**_provider_proposal_kwargs(changes=changes))
        assert proposal.source_event_ids == [e1, e2, e3]

    def test_derivation_matches_canonical_helper(self):
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        changes = [_change([e1, e2]), _change([e2, e3]), _change([e1])]
        proposal = FormalizationProposal(**_provider_proposal_kwargs(changes=changes))
        assert proposal.source_event_ids == ordered_unique_formalization_source_event_ids(
            changes
        )


# ===========================================================================
# B. Provider supplies a correct explicit field → accepted unchanged
# ===========================================================================


class TestProviderExplicitCorrectLineage:
    """B. An explicit ``source_event_ids`` equal to the canonical merge is
    accepted and preserved verbatim (content and order)."""

    def test_explicit_matching_lineage_is_accepted(self):
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        changes = [_change([e1, e2]), _change([e2, e3])]
        expected = ordered_unique_formalization_source_event_ids(changes)
        proposal = FormalizationProposal(
            **_provider_proposal_kwargs(changes=changes),
            source_event_ids=list(expected),
        )
        assert proposal.source_event_ids == expected
        assert proposal.source_event_ids == [e1, e2, e3]


# ===========================================================================
# C. Illegal explicit fields → rejected
# ===========================================================================


class TestProviderIllegalExplicitLineage:
    """C. Explicit ``source_event_ids`` that disagree with the canonical merge
    (or are otherwise malformed) must be rejected."""

    def test_empty_explicit_list_rejected(self):
        e1 = uuid4()
        changes = [_change([e1])]
        with pytest.raises(ValueError, match="source event lineage"):
            FormalizationProposal(
                **_provider_proposal_kwargs(changes=changes),
                source_event_ids=[],
            )

    def test_duplicate_explicit_ids_rejected(self):
        e1, e2 = uuid4(), uuid4()
        changes = [_change([e1, e2])]
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            FormalizationProposal(
                **_provider_proposal_kwargs(changes=changes),
                source_event_ids=[e1, e1],
            )

    def test_missing_change_referenced_event_rejected(self):
        e1, e2 = uuid4(), uuid4()
        changes = [_change([e1, e2])]
        # Omits e2 which a change references.
        with pytest.raises(ValueError, match="source event lineage"):
            FormalizationProposal(
                **_provider_proposal_kwargs(changes=changes),
                source_event_ids=[e1],
            )

    def test_extra_unreferenced_event_rejected(self):
        e1, e_extra = uuid4(), uuid4()
        changes = [_change([e1])]
        # Includes an event no change references.
        with pytest.raises(ValueError, match="source event lineage"):
            FormalizationProposal(
                **_provider_proposal_kwargs(changes=changes),
                source_event_ids=[e1, e_extra],
            )

    def test_wrong_order_rejected(self):
        e1, e2 = uuid4(), uuid4()
        changes = [_change([e1, e2])]
        # Same set, wrong order.
        with pytest.raises(ValueError, match="source event lineage"):
            FormalizationProposal(
                **_provider_proposal_kwargs(changes=changes),
                source_event_ids=[e2, e1],
            )

    def test_all_change_sources_empty_rejected(self):
        # Every change has empty lineage → no derivable top-level lineage.
        changes = [_change([]), _change([])]
        with pytest.raises(ValueError, match="source event lineage"):
            FormalizationProposal(**_provider_proposal_kwargs(changes=changes))


# ===========================================================================
# D. Persistence Domain consistency
# ===========================================================================


class TestPersistenceDomainConsistency:
    """D. ``ProjectDirectorFormalizationProposal`` requires an explicit top-level
    ``source_event_ids`` that matches its changes exactly. It must NOT recompute
    the lineage at conversion time and thereby mask corrupted persisted data."""

    def test_consistent_lineage_constructs(self):
        e1, e2 = uuid4(), uuid4()
        changes = [_change([e1]), _change([e2])]
        proposal = ProjectDirectorFormalizationProposal(
            **_persisted_proposal_kwargs(
                changes=changes, source_event_ids=[e1, e2]
            )
        )
        assert proposal.source_event_ids == [e1, e2]
        assert proposal.status == FormalizationProposalStatus.PROPOSED

    def test_inconsistent_order_fails_construction(self):
        e1, e2 = uuid4(), uuid4()
        changes = [_change([e1]), _change([e2])]
        with pytest.raises(ValueError, match="must match changes"):
            ProjectDirectorFormalizationProposal(
                **_persisted_proposal_kwargs(
                    changes=changes, source_event_ids=[e2, e1]
                )
            )

    def test_missing_event_fails_construction(self):
        e1, e2 = uuid4(), uuid4()
        changes = [_change([e1]), _change([e2])]
        with pytest.raises(ValueError, match="must match changes"):
            ProjectDirectorFormalizationProposal(
                **_persisted_proposal_kwargs(changes=changes, source_event_ids=[e1])
            )

    def test_extra_event_fails_construction(self):
        e1, e_extra = uuid4(), uuid4()
        changes = [_change([e1])]
        with pytest.raises(ValueError, match="must match changes"):
            ProjectDirectorFormalizationProposal(
                **_persisted_proposal_kwargs(
                    changes=changes, source_event_ids=[e1, e_extra]
                )
            )

    def test_empty_lineage_fails_construction(self):
        e1 = uuid4()
        changes = [_change([e1])]
        # min_length=1 on the persistence Domain rejects an empty top-level list.
        with pytest.raises(ValueError):
            ProjectDirectorFormalizationProposal(
                **_persisted_proposal_kwargs(changes=changes, source_event_ids=[])
            )

    def test_duplicate_lineage_fails_construction(self):
        e1 = uuid4()
        changes = [_change([e1])]
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            ProjectDirectorFormalizationProposal(
                **_persisted_proposal_kwargs(
                    changes=changes, source_event_ids=[e1, e1]
                )
            )

    def test_corruption_is_not_recomputed_away(self):
        """A wrong-order persisted lineage must fail, not be silently reordered."""
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        changes = [_change([e1, e2]), _change([e3])]
        corrupted = [e3, e1, e2]  # valid set, wrong order
        assert corrupted != ordered_unique_formalization_source_event_ids(changes)
        with pytest.raises(ValueError, match="must match changes"):
            ProjectDirectorFormalizationProposal(
                **_persisted_proposal_kwargs(
                    changes=changes, source_event_ids=corrupted
                )
            )


# ===========================================================================
# E. to_response_proposal() lossless conversion
# ===========================================================================


class TestResponseProposalLossless:
    """E. ``to_response_proposal()`` exposes the Provider contract without losing
    any field; the top-level ``source_event_ids`` is identical to the persisted
    object."""

    def _make_persisted(self) -> ProjectDirectorFormalizationProposal:
        e1, e2, e3 = uuid4(), uuid4(), uuid4()
        msg1, msg2 = uuid4(), uuid4()
        changes = [_change([e1, e2]), _change([e2, e3])]
        return ProjectDirectorFormalizationProposal(
            **_persisted_proposal_kwargs(
                changes=changes,
                source_event_ids=[e1, e2, e3],
                source_message_ids=[msg1, msg2],
            )
        )

    def test_all_fields_lossless(self):
        persisted = self._make_persisted()
        response = persisted.to_response_proposal()

        assert response.proposal_id == persisted.proposal_id
        assert response.target == persisted.target
        assert response.workspace_version == persisted.workspace_version
        assert response.summary == persisted.summary
        assert response.changes == persisted.changes
        assert response.source_message_ids == persisted.source_message_ids
        assert response.risk_summary == persisted.risk_summary
        assert response.requires_confirmation is True
        assert response.status == "proposed"

    def test_top_level_source_event_ids_identical(self):
        persisted = self._make_persisted()
        response = persisted.to_response_proposal()
        # The exact regression this batch guards: the top-level lineage must
        # survive the Domain → response conversion with order and content intact.
        assert response.source_event_ids == persisted.source_event_ids
        assert response.source_event_ids == [
            persisted.source_event_ids[0],
            persisted.source_event_ids[1],
            persisted.source_event_ids[2],
        ]

    def test_change_level_lineage_preserved(self):
        persisted = self._make_persisted()
        response = persisted.to_response_proposal()
        assert [c.source_event_ids for c in response.changes] == [
            c.source_event_ids for c in persisted.changes
        ]
