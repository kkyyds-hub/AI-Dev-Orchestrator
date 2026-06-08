"""Pure domain model for Project Director action proposals.

This module converts a P7-F ``UserChallengeSeed`` into an in-memory proposal
object that can be reviewed later.  It is intentionally side-effect free: it
does not import repositories or services, does not read or write a database,
does not mutate drafts, does not create tasks, and does not start external
tools.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel
from app.domain.project_director_user_challenge import (
    UserChallengeSeed,
    UserChallengeType,
)


class DirectorActionProposalType(StrEnum):
    """User-reviewable proposal categories."""

    EXPLAIN_ONLY = "explain_only"
    PLAN_REVISION = "plan_revision"
    TASK_SCOPE_REVISION = "task_scope_revision"
    PRIORITY_REVISION = "priority_revision"
    RISK_REVISION = "risk_revision"
    DISPATCH_REVIEW = "dispatch_review"
    GOVERNANCE_REVIEW = "governance_review"
    DELIVERABLE_REVIEW = "deliverable_review"
    REQUIREMENT_CHANGE_REVIEW = "requirement_change_review"
    NO_ACTION = "no_action"


class DirectorActionProposalStatus(StrEnum):
    """Proposal states reserved for later workflow stages."""

    DRAFT = "draft"
    PENDING_USER_REVIEW = "pending_user_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    APPLIED = "applied"
    ARCHIVED = "archived"


class DirectorActionRisk(StrEnum):
    """Risk levels for proposal review."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProposalApprovalRequirement(StrEnum):
    """Review requirement for a proposal."""

    NONE = "none"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    OWNER_APPROVAL_REQUIRED = "owner_approval_required"


class PlanRevisionKind(StrEnum):
    """Kinds of plan revision drafts a proposal may carry."""

    SUMMARY_UPDATE = "summary_update"
    PHASE_UPDATE = "phase_update"
    TASK_UPDATE = "task_update"
    PRIORITY_UPDATE = "priority_update"
    RISK_UPDATE = "risk_update"
    REQUIREMENT_CHANGE = "requirement_change"
    ACCEPTANCE_CRITERIA_UPDATE = "acceptance_criteria_update"


class PlanRevisionDraft(DomainModel):
    """In-memory draft describing a suggested plan change."""

    revision_kind: PlanRevisionKind
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    reason: str = Field(min_length=1, max_length=600)
    affected_sections: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool

    @field_validator(
        "title",
        "summary",
        "reason",
        mode="before",
    )
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


class DirectorActionProposal(DomainModel):
    """In-memory user-reviewable action proposal."""

    proposal_type: DirectorActionProposalType
    status: DirectorActionProposalStatus
    risk: DirectorActionRisk
    approval_requirement: ProposalApprovalRequirement
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    reason: str = Field(min_length=1, max_length=600)
    source_challenge_type: str | None = None
    source_challenge_severity: str | None = None
    conversation_id: UUID | None = None
    project_id: UUID | None = None
    target_id: UUID | None = None
    safe_next_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    plan_revision: PlanRevisionDraft | None = None
    created_by: str = "ai_project_director"

    @field_validator(
        "title",
        "summary",
        "reason",
        "source_challenge_type",
        "source_challenge_severity",
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
]

_SAFE_NEXT_ACTIONS_REVIEW_CN = [
    "查看建议",
    "解释原因",
    "准备草案修改建议",
    "等待你确认",
    "记录为待复核",
]

_SAFE_NEXT_ACTIONS_EXPLAIN_CN = [
    "查看建议",
    "解释原因",
]

_SAFE_NEXT_ACTIONS_REVIEW_ONLY_CN = [
    "查看建议",
    "解释原因",
    "等待你确认",
    "记录为待复核",
]


class DirectorActionProposalBuilder:
    """Build in-memory proposals from user challenge seeds."""

    @classmethod
    def build_from_challenge(cls, seed: UserChallengeSeed) -> DirectorActionProposal:
        """Convert a challenge seed into a reviewable proposal without side effects."""

        proposal_type = cls._proposal_type_for(seed.challenge_type)
        risk = cls._risk_for(seed.challenge_type)
        plan_revision = cls._plan_revision_for(seed.challenge_type)
        approval_requirement = cls._approval_requirement_for(
            proposal_type=proposal_type,
            risk=risk,
            requires_human_confirmation=seed.requires_human_confirmation,
            plan_revision=plan_revision,
        )
        status = cls._status_for(approval_requirement)

        return DirectorActionProposal(
            proposal_type=proposal_type,
            status=status,
            risk=risk,
            approval_requirement=approval_requirement,
            title=cls._title_for(proposal_type),
            summary=cls._summary_for(proposal_type),
            reason=cls._reason_for(proposal_type),
            source_challenge_type=seed.challenge_type.value,
            source_challenge_severity=seed.severity.value,
            conversation_id=seed.conversation_id,
            project_id=seed.project_id,
            target_id=seed.target_id,
            safe_next_actions=cls._safe_next_actions_for(
                proposal_type=proposal_type,
                plan_revision=plan_revision,
            ),
            forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
            plan_revision=plan_revision,
        )

    @staticmethod
    def _proposal_type_for(
        challenge_type: UserChallengeType,
    ) -> DirectorActionProposalType:
        mapping = {
            UserChallengeType.PLAN_CHALLENGE: DirectorActionProposalType.PLAN_REVISION,
            UserChallengeType.TASK_SCOPE_CHALLENGE: (
                DirectorActionProposalType.TASK_SCOPE_REVISION
            ),
            UserChallengeType.PRIORITY_CHALLENGE: (
                DirectorActionProposalType.PRIORITY_REVISION
            ),
            UserChallengeType.RISK_CHALLENGE: DirectorActionProposalType.RISK_REVISION,
            UserChallengeType.DISPATCH_CHALLENGE: (
                DirectorActionProposalType.DISPATCH_REVIEW
            ),
            UserChallengeType.INBOX_ATTENTION_CHALLENGE: (
                DirectorActionProposalType.EXPLAIN_ONLY
            ),
            UserChallengeType.DELIVERABLE_CHALLENGE: (
                DirectorActionProposalType.DELIVERABLE_REVIEW
            ),
            UserChallengeType.GOVERNANCE_CHALLENGE: (
                DirectorActionProposalType.GOVERNANCE_REVIEW
            ),
            UserChallengeType.REQUIREMENT_CHANGE: (
                DirectorActionProposalType.REQUIREMENT_CHANGE_REVIEW
            ),
            UserChallengeType.CLARIFICATION_REQUEST: (
                DirectorActionProposalType.EXPLAIN_ONLY
            ),
            UserChallengeType.UNKNOWN: DirectorActionProposalType.NO_ACTION,
        }
        return mapping[challenge_type]

    @staticmethod
    def _risk_for(challenge_type: UserChallengeType) -> DirectorActionRisk:
        if challenge_type in {
            UserChallengeType.DISPATCH_CHALLENGE,
            UserChallengeType.GOVERNANCE_CHALLENGE,
            UserChallengeType.REQUIREMENT_CHANGE,
        }:
            return DirectorActionRisk.HIGH
        if challenge_type in {
            UserChallengeType.INBOX_ATTENTION_CHALLENGE,
            UserChallengeType.CLARIFICATION_REQUEST,
            UserChallengeType.UNKNOWN,
        }:
            return DirectorActionRisk.LOW
        return DirectorActionRisk.MEDIUM

    @classmethod
    def _plan_revision_for(
        cls,
        challenge_type: UserChallengeType,
    ) -> PlanRevisionDraft | None:
        revision_kind = cls._revision_kind_for(challenge_type)
        if revision_kind is None:
            return None
        return PlanRevisionDraft(
            revision_kind=revision_kind,
            title=cls._revision_title_for(revision_kind),
            summary=cls._revision_summary_for(revision_kind),
            reason=cls._revision_reason_for(revision_kind),
            affected_sections=cls._affected_sections_for(revision_kind),
            proposed_changes=cls._proposed_changes_for(revision_kind),
            requires_user_confirmation=True,
        )

    @staticmethod
    def _revision_kind_for(
        challenge_type: UserChallengeType,
    ) -> PlanRevisionKind | None:
        mapping = {
            UserChallengeType.PLAN_CHALLENGE: PlanRevisionKind.SUMMARY_UPDATE,
            UserChallengeType.TASK_SCOPE_CHALLENGE: PlanRevisionKind.TASK_UPDATE,
            UserChallengeType.PRIORITY_CHALLENGE: PlanRevisionKind.PRIORITY_UPDATE,
            UserChallengeType.RISK_CHALLENGE: PlanRevisionKind.RISK_UPDATE,
            UserChallengeType.REQUIREMENT_CHANGE: PlanRevisionKind.REQUIREMENT_CHANGE,
        }
        return mapping.get(challenge_type)

    @staticmethod
    def _approval_requirement_for(
        *,
        proposal_type: DirectorActionProposalType,
        risk: DirectorActionRisk,
        requires_human_confirmation: bool,
        plan_revision: PlanRevisionDraft | None,
    ) -> ProposalApprovalRequirement:
        if proposal_type in {
            DirectorActionProposalType.EXPLAIN_ONLY,
            DirectorActionProposalType.NO_ACTION,
        }:
            return ProposalApprovalRequirement.NONE
        if risk == DirectorActionRisk.HIGH or requires_human_confirmation:
            return ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED
        if plan_revision is not None:
            return ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED
        return ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED

    @staticmethod
    def _status_for(
        approval_requirement: ProposalApprovalRequirement,
    ) -> DirectorActionProposalStatus:
        if approval_requirement == ProposalApprovalRequirement.NONE:
            return DirectorActionProposalStatus.DRAFT
        return DirectorActionProposalStatus.PENDING_USER_REVIEW

    @staticmethod
    def _safe_next_actions_for(
        *,
        proposal_type: DirectorActionProposalType,
        plan_revision: PlanRevisionDraft | None,
    ) -> list[str]:
        if proposal_type in {
            DirectorActionProposalType.EXPLAIN_ONLY,
            DirectorActionProposalType.NO_ACTION,
        }:
            return list(_SAFE_NEXT_ACTIONS_EXPLAIN_CN)
        if plan_revision is None:
            return list(_SAFE_NEXT_ACTIONS_REVIEW_ONLY_CN)
        return list(_SAFE_NEXT_ACTIONS_REVIEW_CN)

    @staticmethod
    def _title_for(proposal_type: DirectorActionProposalType) -> str:
        return {
            DirectorActionProposalType.EXPLAIN_ONLY: "仅说明原因",
            DirectorActionProposalType.PLAN_REVISION: "建议调整项目草案",
            DirectorActionProposalType.TASK_SCOPE_REVISION: "建议调整任务范围",
            DirectorActionProposalType.PRIORITY_REVISION: "建议调整优先级",
            DirectorActionProposalType.RISK_REVISION: "建议补充风险",
            DirectorActionProposalType.DISPATCH_REVIEW: "建议复核调度安排",
            DirectorActionProposalType.GOVERNANCE_REVIEW: "建议复核治理设置",
            DirectorActionProposalType.DELIVERABLE_REVIEW: "建议复核交付物",
            DirectorActionProposalType.REQUIREMENT_CHANGE_REVIEW: "建议确认需求变更",
            DirectorActionProposalType.NO_ACTION: "暂无需要处理的动作",
        }[proposal_type]

    @staticmethod
    def _summary_for(proposal_type: DirectorActionProposalType) -> str:
        return {
            DirectorActionProposalType.EXPLAIN_ONLY: "这条反馈适合先解释原因，不生成修改建议。",
            DirectorActionProposalType.PLAN_REVISION: "这条反馈适合整理为项目草案修改建议，等待确认后再处理。",
            DirectorActionProposalType.TASK_SCOPE_REVISION: "这条反馈适合整理为任务范围修改建议，等待确认后再处理。",
            DirectorActionProposalType.PRIORITY_REVISION: "这条反馈适合整理为优先级调整建议，等待确认后再处理。",
            DirectorActionProposalType.RISK_REVISION: "这条反馈适合整理为风险补充建议，等待确认后再处理。",
            DirectorActionProposalType.DISPATCH_REVIEW: "这条反馈涉及调度安排，需要人工复核后再决定。",
            DirectorActionProposalType.GOVERNANCE_REVIEW: "这条反馈涉及治理设置，需要人工复核后再决定。",
            DirectorActionProposalType.DELIVERABLE_REVIEW: "这条反馈适合先复核交付物内容，不会自动改动。",
            DirectorActionProposalType.REQUIREMENT_CHANGE_REVIEW: "这条反馈涉及需求变化，需要人工复核后再决定。",
            DirectorActionProposalType.NO_ACTION: "这条反馈暂时不能形成明确建议，可先继续澄清。",
        }[proposal_type]

    @staticmethod
    def _reason_for(proposal_type: DirectorActionProposalType) -> str:
        return {
            DirectorActionProposalType.EXPLAIN_ONLY: "用户主要是在询问原因，先说明依据更安全。",
            DirectorActionProposalType.PLAN_REVISION: "用户质疑项目草案，需要先形成可审查的修改建议。",
            DirectorActionProposalType.TASK_SCOPE_REVISION: "用户质疑任务范围，需要先形成可审查的调整建议。",
            DirectorActionProposalType.PRIORITY_REVISION: "用户质疑先后顺序，需要先形成可审查的调整建议。",
            DirectorActionProposalType.RISK_REVISION: "用户质疑风险判断，需要先形成可审查的补充建议。",
            DirectorActionProposalType.DISPATCH_REVIEW: "调度安排可能影响后续推进，必须先复核。",
            DirectorActionProposalType.GOVERNANCE_REVIEW: "治理设置可能影响成本、权限或责任分配，必须先复核。",
            DirectorActionProposalType.DELIVERABLE_REVIEW: "交付物内容需要先检查，再决定是否提出修改建议。",
            DirectorActionProposalType.REQUIREMENT_CHANGE_REVIEW: "需求变化会影响范围和验收，必须先复核。",
            DirectorActionProposalType.NO_ACTION: "当前信息不足，不能安全地提出动作建议。",
        }[proposal_type]

    @staticmethod
    def _revision_title_for(revision_kind: PlanRevisionKind) -> str:
        return {
            PlanRevisionKind.SUMMARY_UPDATE: "调整草案摘要",
            PlanRevisionKind.PHASE_UPDATE: "调整阶段安排",
            PlanRevisionKind.TASK_UPDATE: "调整任务范围",
            PlanRevisionKind.PRIORITY_UPDATE: "调整优先级",
            PlanRevisionKind.RISK_UPDATE: "补充风险说明",
            PlanRevisionKind.REQUIREMENT_CHANGE: "确认需求变更",
            PlanRevisionKind.ACCEPTANCE_CRITERIA_UPDATE: "调整验收标准",
        }[revision_kind]

    @staticmethod
    def _revision_summary_for(revision_kind: PlanRevisionKind) -> str:
        return {
            PlanRevisionKind.SUMMARY_UPDATE: "建议复核项目草案摘要，让目标、范围和阶段说明更清楚。",
            PlanRevisionKind.PHASE_UPDATE: "建议复核阶段安排，让阶段目标和顺序更清楚。",
            PlanRevisionKind.TASK_UPDATE: "建议复核任务范围，让任务内容和验收口径更清楚。",
            PlanRevisionKind.PRIORITY_UPDATE: "建议复核优先级，让先后顺序更清楚。",
            PlanRevisionKind.RISK_UPDATE: "建议补充风险说明，让风险和应对方式更清楚。",
            PlanRevisionKind.REQUIREMENT_CHANGE: "建议先确认需求变化，再决定是否调整草案。",
            PlanRevisionKind.ACCEPTANCE_CRITERIA_UPDATE: "建议复核验收标准，让完成口径更清楚。",
        }[revision_kind]

    @staticmethod
    def _revision_reason_for(revision_kind: PlanRevisionKind) -> str:
        return {
            PlanRevisionKind.SUMMARY_UPDATE: "当前反馈指向草案内容，需要先形成修改建议。",
            PlanRevisionKind.PHASE_UPDATE: "当前反馈指向阶段安排，需要先形成修改建议。",
            PlanRevisionKind.TASK_UPDATE: "当前反馈指向任务范围，需要先形成修改建议。",
            PlanRevisionKind.PRIORITY_UPDATE: "当前反馈指向优先级，需要先形成修改建议。",
            PlanRevisionKind.RISK_UPDATE: "当前反馈指向风险判断，需要先形成补充建议。",
            PlanRevisionKind.REQUIREMENT_CHANGE: "当前反馈指向需求变化，需要先确认影响范围。",
            PlanRevisionKind.ACCEPTANCE_CRITERIA_UPDATE: "当前反馈指向验收口径，需要先形成修改建议。",
        }[revision_kind]

    @staticmethod
    def _affected_sections_for(revision_kind: PlanRevisionKind) -> list[str]:
        return {
            PlanRevisionKind.SUMMARY_UPDATE: ["项目草案", "范围说明"],
            PlanRevisionKind.PHASE_UPDATE: ["阶段安排", "推进顺序"],
            PlanRevisionKind.TASK_UPDATE: ["任务范围", "验收标准"],
            PlanRevisionKind.PRIORITY_UPDATE: ["优先级", "推进顺序"],
            PlanRevisionKind.RISK_UPDATE: ["风险说明", "应对方式"],
            PlanRevisionKind.REQUIREMENT_CHANGE: ["需求范围", "验收标准"],
            PlanRevisionKind.ACCEPTANCE_CRITERIA_UPDATE: ["验收标准"],
        }[revision_kind]

    @staticmethod
    def _proposed_changes_for(revision_kind: PlanRevisionKind) -> list[str]:
        return {
            PlanRevisionKind.SUMMARY_UPDATE: [
                "重新梳理草案摘要",
                "补充受影响范围",
            ],
            PlanRevisionKind.PHASE_UPDATE: [
                "重新检查阶段顺序",
                "补充阶段调整理由",
            ],
            PlanRevisionKind.TASK_UPDATE: [
                "重新检查任务边界",
                "补充验收口径",
            ],
            PlanRevisionKind.PRIORITY_UPDATE: [
                "重新检查先后顺序",
                "补充优先级依据",
            ],
            PlanRevisionKind.RISK_UPDATE: [
                "补充风险说明",
                "补充应对建议",
            ],
            PlanRevisionKind.REQUIREMENT_CHANGE: [
                "确认新需求范围",
                "列出受影响内容",
            ],
            PlanRevisionKind.ACCEPTANCE_CRITERIA_UPDATE: [
                "补充验收标准",
                "明确完成口径",
            ],
        }[revision_kind]
