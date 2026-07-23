"""Provider-first, side-effect-free Project Director response generation."""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.domain.project_director_conversation_intelligence import (
    ConversationMode,
    DirectorResponseEnvelope,
    DirectorResponseSource,
    TurnInterpretation,
)
from app.domain.project_director_discussion import (
    DiscussionActorClaim,
    DiscussionDelta,
    DiscussionEvent,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
from app.services.project_director_discussion_context_builder_service import (
    DiscussionContextAssembly,
)


ProviderTextGenerator = Callable[[str, str, str], tuple[str, str | None]]

_FORBIDDEN_EXECUTION_CLAIMS = (
    "已创建任务",
    "已经创建任务",
    "已启动 Worker",
    "已经启动 Worker",
    "已启动 Codex",
    "已启动 Claude Code",
    "已修改正式计划",
    "已经修改正式计划",
    "已应用计划",
    "已创建 PlanVersion",
    "已写入仓库",
    "已提交代码",
    "已推送代码",
    "已部署",
    "已发布",
)


class ProjectDirectorResponseEngineService:
    """Generate and validate one natural response without persisting it."""

    def __init__(
        self,
        *,
        provider_text_generator: ProviderTextGenerator | None = None,
    ) -> None:
        self._provider_text_generator = provider_text_generator

    def generate_response(
        self,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        assistant_message_id: UUID,
        model_name: str,
        request_id: str,
    ) -> DirectorResponseEnvelope:
        """Return one validated provider envelope or a safe rule fallback."""

        self._validate_caller_inputs(
            context=context,
            interpretation=interpretation,
            assistant_message_id=assistant_message_id,
            model_name=model_name,
            request_id=request_id,
        )
        if self._provider_text_generator is None:
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason="provider_unavailable",
            )

        prompt_text = self._build_provider_prompt(
            context=context,
            interpretation=interpretation,
            assistant_message_id=assistant_message_id,
        )
        try:
            output_text, receipt_id = self._provider_text_generator(
                model_name, prompt_text, request_id
            )
        except Exception:  # noqa: BLE001 - provider failures are intentionally opaque
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason="provider_failed",
            )
        if not isinstance(output_text, str) or not output_text.strip():
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason="provider_empty_output",
            )

        parsed, parse_reason = self._parse_envelope(output_text)
        if parsed is None:
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason=parse_reason,
            )
        if parsed.source != DirectorResponseSource.PROVIDER:
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason="provider_source_invalid",
            )
        if parsed.turn_interpretation.model_dump(mode="python") != interpretation.model_dump(
            mode="python"
        ):
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason="provider_interpretation_mismatch",
            )
        if self._has_forbidden_execution_claim(parsed.answer):
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason="provider_forbidden_execution_claim",
            )

        delta_reason = self._validate_delta_sources(
            context=context,
            delta=parsed.discussion_delta,
            assistant_message_id=assistant_message_id,
        )
        if delta_reason is not None:
            return self._fallback(
                context=context, interpretation=interpretation, reason=delta_reason
            )
        proposal_reason = self._validate_formalization_proposal(
            context=context,
            interpretation=interpretation,
            envelope=parsed,
            assistant_message_id=assistant_message_id,
        )
        if proposal_reason is not None:
            return self._fallback(
                context=context, interpretation=interpretation, reason=proposal_reason
            )

        requires_confirmation = (
            parsed.requires_confirmation
            or parsed.formalization_proposal is not None
            or (
                interpretation.formal_action_requested
                and not interpretation.hypothetical_action
            )
        )
        return parsed.model_copy(
            update={
                "answer": parsed.answer[:10_000],
                "requires_confirmation": requires_confirmation,
                "source_detail": self._provider_source_detail(receipt_id),
            }
        )

    def _validate_caller_inputs(
        self,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        assistant_message_id: UUID,
        model_name: str,
        request_id: str,
    ) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("director_response_model_name_invalid")
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("director_response_request_id_invalid")
        if context.current_user_message.role != ProjectDirectorMessageRole.USER:
            raise ValueError("director_response_current_message_role_invalid")

        session_ids = [
            context.current_user_message.session_id,
            context.pinned_formal_facts.session_id,
        ]
        if context.active_workspace is not None:
            session_ids.append(context.active_workspace.workspace.session_id)
        if len(set(session_ids)) != 1:
            raise ValueError("director_response_context_session_mismatch")

        project_ids = [
            context.current_user_message.related_project_id,
            context.pinned_formal_facts.project_id,
        ]
        if context.active_workspace is not None:
            project_ids.append(context.active_workspace.workspace.project_id)
        if any(project_id != project_ids[0] for project_id in project_ids[1:]):
            raise ValueError("director_response_context_project_mismatch")
        if context.plan.conversation_mode != interpretation.conversation_mode:
            raise ValueError("director_response_interpretation_mode_mismatch")
        if (
            context.plan.referenced_option_ids
            != tuple(interpretation.referenced_option_ids)
            or context.plan.referenced_entity_ids
            != tuple(interpretation.referenced_entity_ids)
        ):
            raise ValueError("director_response_interpretation_references_mismatch")
        if assistant_message_id == context.current_user_message.id or any(
            assistant_message_id == message.id for message in context.recent_raw_messages
        ):
            raise ValueError("director_response_assistant_message_id_conflict")

    @classmethod
    def _build_provider_prompt(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        assistant_message_id: UUID,
    ) -> str:
        payload = {
            "behavior_instructions": [
                "Directly and naturally answer the user question.",
                "Prefer pinned formal facts and retain every active constraint.",
                "Use relevant historical events to explain prior rejection when applicable.",
                "Acknowledge information absent from this context.",
                "Do not repeat the full internal safety boundaries in ordinary discussion.",
                "Do not claim that any formal action has already been executed.",
                "DiscussionDelta is only a proposal and must not be described as written.",
                "Only an explicit formalization request may include FormalizationProposal.",
                "Return exactly one JSON object and no Markdown code fence.",
                "turn_interpretation must be an exact copy of caller_interpretation.",
                "Do not wrap caller_interpretation under an interpretation key.",
                "For ordinary discussion, use discussion_delta={\"operations\": []} and formalization_proposal=null.",
            ],
            "output_schema": {
                "answer": "user-visible natural response",
                "turn_interpretation": interpretation.model_dump(mode="json"),
                "discussion_delta": {"operations": []},
                "formalization_proposal": None,
                "requires_confirmation": False,
                "source": "provider",
                "source_detail": "project_director_conversational_intelligence",
            },
            "source_id_rules": {
                "user_explicit_or_user_inferred": "source_message_ids must only use visible USER message IDs",
                "assistant_proposal": (
                    "source_message_ids must contain reserved_assistant_message_id "
                    "and only use visible ASSISTANT message IDs"
                ),
                "forbidden_actor_claims": [
                    DiscussionActorClaim.SYSTEM_FACT.value,
                    DiscussionActorClaim.FORMAL_PROJECT_FACT.value,
                ],
                "supersedes_event_id": "must use only visible discussion event IDs",
            },
            "silent_governance_instruction": (
                "silent_governance_boundaries are internal behavior boundaries; do not "
                "repeat them item by item unless a real formal action request needs a "
                "brief confirmation explanation"
            ),
            "context": {
                "pinned_formal_facts": cls._serialize_pinned_facts(context),
                "recent_raw_messages": [
                    cls._serialize_message(message)
                    for message in context.recent_raw_messages
                ],
                "active_workspace": cls._serialize_active_workspace(context),
                "relevant_events": [
                    cls._serialize_event(
                        item.event, resolved_status=item.resolved_status.value
                    )
                    for item in context.relevant_events
                ],
                "current_user_message": cls._serialize_message(
                    context.current_user_message
                ),
                "silent_governance_boundaries": list(
                    context.silent_governance_boundaries
                ),
                "discussion_context_plan": {
                    "conversation_mode": context.plan.conversation_mode.value,
                    "selected_sections": [
                        section.value for section in context.plan.selected_sections
                    ],
                    "formal_fact_scope": context.plan.formal_fact_scope.value,
                    "recent_message_limit": context.plan.recent_message_limit,
                    "relevant_event_limit": context.plan.relevant_event_limit,
                    "included_event_statuses": [
                        item.value for item in context.plan.included_event_statuses
                    ],
                    "included_event_types": [
                        item.value for item in context.plan.included_event_types
                    ],
                    "referenced_option_ids": [
                        str(item) for item in context.plan.referenced_option_ids
                    ],
                    "referenced_entity_ids": [
                        str(item) for item in context.plan.referenced_entity_ids
                    ],
                    "retrieval_disposition": context.plan.retrieval_disposition.value,
                    "reason_codes": list(context.plan.reason_codes),
                },
                "caller_interpretation": interpretation.model_dump(mode="json"),
                "reserved_assistant_message_id": str(assistant_message_id),
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _serialize_pinned_facts(context: DiscussionContextAssembly) -> dict[str, Any]:
        facts = context.pinned_formal_facts
        return {
            "scope": facts.scope.value,
            "session_id": str(facts.session_id),
            "project_id": str(facts.project_id) if facts.project_id else None,
            "goal_text": facts.goal_text,
            "constraints": facts.constraints,
            "session_status": facts.session_status,
            "goal_summary": facts.goal_summary,
            "confirmed_at": facts.confirmed_at,
            "latest_plan_version": facts.latest_plan_version,
            "task_creation": facts.task_creation,
            "project_snapshot": facts.project_snapshot,
            "task_snapshot": facts.task_snapshot,
        }

    @classmethod
    def _serialize_active_workspace(
        cls, context: DiscussionContextAssembly
    ) -> dict[str, Any] | None:
        if context.active_workspace is None:
            return None
        workspace = context.active_workspace.workspace
        return {
            "workspace": {
                "session_id": str(workspace.session_id),
                "project_id": str(workspace.project_id) if workspace.project_id else None,
                "topic": workspace.topic,
                "discussion_status": workspace.discussion_status.value,
                "active_option_ids": [str(item) for item in workspace.active_option_ids],
                "preferred_option_id": (
                    str(workspace.preferred_option_id)
                    if workspace.preferred_option_id
                    else None
                ),
                "active_constraint_ids": [
                    str(item) for item in workspace.active_constraint_ids
                ],
                "open_question_ids": [str(item) for item in workspace.open_question_ids],
                "temporary_conclusion_ids": [
                    str(item) for item in workspace.temporary_conclusion_ids
                ],
                "confirmed_decision_ids": [
                    str(item) for item in workspace.confirmed_decision_ids
                ],
                "latest_user_correction_event_id": (
                    str(workspace.latest_user_correction_event_id)
                    if workspace.latest_user_correction_event_id
                    else None
                ),
                "version_no": workspace.version_no,
                "last_event_sequence_no": workspace.last_event_sequence_no,
            },
            "active_events": [
                cls._serialize_event(event)
                for event in context.active_workspace.active_events
            ],
        }

    @staticmethod
    def _serialize_message(message: ProjectDirectorMessage) -> dict[str, Any]:
        return {
            "id": str(message.id),
            "session_id": str(message.session_id),
            "role": message.role.value,
            "content": message.content,
            "sequence_no": message.sequence_no,
            "related_project_id": (
                str(message.related_project_id)
                if message.related_project_id
                else None
            ),
            "created_at": message.created_at.isoformat(),
        }

    @staticmethod
    def _serialize_event(
        event: DiscussionEvent, *, resolved_status: str | None = None
    ) -> dict[str, Any]:
        result = {
            "id": str(event.id),
            "session_id": str(event.session_id),
            "project_id": str(event.project_id) if event.project_id else None,
            "sequence_no": event.sequence_no,
            "event_type": event.event_type.value,
            "subject_key": event.subject_key,
            "content": event.content,
            "payload": event.payload,
            "source_message_ids": [str(item) for item in event.source_message_ids],
            "supersedes_event_id": (
                str(event.supersedes_event_id) if event.supersedes_event_id else None
            ),
            "created_by": event.created_by.value,
            "confidence": event.confidence,
            "created_at": event.created_at.isoformat(),
        }
        if resolved_status is None:
            result["status"] = event.status.value
        else:
            result["resolved_status"] = resolved_status
        return result

    @staticmethod
    def _parse_envelope(
        output_text: str,
    ) -> tuple[DirectorResponseEnvelope | None, str]:
        text = output_text.strip()
        fence = chr(96) * 3
        if text.startswith(fence):
            lines = text.splitlines()
            if (
                len(lines) < 2
                or lines[0].strip().lower() not in {fence, f"{fence}json"}
                or lines[-1].strip() != fence
            ):
                return None, "provider_response_not_json"
            text = "\n".join(lines[1:-1]).strip()
        try:
            raw, end = json.JSONDecoder().raw_decode(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, "provider_response_not_json"
        if text[end:].strip():
            return None, "provider_response_not_json"
        if not isinstance(raw, dict):
            return None, "provider_response_not_object"
        try:
            return DirectorResponseEnvelope.model_validate(raw), ""
        except ValidationError:
            return None, "provider_envelope_invalid"

    @staticmethod
    def _has_forbidden_execution_claim(answer: str) -> bool:
        return any(claim in answer for claim in _FORBIDDEN_EXECUTION_CLAIMS)

    @staticmethod
    def _visible_message_roles(
        context: DiscussionContextAssembly, assistant_message_id: UUID
    ) -> dict[UUID, ProjectDirectorMessageRole]:
        roles = {message.id: message.role for message in context.recent_raw_messages}
        roles[context.current_user_message.id] = context.current_user_message.role
        roles[assistant_message_id] = ProjectDirectorMessageRole.ASSISTANT
        return roles

    @classmethod
    def _validate_delta_sources(
        cls,
        *,
        context: DiscussionContextAssembly,
        delta: DiscussionDelta,
        assistant_message_id: UUID,
    ) -> str | None:
        message_roles = cls._visible_message_roles(context, assistant_message_id)
        visible_event_ids = cls._visible_event_ids(context)
        for operation in delta.operations:
            if operation.actor_claim in {
                DiscussionActorClaim.SYSTEM_FACT,
                DiscussionActorClaim.FORMAL_PROJECT_FACT,
            }:
                return "provider_delta_authority_claim_invalid"
            source_ids = tuple(operation.source_message_ids)
            if operation.actor_claim in {
                DiscussionActorClaim.USER_EXPLICIT,
                DiscussionActorClaim.USER_INFERRED,
            }:
                if (
                    not source_ids
                    or assistant_message_id in source_ids
                    or any(
                        message_roles.get(message_id) != ProjectDirectorMessageRole.USER
                        for message_id in source_ids
                    )
                ):
                    return "provider_delta_user_source_invalid"
            elif operation.actor_claim == DiscussionActorClaim.ASSISTANT_PROPOSAL:
                if (
                    assistant_message_id not in source_ids
                    or any(
                        message_roles.get(message_id)
                        != ProjectDirectorMessageRole.ASSISTANT
                        for message_id in source_ids
                    )
                ):
                    return "provider_delta_assistant_source_invalid"
            if (
                operation.supersedes_event_id is not None
                and operation.supersedes_event_id not in visible_event_ids
            ):
                return "provider_delta_supersede_target_not_visible"
        return None

    @staticmethod
    def _visible_event_ids(context: DiscussionContextAssembly) -> set[UUID]:
        event_ids = {item.event.id for item in context.relevant_events}
        if context.active_workspace is not None:
            event_ids.update(
                event.id for event in context.active_workspace.active_events
            )
        return event_ids

    @classmethod
    def _validate_formalization_proposal(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        envelope: DirectorResponseEnvelope,
        assistant_message_id: UUID,
    ) -> str | None:
        proposal = envelope.formalization_proposal
        if proposal is None:
            return None
        if (
            interpretation.conversation_mode
            != ConversationMode.FORMALIZATION_REQUEST
            or not interpretation.formal_action_requested
            or interpretation.hypothetical_action
        ):
            return "provider_formalization_not_requested"
        if context.active_workspace is None:
            return "provider_formalization_workspace_missing"
        if proposal.workspace_version != context.active_workspace.workspace.version_no:
            return "provider_formalization_workspace_version_mismatch"
        visible_message_ids = set(
            cls._visible_message_roles(context, assistant_message_id)
        )
        if (
            context.current_user_message.id not in proposal.source_message_ids
            or any(
                message_id not in visible_message_ids
                for message_id in proposal.source_message_ids
            )
        ):
            return "provider_formalization_source_message_invalid"
        visible_event_ids = cls._visible_event_ids(context)
        if any(
            event_id not in visible_event_ids
            for change in proposal.changes
            for event_id in change.source_event_ids
        ):
            return "provider_formalization_source_event_invalid"
        return None

    @staticmethod
    def _provider_source_detail(receipt_id: str | None) -> str:
        receipt = receipt_id.strip()[:120] if isinstance(receipt_id, str) else ""
        return f"p26_f1_provider_response;receipt={receipt or 'missing'}"[:300]

    @staticmethod
    def _fallback(
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        reason: str,
    ) -> DirectorResponseEnvelope:
        mode = interpretation.conversation_mode
        if mode == ConversationMode.STATUS_QUERY:
            facts = context.pinned_formal_facts
            summary = facts.goal_summary or facts.goal_text
            answer = f"当前会话状态为 {facts.session_status}。{summary[:300]}"
        elif mode in {
            ConversationMode.ACTION_REQUEST,
            ConversationMode.FORMALIZATION_REQUEST,
        }:
            answer = "当前没有执行正式动作；该请求需要确认和后续治理检查。"
        else:
            answer = "当前未能生成完整回答；讨论上下文仍然保留，可以继续基于当前问题讨论。"
        return DirectorResponseEnvelope(
            answer=answer,
            turn_interpretation=interpretation,
            discussion_delta=DiscussionDelta(),
            formalization_proposal=None,
            requires_confirmation=(
                interpretation.formal_action_requested
                and not interpretation.hypothetical_action
            ),
            source=DirectorResponseSource.RULE_FALLBACK,
            source_detail=f"p26_f1_rule_fallback;reason={reason}",
        )
