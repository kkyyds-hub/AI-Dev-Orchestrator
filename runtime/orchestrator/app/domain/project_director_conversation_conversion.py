"""Pure domain conversion drafts for Project Director conversations.

This module converts an in-memory ``DirectorActionProposal`` into another
in-memory draft that can later be reviewed by a user.  It intentionally has no
side effects: it does not import repositories or services, does not use a
database session, does not modify plan drafts, does not create tasks, does not
create approvals, and does not start external tools.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel
from app.domain.project_director_action_proposal import (
    DirectorActionProposal,
    DirectorActionProposalType,
    DirectorActionRisk,
    ProposalApprovalRequirement,
)


class ConversationConversionTarget(StrEnum):
    """Target draft type for one conversation conversion."""

    PLAN_REVISION_DRAFT = "plan_revision_draft"
    TASK_DRAFT = "task_draft"
    TASK_SCOPE_UPDATE_DRAFT = "task_scope_update_draft"
    PRIORITY_UPDATE_DRAFT = "priority_update_draft"
    RISK_UPDATE_DRAFT = "risk_update_draft"
    EXPLANATION_ONLY = "explanation_only"
    NO_CONVERSION = "no_conversion"


class ConversationConversionStatus(StrEnum):
    """Review status for conversion drafts.

    Applied, created, and executed states are intentionally not present in P7-H1.
    """

    DRAFT = "draft"
    NEEDS_USER_REVIEW = "needs_user_review"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ConversationConversionRisk(StrEnum):
    """Risk level copied from the source proposal."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanConversionDraft(DomainModel):
    """In-memory draft describing a suggested plan change."""

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    reason: str = Field(min_length=1, max_length=600)
    affected_sections: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool

    @field_validator("title", "summary", "reason", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("text fields must not be empty")
        return normalized

    @field_validator("affected_sections", "proposed_changes")
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class TaskConversionDraft(DomainModel):
    """In-memory draft describing a suggested task-level change."""

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    input_summary: str = Field(min_length=1, max_length=1_000)
    acceptance_criteria: list[str] = Field(default_factory=list)
    suggested_priority: str = Field(min_length=1, max_length=40)
    blocked_reason: str | None = Field(default=None, max_length=600)
    requires_user_confirmation: bool

    @field_validator(
        "title",
        "summary",
        "input_summary",
        "suggested_priority",
        "blocked_reason",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized

    @field_validator("acceptance_criteria")
    @classmethod
    def normalize_acceptance_criteria(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class ConversationConversionDraft(DomainModel):
    """In-memory conversion draft produced from one action proposal."""

    target: ConversationConversionTarget
    status: ConversationConversionStatus
    risk: ConversationConversionRisk
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    reason: str = Field(min_length=1, max_length=600)
    source_proposal_type: str | None = None
    source_approval_requirement: str | None = None
    conversation_id: UUID | None = None
    project_id: UUID | None = None
    target_id: UUID | None = None
    plan_draft: PlanConversionDraft | None = None
    task_draft: TaskConversionDraft | None = None
    safe_next_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    created_by: str = "ai_project_director"

    @field_validator(
        "title",
        "summary",
        "reason",
        "source_proposal_type",
        "source_approval_requirement",
        "created_by",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("safe_next_actions", "forbidden_actions")
    @classmethod
    def normalize_action_texts(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


_FORBIDDEN_ACTIONS_CN = [
    "不会自动修改草案",
    "不会自动创建任务",
    "不会自动执行任务",
    "不会修改仓库",
    "不会启动外部工具",
    "不会自动应用建议",
    "不会自动执行审批",
]

_SAFE_NEXT_ACTIONS_REVIEW_CN = [
    "查看草稿",
    "解释原因",
    "等待你确认",
    "调整草稿内容",
    "记录为待复核",
]

_SAFE_NEXT_ACTIONS_EXPLAIN_CN = [
    "解释原因",
    "记录为待复核",
]

_SAFE_NEXT_ACTIONS_NONE_CN = [
    "继续澄清问题",
    "解释原因",
]


class ConversationConversionBuilder:
    """Build side-effect-free conversion drafts from action proposals."""

    @classmethod
    def build_from_proposal(
        cls,
        proposal: DirectorActionProposal,
    ) -> ConversationConversionDraft:
        """Convert a proposal into a reviewable in-memory conversion draft."""

        target = cls._target_for(proposal.proposal_type)
        risk = cls._risk_for(proposal.risk)
        plan_draft = cls._plan_draft_for(proposal=proposal, target=target)
        task_draft = cls._task_draft_for(proposal=proposal, target=target)
        status = cls._status_for(
            target=target,
            risk=risk,
            approval_requirement=proposal.approval_requirement,
        )

        return ConversationConversionDraft(
            target=target,
            status=status,
            risk=risk,
            title=cls._title_for(target),
            summary=cls._summary_for(target),
            reason=cls._reason_for(proposal=proposal, target=target),
            source_proposal_type=proposal.proposal_type.value,
            source_approval_requirement=proposal.approval_requirement.value,
            conversation_id=proposal.conversation_id,
            project_id=proposal.project_id,
            target_id=proposal.target_id,
            plan_draft=plan_draft,
            task_draft=task_draft,
            safe_next_actions=cls._safe_next_actions_for(target),
            forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
        )

    @staticmethod
    def _target_for(
        proposal_type: DirectorActionProposalType,
    ) -> ConversationConversionTarget:
        mapping = {
            DirectorActionProposalType.PLAN_REVISION: (
                ConversationConversionTarget.PLAN_REVISION_DRAFT
            ),
            DirectorActionProposalType.TASK_SCOPE_REVISION: (
                ConversationConversionTarget.TASK_SCOPE_UPDATE_DRAFT
            ),
            DirectorActionProposalType.PRIORITY_REVISION: (
                ConversationConversionTarget.PRIORITY_UPDATE_DRAFT
            ),
            DirectorActionProposalType.RISK_REVISION: (
                ConversationConversionTarget.RISK_UPDATE_DRAFT
            ),
            DirectorActionProposalType.REQUIREMENT_CHANGE_REVIEW: (
                ConversationConversionTarget.PLAN_REVISION_DRAFT
            ),
            DirectorActionProposalType.DISPATCH_REVIEW: (
                ConversationConversionTarget.EXPLANATION_ONLY
            ),
            DirectorActionProposalType.GOVERNANCE_REVIEW: (
                ConversationConversionTarget.EXPLANATION_ONLY
            ),
            DirectorActionProposalType.DELIVERABLE_REVIEW: (
                ConversationConversionTarget.EXPLANATION_ONLY
            ),
            DirectorActionProposalType.EXPLAIN_ONLY: (
                ConversationConversionTarget.EXPLANATION_ONLY
            ),
            DirectorActionProposalType.NO_ACTION: (
                ConversationConversionTarget.NO_CONVERSION
            ),
        }
        return mapping[proposal_type]

    @staticmethod
    def _risk_for(proposal_risk: DirectorActionRisk) -> ConversationConversionRisk:
        return {
            DirectorActionRisk.LOW: ConversationConversionRisk.LOW,
            DirectorActionRisk.MEDIUM: ConversationConversionRisk.MEDIUM,
            DirectorActionRisk.HIGH: ConversationConversionRisk.HIGH,
        }[proposal_risk]

    @staticmethod
    def _status_for(
        *,
        target: ConversationConversionTarget,
        risk: ConversationConversionRisk,
        approval_requirement: ProposalApprovalRequirement,
    ) -> ConversationConversionStatus:
        if target == ConversationConversionTarget.NO_CONVERSION:
            return ConversationConversionStatus.DRAFT
        if target == ConversationConversionTarget.EXPLANATION_ONLY:
            return ConversationConversionStatus.DRAFT
        if approval_requirement != ProposalApprovalRequirement.NONE:
            return ConversationConversionStatus.NEEDS_USER_REVIEW
        if risk == ConversationConversionRisk.HIGH:
            return ConversationConversionStatus.NEEDS_USER_REVIEW
        return ConversationConversionStatus.DRAFT

    @classmethod
    def _plan_draft_for(
        cls,
        *,
        proposal: DirectorActionProposal,
        target: ConversationConversionTarget,
    ) -> PlanConversionDraft | None:
        if target not in {
            ConversationConversionTarget.PLAN_REVISION_DRAFT,
            ConversationConversionTarget.RISK_UPDATE_DRAFT,
        }:
            return None

        revision = proposal.plan_revision
        if revision is None:
            return PlanConversionDraft(
                title="整理草案修改建议",
                summary="这条反馈需要先整理为草案修改建议，再等待你确认。",
                reason="当前建议可能影响项目范围或验收方式，不能自动应用。",
                affected_sections=["项目草案", "验收标准"],
                proposed_changes=["列出受影响内容", "补充修改理由"],
                requires_user_confirmation=True,
            )

        return PlanConversionDraft(
            title=revision.title,
            summary=revision.summary,
            reason=revision.reason,
            affected_sections=list(revision.affected_sections),
            proposed_changes=list(revision.proposed_changes),
            requires_user_confirmation=revision.requires_user_confirmation,
        )

    @classmethod
    def _task_draft_for(
        cls,
        *,
        proposal: DirectorActionProposal,
        target: ConversationConversionTarget,
    ) -> TaskConversionDraft | None:
        if target not in {
            ConversationConversionTarget.TASK_DRAFT,
            ConversationConversionTarget.TASK_SCOPE_UPDATE_DRAFT,
            ConversationConversionTarget.PRIORITY_UPDATE_DRAFT,
        }:
            return None

        if target == ConversationConversionTarget.PRIORITY_UPDATE_DRAFT:
            return TaskConversionDraft(
                title="调整任务优先级",
                summary="这条反馈适合整理为任务优先级调整草稿。",
                input_summary="复核任务先后顺序，并说明调整依据。",
                acceptance_criteria=[
                    "说明为什么需要调整优先级",
                    "列出受影响的任务或阶段",
                ],
                suggested_priority="待确认",
                blocked_reason=None,
                requires_user_confirmation=True,
            )

        return TaskConversionDraft(
            title="调整任务范围",
            summary="这条反馈适合整理为任务范围调整草稿。",
            input_summary="复核任务边界、输入内容和验收口径。",
            acceptance_criteria=[
                "说明需要调整的任务范围",
                "补充清晰的验收标准",
            ],
            suggested_priority="待确认",
            blocked_reason=None,
            requires_user_confirmation=True,
        )

    @staticmethod
    def _safe_next_actions_for(target: ConversationConversionTarget) -> list[str]:
        if target == ConversationConversionTarget.NO_CONVERSION:
            return list(_SAFE_NEXT_ACTIONS_NONE_CN)
        if target == ConversationConversionTarget.EXPLANATION_ONLY:
            return list(_SAFE_NEXT_ACTIONS_EXPLAIN_CN)
        return list(_SAFE_NEXT_ACTIONS_REVIEW_CN)

    @staticmethod
    def _title_for(target: ConversationConversionTarget) -> str:
        return {
            ConversationConversionTarget.PLAN_REVISION_DRAFT: "计划修改草稿",
            ConversationConversionTarget.TASK_DRAFT: "任务草稿",
            ConversationConversionTarget.TASK_SCOPE_UPDATE_DRAFT: "任务范围调整草稿",
            ConversationConversionTarget.PRIORITY_UPDATE_DRAFT: "优先级调整草稿",
            ConversationConversionTarget.RISK_UPDATE_DRAFT: "风险补充草稿",
            ConversationConversionTarget.EXPLANATION_ONLY: "仅解释说明",
            ConversationConversionTarget.NO_CONVERSION: "暂不转换",
        }[target]

    @staticmethod
    def _summary_for(target: ConversationConversionTarget) -> str:
        return {
            ConversationConversionTarget.PLAN_REVISION_DRAFT: (
                "这条建议会先整理成计划修改草稿，只供查看和确认。"
            ),
            ConversationConversionTarget.TASK_DRAFT: (
                "这条建议会先整理成任务草稿，不会自动创建任务。"
            ),
            ConversationConversionTarget.TASK_SCOPE_UPDATE_DRAFT: (
                "这条建议会先整理成任务范围调整草稿，不会自动创建任务。"
            ),
            ConversationConversionTarget.PRIORITY_UPDATE_DRAFT: (
                "这条建议会先整理成优先级调整草稿，不会自动改动任务。"
            ),
            ConversationConversionTarget.RISK_UPDATE_DRAFT: (
                "这条建议会先整理成风险补充草稿，不会自动改动草案。"
            ),
            ConversationConversionTarget.EXPLANATION_ONLY: (
                "这条建议只适合先解释原因，不生成执行草稿。"
            ),
            ConversationConversionTarget.NO_CONVERSION: (
                "当前信息不足，暂时不转换为草稿。"
            ),
        }[target]

    @staticmethod
    def _reason_for(
        *,
        proposal: DirectorActionProposal,
        target: ConversationConversionTarget,
    ) -> str:
        if target == ConversationConversionTarget.EXPLANATION_ONLY:
            if proposal.proposal_type == DirectorActionProposalType.DISPATCH_REVIEW:
                return "这条反馈涉及安排复核，只能先说明依据，不会启动外部工具。"
            if proposal.proposal_type == DirectorActionProposalType.GOVERNANCE_REVIEW:
                return "这条反馈涉及治理设置，只能先说明风险，不会修改配置。"
            return "这条反馈更适合先说明原因，不能自动执行后续动作。"
        if target == ConversationConversionTarget.NO_CONVERSION:
            return "当前反馈还不够明确，需要继续澄清后再决定。"
        return "这条建议可能影响项目推进，需要先形成可审查草稿。"
