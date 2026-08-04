"""Provider-first, side-effect-free Project Director response generation."""

from __future__ import annotations

from collections.abc import Callable
import json
import re
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
    DiscussionDeltaOperationType,
    DiscussionEvent,
    DiscussionEventStatus,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
from app.services.project_director_discussion_context_builder_service import (
    DiscussionContextAssembly,
)
from app.services.project_director_discussion_delta_gate_service import (
    discussion_delta_operation_contract_rows,
    validate_discussion_operation_admission,
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
        (
            validated,
            validation_reason,
            initial_raw_envelope,
            validation_diagnostics,
        ) = self._validate_provider_envelope(
            context=context,
            interpretation=interpretation,
            assistant_message_id=assistant_message_id,
            output_text=output_text,
        )
        validation_reason = self._repair_reason_for_context(
            context=context,
            interpretation=interpretation,
            reason=validation_reason,
        )
        if validated is not None:
            return self._successful_provider_response(
                envelope=validated, receipt_id=receipt_id, repaired=False
            )
        if not self._repairable_reason(validation_reason):
            return self._fallback(
                context=context, interpretation=interpretation, reason=validation_reason
            )

        if (
            validation_reason
            == "provider_formalization_proposal_invalid:provider_envelope_invalid"
            and initial_raw_envelope is not None
        ):
            repair_prompt = self._build_formalization_envelope_repair_prompt(
                context=context,
                interpretation=interpretation,
                assistant_message_id=assistant_message_id,
                repair_reason=validation_reason,
                initial_raw_envelope=initial_raw_envelope,
                validation_diagnostics=validation_diagnostics,
            )
            repair_request_id = f"{request_id}-repair"
        else:
            repair_prompt = self._build_provider_prompt(
                context=context,
                interpretation=interpretation,
                assistant_message_id=assistant_message_id,
                repair_reason=validation_reason,
            )
            repair_request_id = request_id
        try:
            repaired_text, repaired_receipt_id = self._provider_text_generator(
                model_name, repair_prompt, repair_request_id
            )
        except Exception:  # noqa: BLE001 - never retry a failed provider request again
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason=f"provider_repair_failed:{validation_reason}",
            )
        if not isinstance(repaired_text, str) or not repaired_text.strip():
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason=f"provider_repair_failed:{validation_reason}",
            )
        repaired, repair_reason, _, _ = self._validate_provider_envelope(
            context=context,
            interpretation=interpretation,
            assistant_message_id=assistant_message_id,
            output_text=repaired_text,
        )
        repair_reason = self._repair_reason_for_context(
            context=context,
            interpretation=interpretation,
            reason=repair_reason,
        )
        if repaired is None:
            return self._fallback(
                context=context,
                interpretation=interpretation,
                reason=f"provider_repair_failed:{repair_reason}",
            )
        return self._successful_provider_response(
            envelope=repaired, receipt_id=repaired_receipt_id, repaired=True
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
        repair_reason: str | None = None,
    ) -> str:
        expected_workspace_version = cls._expected_workspace_version(
            context=context, interpretation=interpretation
        )
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
                "For a non-hypothetical formalization request with workspace version at least 1, include both request_formalization and a FormalizationProposal.",
                "Return exactly one JSON object and no Markdown code fence.",
                "turn_interpretation must be an exact copy of caller_interpretation.",
                "Do not wrap caller_interpretation under an interpretation key.",
                "An empty discussion_delta is allowed only when the user message does not change discussion state.",
                "A topic, option, preference, rejection, explicit constraint, correction, decision, or formalization request must produce at least one operation.",
                "USER_EXPLICIT operations must cite the current real user message ID or another visible real USER message ID.",
                "Do not use USER_INFERRED to represent what the user explicitly said.",
                "ASSISTANT_PROPOSAL operations must cite reserved_assistant_message_id.",
                "Never invent message IDs or event IDs, and never use SYSTEM_FACT or FORMAL_PROJECT_FACT.",
                "A new option must use a stable UUID target_id; changes to an existing option must reuse its visible option_id.",
                "supersedes_event_id may only cite a visible effective event.",
                (
                    "For prefer_option on an active option, reuse the existing option_id, "
                    "set supersedes_event_id to null, do not manually supersede the old "
                    "preferred event, and rely on the reducer to keep one preferred option. "
                    "When the user explicitly reverses a prior rejection of an inactive "
                    "option, reuse that same option_id and set supersedes_event_id to its "
                    "visible effective option_rejected event. This is a user viewpoint "
                    "reversal, not add_option: do not generate a new UUID or duplicate "
                    "the option. In both cases use actor_claim=user_explicit and cite the "
                    "current user message ID."
                ),
                (
                    "When the user explicitly chooses, re-chooses, or changes preference "
                    "to a visible option, the delta must contain a legal prefer_option "
                    "operation. record_user_correction may supplement that operation but "
                    "cannot replace it. For a preference reversal, point prefer_option at "
                    "the newly chosen visible option rather than the current preferred "
                    "option. A rejected option must keep its original option_id and "
                    "supersede its effective rejection event; do not add_option or create "
                    "a new UUID."
                ),
                (
                    "Discussion, hypotheses, questions, comparisons, negations, and "
                    "ambiguous approval are not a current preference selection. A true "
                    "explicit selection requires exactly one prefer_option; "
                    "record_user_correction may only supplement it. Never emit multiple "
                    "prefer_option operations. When caller_interpretation has exactly one "
                    "referenced_option_id, use that ID. Do not retain the old preferred "
                    "option for a reversal, add_option, or generate a UUID."
                ),
                (
                    "For a required formalization, include request_formalization and a "
                    "FormalizationProposal together; request_formalization uses "
                    "actor_claim=user_explicit, the current user message ID, and "
                    "supersedes_event_id=null; the proposal uses "
                    "expected_workspace_version_after_this_turn and only visible pre-turn "
                    "event IDs, does not create a PlanVersion, and does not claim execution."
                ),
            ],
            "output_schema": cls._output_schema(
                interpretation=interpretation,
                expected_workspace_version=expected_workspace_version,
            ),
            "discussion_delta_operation_contract": {
                "required_fields": [
                    "op",
                    "target_id",
                    "subject_key",
                    "content",
                    "payload",
                    "source_message_ids",
                    "actor_claim",
                    "supersedes_event_id",
                ],
                "allowed_ops": [
                    "set_topic",
                    "add_option",
                    "update_option",
                    "prefer_option",
                    "reject_option",
                    "add_constraint",
                    "update_constraint",
                    "supersede_constraint",
                    "add_concern",
                    "add_assumption",
                    "reject_assumption",
                    "add_open_question",
                    "resolve_open_question",
                    "add_temporary_conclusion",
                    "record_user_correction",
                    "confirm_decision",
                    "request_formalization",
                    "cancel_formalization",
                ],
                "field_rules": {
                    "target_id": "new or visible active option UUID according to operation_rules; otherwise null",
                    "subject_key": "stable non-empty semantic key",
                    "content": "the user claim, reason, or proposed discussion content",
                    "payload": "structured operation details; option operations use payload.option_id equal to target_id",
                    "source_message_ids": "visible real message IDs matching actor_claim",
                    "actor_claim": "user_explicit, user_inferred, or assistant_proposal only",
                    "supersedes_event_id": "visible effective event UUID or null",
                },
                "operation_rules": discussion_delta_operation_contract_rows(
                    provider_preflight=True
                ),
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
                "supersedes_event_id": "must use only visible effective discussion event IDs",
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
                "expected_workspace_version_after_this_turn": expected_workspace_version,
            },
        }
        if repair_reason is not None:
            payload["repair_instruction"] = {
                "previous_failure_reason": repair_reason,
                "instruction": (
                    "Repair the prior output without changing the user meaning. Output only "
                    "one JSON object matching the complete schema. Do not claim execution. "
                    + cls._repair_requirement(repair_reason)
                ),
            }
        if cls._formalization_proposal_required(
            context=context, interpretation=interpretation
        ):
            payload["behavior_instructions"].extend(
                [
                    "For this formalization request, return the complete canonical Envelope, not a FormalizationProposal fragment.",
                    "Use exactly these Envelope top-level fields: answer, turn_interpretation, discussion_delta, formalization_proposal, requires_confirmation, source, and source_detail.",
                    "Do not use aliases or wrapper fields such as proposalId, proposal_target, target_type, workspaceVersion, proposal_summary, required_confirmation, linked_pre_turn_event_ids, visible_pre_turn_event_ids, proposal, formalizationProposal, or data.",
                    "formalization_proposal must use canonical proposal_id, target, workspace_version, summary, changes, source_message_ids, risk_summary, requires_confirmation, and status fields; every change must use change_type, subject_key, summary, and source_event_ids.",
                ]
            )
            payload["formalization_envelope_contract"] = (
                cls._formalization_envelope_contract(
                    context=context,
                    interpretation=interpretation,
                    assistant_message_id=assistant_message_id,
                )
            )
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _build_formalization_envelope_repair_prompt(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        assistant_message_id: UUID,
        repair_reason: str,
        initial_raw_envelope: dict[str, Any],
        validation_diagnostics: list[dict[str, Any]],
    ) -> str:
        """Request one canonical Envelope repair for a formalization Pydantic failure."""

        payload = {
            "repair_instruction": {
                "previous_failure_reason": repair_reason,
                "instructions": [
                    "Return exactly one complete canonical Envelope JSON object and no Markdown.",
                    "Do not return only a formalization_proposal fragment.",
                    "Preserve the user intent plus the legal answer and DiscussionDelta semantics from the first response; repair only the Envelope and FormalizationProposal structure.",
                    "Do not invent message IDs or event IDs, and do not reference the unpersisted request_formalization Event from this turn.",
                    "Do not claim that a PlanVersion was created or that any task was executed.",
                ],
            },
            "initial_provider_envelope_json": initial_raw_envelope,
            "safe_pydantic_validation_errors": validation_diagnostics,
            "formalization_envelope_contract": cls._formalization_envelope_contract(
                context=context,
                interpretation=interpretation,
                assistant_message_id=assistant_message_id,
            ),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _formalization_envelope_contract(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        assistant_message_id: UUID,
    ) -> dict[str, Any]:
        """Describe the canonical formalization Envelope without manufacturing data."""

        expected_workspace_version = cls._expected_workspace_version(
            context=context, interpretation=interpretation
        )
        visible_user_message_ids = sorted(
            str(message_id)
            for message_id, role in cls._visible_message_roles(
                context, assistant_message_id
            ).items()
            if role == ProjectDirectorMessageRole.USER
        )
        visible_pre_turn_event_ids = sorted(
            str(event_id) for event_id in cls._visible_event_ids(context)
        )
        return {
            "canonical_envelope_schema": {
                "answer": "non-empty user-visible natural response",
                "turn_interpretation": interpretation.model_dump(mode="json"),
                "discussion_delta": {
                    "operations": [
                        {
                            "op": "request_formalization",
                            "target_id": None,
                            "subject_key": "formalization:request",
                            "content": "user formalization request",
                            "payload": {},
                            "source_message_ids": [
                                str(context.current_user_message.id)
                            ],
                            "actor_claim": DiscussionActorClaim.USER_EXPLICIT.value,
                            "supersedes_event_id": None,
                        }
                    ]
                },
                "formalization_proposal": {
                    "proposal_id": "provider-generated UUID",
                    "target": "plan_revision",
                    "workspace_version": expected_workspace_version,
                    "summary": "proposal summary",
                    "changes": [
                        {
                            "change_type": "add, update, or remove",
                            "subject_key": "stable semantic key",
                            "summary": "draft-only change",
                            "source_event_ids": [
                                "visible pre-turn discussion event UUID"
                            ],
                        }
                    ],
                    "source_message_ids": ["visible USER message UUID"],
                    "source_event_ids": (
                        "optional; if present, the deterministic ordered union of "
                        "changes.source_event_ids"
                    ),
                    "risk_summary": "confirmation and implementation risks",
                    "requires_confirmation": True,
                    "status": "proposed",
                },
                "requires_confirmation": True,
                "source": "provider",
                "source_detail": "non-empty provider description",
            },
            "top_level_field_rule": {
                "required": [
                    "answer",
                    "turn_interpretation",
                    "discussion_delta",
                    "formalization_proposal",
                    "requires_confirmation",
                    "source",
                    "source_detail",
                ],
                "forbidden_aliases_or_wrappers": [
                    "proposalId",
                    "proposal_target",
                    "target_type",
                    "workspaceVersion",
                    "proposal_summary",
                    "required_confirmation",
                    "linked_pre_turn_event_ids",
                    "visible_pre_turn_event_ids",
                    "proposal",
                    "formalizationProposal",
                    "data",
                ],
            },
            "identity_context": {
                "caller_interpretation": interpretation.model_dump(mode="json"),
                "current_user_message_id": str(context.current_user_message.id),
                "reserved_assistant_message_id": str(assistant_message_id),
                "expected_workspace_version_after_this_turn": expected_workspace_version,
                "visible_user_message_ids": visible_user_message_ids,
                "visible_pre_turn_event_ids": visible_pre_turn_event_ids,
            },
        }

    @staticmethod
    def _output_schema(
        *, interpretation: TurnInterpretation, expected_workspace_version: int | None
    ) -> dict[str, Any]:
        return {
            "answer": "user-visible natural response",
            "turn_interpretation": interpretation.model_dump(mode="json"),
            "discussion_delta": {
                "operations": [
                    {
                        "op": "one allowed operation",
                        "target_id": "UUID or null",
                        "subject_key": "stable semantic key or null",
                        "content": "non-empty operation content",
                        "payload": {},
                        "source_message_ids": ["visible message UUID"],
                        "actor_claim": "user_explicit",
                        "supersedes_event_id": "visible event UUID or null",
                    }
                ]
            },
            "formalization_proposal": {
                "proposal_id": "UUID",
                "target": "plan_revision",
                "workspace_version": expected_workspace_version,
                "summary": "proposal summary",
                "changes": [
                    {
                        "change_type": "add, update, or remove",
                        "subject_key": "stable semantic key",
                        "summary": "draft-only change",
                        "source_event_ids": ["visible discussion event UUID"],
                    }
                ],
                "source_message_ids": ["visible user message UUID"],
                "risk_summary": "confirmation and implementation risks",
                "requires_confirmation": True,
                "status": "proposed",
            }
            if expected_workspace_version is not None
            else None,
            "requires_confirmation": expected_workspace_version is not None,
            "source": "provider",
            "source_detail": "project_director_conversational_intelligence",
        }

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
    ) -> tuple[
        DirectorResponseEnvelope | None,
        str,
        dict[str, Any] | None,
        list[dict[str, Any]],
    ]:
        text = output_text.strip()
        fence = chr(96) * 3
        if text.startswith(fence):
            lines = text.splitlines()
            if (
                len(lines) < 2
                or lines[0].strip().lower() not in {fence, f"{fence}json"}
                or lines[-1].strip() != fence
            ):
                return None, "provider_response_not_json", None, []
            text = "\n".join(lines[1:-1]).strip()
        try:
            raw, end = json.JSONDecoder().raw_decode(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, "provider_response_not_json", None, []
        if text[end:].strip():
            return None, "provider_response_not_json", None, []
        if not isinstance(raw, dict):
            return None, "provider_response_not_object", None, []
        try:
            return DirectorResponseEnvelope.model_validate(raw), "", None, []
        except ValidationError as exc:
            return (
                None,
                "provider_envelope_invalid",
                raw,
                ProjectDirectorResponseEngineService._safe_pydantic_diagnostics(exc),
            )

    @staticmethod
    def _safe_pydantic_diagnostics(
        error: ValidationError,
    ) -> list[dict[str, Any]]:
        """Keep only structural Pydantic diagnostics for an in-memory repair prompt."""

        diagnostics: list[dict[str, Any]] = []
        for item in error.errors():
            raw_loc = item.get("loc", ())
            loc = (
                [str(part) for part in raw_loc]
                if isinstance(raw_loc, (tuple, list))
                else []
            )
            diagnostics.append(
                {
                    "loc": loc,
                    "type": str(item.get("type", "")),
                    "msg": str(item.get("msg", "")),
                }
            )
        return diagnostics

    def _validate_provider_envelope(
        self,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        assistant_message_id: UUID,
        output_text: str,
    ) -> tuple[
        DirectorResponseEnvelope | None,
        str,
        dict[str, Any] | None,
        list[dict[str, Any]],
    ]:
        parsed, parse_reason, raw_envelope, validation_diagnostics = self._parse_envelope(
            output_text
        )
        if parsed is None:
            return None, parse_reason, raw_envelope, validation_diagnostics
        if parsed.source != DirectorResponseSource.PROVIDER:
            return None, "provider_source_invalid", None, []
        if parsed.turn_interpretation.model_dump(mode="python") != interpretation.model_dump(
            mode="python"
        ):
            return None, "provider_interpretation_mismatch", None, []
        if self._has_forbidden_execution_claim(parsed.answer):
            return None, "provider_forbidden_execution_claim", None, []

        delta_contract_reason = self._validate_delta_operation_contract(
            context=context,
            delta=parsed.discussion_delta,
        )
        if delta_contract_reason is not None:
            return None, delta_contract_reason, None, []
        delta_reason = self._validate_delta_sources(
            context=context,
            delta=parsed.discussion_delta,
            assistant_message_id=assistant_message_id,
        )
        if delta_reason is not None:
            return None, delta_reason, None, []
        delta_requirement_reason = self._validate_delta_requirement(
            context=context,
            interpretation=interpretation,
            delta=parsed.discussion_delta,
        )
        if delta_requirement_reason is not None:
            return None, delta_requirement_reason, None, []
        proposal_reason = self._validate_formalization_proposal(
            context=context,
            interpretation=interpretation,
            envelope=parsed,
            assistant_message_id=assistant_message_id,
        )
        if proposal_reason is not None:
            return None, proposal_reason, None, []
        return parsed, "", None, []

    @staticmethod
    def _successful_provider_response(
        *,
        envelope: DirectorResponseEnvelope,
        receipt_id: str | None,
        repaired: bool,
    ) -> DirectorResponseEnvelope:
        interpretation = envelope.turn_interpretation
        requires_confirmation = (
            envelope.requires_confirmation
            or envelope.formalization_proposal is not None
            or (
                interpretation.formal_action_requested
                and not interpretation.hypothetical_action
            )
        )
        return envelope.model_copy(
            update={
                "answer": envelope.answer[:10_000],
                "requires_confirmation": requires_confirmation,
                "source_detail": ProjectDirectorResponseEngineService._provider_source_detail(
                    receipt_id, repaired=repaired
                ),
            }
        )

    @staticmethod
    def _repairable_reason(reason: str) -> bool:
        return reason in {
            "provider_response_not_json",
            "provider_response_not_object",
            "provider_envelope_invalid",
            "provider_interpretation_mismatch",
            "provider_delta_required",
            "provider_delta_operation_invalid",
            "provider_delta_explicit_source_required",
            "provider_formalization_request_delta_missing",
            "provider_formalization_proposal_missing",
            "provider_formalization_workspace_version_mismatch",
            "provider_formalization_source_message_invalid",
            "provider_formalization_source_event_invalid",
        } or reason.startswith(("provider_delta_", "provider_formalization_proposal_invalid:"))

    @classmethod
    def _repair_reason_for_context(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        reason: str,
    ) -> str:
        if (
            reason == "provider_envelope_invalid"
            and cls._formalization_proposal_required(
                context=context, interpretation=interpretation
            )
        ):
            return "provider_formalization_proposal_invalid:provider_envelope_invalid"
        return reason

    @staticmethod
    def _repair_requirement(reason: str) -> str:
        if reason.startswith("provider_formalization_proposal_invalid:"):
            return (
                "Return a complete FormalizationProposal with proposal_id, "
                "target=plan_revision, expected workspace_version, summary, changes, "
                "source_message_ids, risk_summary, requires_confirmation=true, and "
                "status=proposed. Each change needs change_type, subject_key, summary, "
                "and source_event_ids drawn only from visible pre-turn events."
            )
        requirements = {
            "provider_delta_rejected_option_target_not_found": (
                "Do not use a new UUID to imitate a previously rejected option. A "
                "reselection must reuse an option_id with a visible effective "
                "option_rejected event; otherwise regenerate a legal delta without "
                "inventing an option or event ID."
            ),
            "provider_delta_rejected_option_supersedes_required": (
                "When the visible context contains the same inactive option_id and its "
                "visible effective option_rejected event, retain prefer_option, reuse "
                "that target_id, set supersedes_event_id to that rejection event, use "
                "actor_claim=user_explicit, and cite the current USER message. Do not "
                "add_option or generate a new UUID. If no such rejection event is "
                "visible, regenerate a legal delta without inventing an event ID."
            ),
            "provider_delta_rejected_option_target_mismatch": (
                "Use the visible effective option_rejected event whose payload.option_id "
                "matches prefer_option.target_id. Do not reuse a rejection for another "
                "option, add_option, or generate a new UUID."
            ),
            "provider_delta_rejected_option_supersedes_target_incompatible": (
                "For a rejected-option reselection, supersedes_event_id must cite the "
                "same option's visible effective option_rejected event. Do not invent "
                "an event ID or supersede another event type."
            ),
            "provider_delta_rejected_option_source_invalid": (
                "For a rejected-option reselection, use actor_claim=user_explicit and "
                "include the current real USER message ID in source_message_ids."
            ),
            "provider_delta_preference_operation_missing": (
                "The user explicitly selected a preference. Preserve any legal "
                "record_user_correction operation, and add or correct prefer_option "
                "using the user-selected visible option ID. If the target was previously "
                "rejected, reuse its original option_id and supersede its effective "
                "option_rejected event. Use the current USER message ID, actor_claim="
                "user_explicit, and do not add_option or generate a new UUID."
            ),
            "provider_delta_preference_operation_ambiguous": (
                "Keep exactly one prefer_option for this turn's uniquely explicit "
                "selection. You may retain a legal record_user_correction, but do not "
                "produce multiple final preferences or create an option."
            ),
            "provider_delta_preference_target_mismatch": (
                "Set prefer_option.target_id to the sole referenced visible option. Do "
                "not retain the old preferred option, select another visible option the "
                "user did not choose, or create a new UUID."
            ),
            "provider_delta_preference_target_ambiguous": (
                "Do not guess a target when multiple referenced options prevent one "
                "deterministic choice. Fail closed and do not generate multiple "
                "prefer_option operations."
            ),
            "provider_delta_preference_target_unchanged": (
                "The user explicitly changed preference. Do not continue pointing to the "
                "current preferred option; use the other visible option explicitly chosen "
                "this turn. Do not guess or create an option. If no legal visible target "
                "can be determined, fail closed."
            ),
            "provider_delta_supersedes_forbidden": (
                "For the named operation, set supersedes_event_id to null, retain its "
                "target_id, preserve the user preference meaning, and do not add a "
                "separate supersede operation."
            ),
            "provider_delta_supersedes_required": (
                "Use only a visible effective event with the operation-compatible type "
                "for supersedes_event_id. Do not invent an event ID; if none exists, "
                "regenerate a legal delta that does not depend on this operation."
            ),
            "provider_delta_supersedes_target_incompatible": (
                "Replace supersedes_event_id with a visible effective event of the "
                "required type, or regenerate a legal delta that does not depend on "
                "the incompatible operation."
            ),
            "provider_delta_supersedes_target_not_visible": (
                "Use only a visible event ID. Do not invent an event ID or cite a "
                "previously unseen event."
            ),
            "provider_delta_supersedes_target_not_effective": (
                "Use a visible effective event rather than a rejected, superseded, or "
                "historical event."
            ),
            "provider_formalization_request_delta_missing": (
                "Include request_formalization with actor_claim=user_explicit, the "
                "current user message ID in source_message_ids, and "
                "supersedes_event_id=null. Do not create a PlanVersion or claim "
                "execution."
            ),
            "provider_formalization_proposal_missing": (
                "Include a complete FormalizationProposal with proposal_id, "
                "target=plan_revision, expected workspace_version, summary, changes, "
                "source_message_ids, risk_summary, requires_confirmation=true, and "
                "status=proposed. Each change needs change_type, subject_key, summary, "
                "and source_event_ids drawn only from visible pre-turn events."
            ),
            "provider_formalization_workspace_version_mismatch": (
                "Use expected_workspace_version_after_this_turn for the proposal "
                "workspace_version."
            ),
            "provider_formalization_source_message_invalid": (
                "Use visible source message IDs and include the current user message "
                "ID in the FormalizationProposal."
            ),
            "provider_formalization_source_event_invalid": (
                "Use only visible pre-turn event IDs in every proposal change; never "
                "cite the request_formalization event from this unpersisted turn."
            ),
        }
        return requirements.get(
            reason,
            "Correct the stated contract failure using only IDs and facts visible in "
            "the supplied context.",
        )

    @classmethod
    def _validate_delta_operation_contract(
        cls,
        *,
        context: DiscussionContextAssembly,
        delta: DiscussionDelta,
    ) -> str | None:
        explicit_operations = {
            DiscussionDeltaOperationType.PREFER_OPTION,
            DiscussionDeltaOperationType.REJECT_OPTION,
            DiscussionDeltaOperationType.RECORD_USER_CORRECTION,
            DiscussionDeltaOperationType.CONFIRM_DECISION,
            DiscussionDeltaOperationType.REQUEST_FORMALIZATION,
            DiscussionDeltaOperationType.CANCEL_FORMALIZATION,
        }
        event_by_id, effective_event_ids = cls._visible_event_admission_catalog(context)
        active_option_ids = (
            set(context.active_workspace.workspace.active_option_ids)
            if context.active_workspace is not None
            else set()
        )
        for operation in delta.operations:
            if (
                operation.op in explicit_operations
                and operation.actor_claim != DiscussionActorClaim.USER_EXPLICIT
            ):
                return "provider_delta_operation_actor_not_authorized"
            reason = validate_discussion_operation_admission(
                operation=operation,
                event_by_id=event_by_id,
                effective_event_ids=effective_event_ids,
                active_option_ids=active_option_ids,
            )
            if reason is not None:
                return cls._provider_admission_reason(reason)
        return None

    @staticmethod
    def _provider_admission_reason(reason: str) -> str:
        return {
            "discussion_delta_option_target_required": "provider_delta_option_target_required",
            "discussion_delta_option_target_not_new": "provider_delta_option_target_not_new",
            "discussion_delta_option_target_not_active": "provider_delta_option_target_not_active",
            "discussion_delta_prefer_active_option_supersedes_forbidden": (
                "provider_delta_supersedes_forbidden"
            ),
            "discussion_delta_rejected_option_actor_not_user_explicit": (
                "provider_delta_operation_actor_not_authorized"
            ),
            "discussion_delta_rejected_option_target_not_found": (
                "provider_delta_rejected_option_target_not_found"
            ),
            "discussion_delta_rejected_option_supersedes_required": (
                "provider_delta_rejected_option_supersedes_required"
            ),
            "discussion_delta_rejected_option_supersedes_type_invalid": (
                "provider_delta_rejected_option_supersedes_target_incompatible"
            ),
            "discussion_delta_rejected_option_target_mismatch": (
                "provider_delta_rejected_option_target_mismatch"
            ),
            "discussion_delta_target_id_forbidden": "provider_delta_target_id_forbidden",
            "discussion_delta_supersedes_required": "provider_delta_supersedes_required",
            "discussion_delta_supersedes_forbidden": "provider_delta_supersedes_forbidden",
            "discussion_delta_supersedes_target_not_found": (
                "provider_delta_supersedes_target_not_visible"
            ),
            "discussion_delta_supersedes_target_not_effective": (
                "provider_delta_supersedes_target_not_effective"
            ),
            "discussion_delta_supersedes_type_invalid": (
                "provider_delta_supersedes_target_incompatible"
            ),
        }.get(reason, "provider_delta_operation_invalid")

    @staticmethod
    def _visible_event_admission_catalog(
        context: DiscussionContextAssembly,
    ) -> tuple[dict[UUID, DiscussionEvent], set[UUID]]:
        event_by_id: dict[UUID, DiscussionEvent] = {}
        effective_event_ids: set[UUID] = set()
        if context.active_workspace is not None:
            for event in context.active_workspace.active_events:
                event_by_id[event.id] = event
                effective_event_ids.add(event.id)
        for item in context.relevant_events:
            event_by_id[item.event.id] = item.event
            if item.resolved_status in {
                DiscussionEventStatus.ACTIVE,
                DiscussionEventStatus.CONFIRMED,
            }:
                effective_event_ids.add(item.event.id)
        return event_by_id, effective_event_ids

    @classmethod
    def _validate_delta_requirement(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
        delta: DiscussionDelta,
    ) -> str | None:
        explicit_preference_selection = cls._has_explicit_preference_selection(
            context.current_user_message.content
        )
        prefer_operations = []
        if explicit_preference_selection:
            prefer_operations = [
                operation
                for operation in delta.operations
                if operation.op == DiscussionDeltaOperationType.PREFER_OPTION
            ]
            if len(prefer_operations) == 0:
                return "provider_delta_preference_operation_missing"
            if len(prefer_operations) != 1:
                return "provider_delta_preference_operation_ambiguous"

        state_change_mode = interpretation.conversation_mode in {
            ConversationMode.CONSTRAINT_UPDATE,
            ConversationMode.PREFERENCE_UPDATE,
            ConversationMode.DECISION_CONFIRMATION,
            ConversationMode.FORMALIZATION_REQUEST,
        }
        explicit_state_change = cls._has_explicit_state_change(
            context.current_user_message.content,
            explicit_preference_selection=explicit_preference_selection,
        )
        requires_delta = state_change_mode or explicit_state_change
        if requires_delta and not delta.operations:
            return "provider_delta_required"
        if requires_delta and any(
            operation.actor_claim != DiscussionActorClaim.USER_EXPLICIT
            for operation in delta.operations
        ):
            return "provider_delta_explicit_source_required"
        if explicit_preference_selection:
            prefer_operation = prefer_operations[0]
            if (
                prefer_operation.actor_claim != DiscussionActorClaim.USER_EXPLICIT
                or context.current_user_message.id
                not in prefer_operation.source_message_ids
            ):
                return "provider_delta_preference_operation_missing"
            referenced_option_ids = tuple(interpretation.referenced_option_ids)
            if len(referenced_option_ids) > 1:
                return "provider_delta_preference_target_ambiguous"
            if (
                context.active_workspace is not None
                and context.active_workspace.workspace.preferred_option_id is not None
                and cls._has_preference_reversal(context.current_user_message.content)
                and prefer_operation.target_id
                == context.active_workspace.workspace.preferred_option_id
            ):
                return "provider_delta_preference_target_unchanged"
            if (
                len(referenced_option_ids) == 1
                and prefer_operation.target_id != referenced_option_ids[0]
            ):
                return "provider_delta_preference_target_mismatch"
        if cls._formalization_proposal_required(
            context=context, interpretation=interpretation
        ) and not any(
            operation.op == DiscussionDeltaOperationType.REQUEST_FORMALIZATION
            for operation in delta.operations
        ):
            return "provider_formalization_request_delta_missing"
        return None

    @classmethod
    def _has_explicit_state_change(
        cls,
        content: str,
        *,
        explicit_preference_selection: bool | None = None,
    ) -> bool:
        normalized = content.lower()
        direct_markers = (
            "讨论主题",
            "主题是",
            "新增约束",
            "约束",
            "必须",
            "不要",
            "不允许",
            "拒绝",
            "不选",
            "纠正",
            "确认",
        )
        if any(marker in normalized for marker in direct_markers):
            return True
        state_actions = ("新增", "添加", "加入", "提出", "设为")
        state_entities = ("方案", "选项", "组合")
        if any(action in normalized for action in state_actions) and any(
            entity in normalized for entity in state_entities
        ):
            return True
        if explicit_preference_selection is None:
            explicit_preference_selection = cls._has_explicit_preference_selection(
                content
            )
        return explicit_preference_selection

    @classmethod
    def _has_explicit_preference_selection(cls, content: str) -> bool:
        """Recognize one affirmative first-person selection at clause scope."""

        for sentence in cls._preference_sentences(content):
            clauses = [
                clause.strip()
                for clause in re.split(r"[，,、]+", sentence)
                if clause.strip()
            ]
            conditional_scope = False
            for index, clause in enumerate(clauses):
                conditional_scope = conditional_scope or cls._opens_conditional_scope(
                    clause
                )
                selection_clause = clause
                if index > 0 and "我" not in clause and "我" in clauses[index - 1]:
                    selection_clause = clauses[index - 1] + clause
                if conditional_scope:
                    continue
                if cls._is_non_selection_clause(selection_clause):
                    continue
                if not cls._is_affirmative_preference_clause(selection_clause):
                    continue
                if (
                    index + 1 < len(clauses)
                    and cls._is_selection_question_continuation(clauses[index + 1])
                ):
                    continue
                return True
        return False

    @staticmethod
    def _opens_conditional_scope(clause: str) -> bool:
        compact = re.sub(r"\s+", "", clause)
        return (
            any(
                marker in compact
                for marker in (
                    "如果",
                    "假如",
                    "假设",
                    "只要",
                    "除非",
                    "条件满足",
                )
            )
            or compact.startswith("若")
            or re.search(r"在.+?(?:的)?情况下", compact) is not None
            or re.search(r"当.+?时", compact) is not None
        )

    @staticmethod
    def _preference_sentences(content: str) -> tuple[str, ...]:
        return tuple(
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？?!；;])|\n+", content.lower())
            if sentence.strip()
        )

    @staticmethod
    def _is_affirmative_preference_clause(clause: str) -> bool:
        compact = re.sub(r"\s+", "", clause)
        return any(
            re.search(pattern, compact)
            for pattern in (
                r"我(?:改变主意)?(?:当前|暂时|最终|重新)?选择(?:方案|选项|组合)?[^，。！？?!；;\s]+",
                r"我(?:改选|改回)(?:方案|选项|组合)?[^，。！？?!；;\s]+",
                r"我(?:更倾向|优先(?:选|选择)|更偏好|偏好|比较喜欢|确认选择)(?:方案|选项|组合)?[^，。！？?!；;\s]+",
            )
        )

    @staticmethod
    def _is_non_selection_clause(clause: str) -> bool:
        compact = re.sub(r"\s+", "", clause)
        return any(
            marker in compact
            for marker in (
                "如果",
                "假如",
                "假设",
                "是否",
                "吗",
                "呢",
                "会怎样",
                "会有什么",
                "有什么风险",
                "还是",
                "哪个更好",
                "更好",
                "比较",
                "分析",
                "不要",
                "不再",
                "不选择",
                "拒绝",
                "尚未决定",
                "还没有决定",
            )
        ) or "?" in clause or "？" in clause

    @staticmethod
    def _is_selection_question_continuation(clause: str) -> bool:
        compact = re.sub(r"\s+", "", clause)
        return any(
            marker in compact
            for marker in (
                "还是",
                "哪个更好",
                "更好",
                "吗",
                "呢",
                "如何",
                "怎样",
                "会怎样",
                "会有什么",
                "有什么风险",
                "是否",
            )
        ) or "?" in clause or "？" in clause

    @classmethod
    def _has_preference_reversal(cls, content: str) -> bool:
        return any(
            cls._has_explicit_preference_selection(sentence)
            and any(
                marker in sentence
                for marker in (
                    "改变主意",
                    "改选",
                    "重新选择",
                    "重新选",
                    "改回",
                    "最终纠正当前选择",
                )
            )
            for sentence in cls._preference_sentences(content)
        )

    @staticmethod
    def _formalization_proposal_required(
        *, context: DiscussionContextAssembly, interpretation: TurnInterpretation
    ) -> bool:
        return (
            interpretation.conversation_mode == ConversationMode.FORMALIZATION_REQUEST
            and interpretation.formal_action_requested
            and not interpretation.hypothetical_action
            and context.active_workspace is not None
            and context.active_workspace.workspace.version_no >= 1
        )

    @classmethod
    def _expected_workspace_version(
        cls,
        *,
        context: DiscussionContextAssembly,
        interpretation: TurnInterpretation,
    ) -> int | None:
        if not cls._formalization_proposal_required(
            context=context, interpretation=interpretation
        ):
            return None
        return context.active_workspace.workspace.version_no + 1

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
        active_option_ids = (
            set(context.active_workspace.workspace.active_option_ids)
            if context.active_workspace is not None
            else set()
        )
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
                if (
                    operation.op == DiscussionDeltaOperationType.PREFER_OPTION
                    and operation.target_id not in active_option_ids
                    and context.current_user_message.id not in source_ids
                ):
                    return "provider_delta_rejected_option_source_invalid"
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
            if cls._formalization_proposal_required(
                context=context, interpretation=interpretation
            ):
                return "provider_formalization_proposal_missing"
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
        expected_workspace_version = cls._expected_workspace_version(
            context=context, interpretation=interpretation
        )
        if proposal.workspace_version != expected_workspace_version:
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
    def _provider_source_detail(receipt_id: str | None, *, repaired: bool) -> str:
        receipt = receipt_id.strip()[:120] if isinstance(receipt_id, str) else ""
        attempt = "repair" if repaired else "direct"
        return (
            f"p26_f1_provider_response;attempt={attempt};receipt={receipt or 'missing'}"
        )[:300]

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
            source_detail=(
                "p26_f1_rule_fallback;attempt="
                f"{'repair' if reason.startswith('provider_repair_failed:') else 'direct'};"
                f"reason={reason}"
            )[:300],
        )
