"""Real P25-F Outcome support over the committed P25-B/D/E chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.external_executors.project_director_bounded_rework_executor import (
    ProjectDirectorBoundedReworkExecutorProtocol,
    ProjectDirectorBoundedReworkExecutorRequest,
    ProjectDirectorBoundedReworkExecutorResult,
)
from app.services.project_director_bounded_rework_invocation_outcome_service import (
    ProjectDirectorBoundedReworkInvocationOutcomeService,
)
from tests.p25_claim_real_chain_test_support import (
    FreshP25ClaimServices,
    RealP25AttemptZeroClaimContext,
    build_fresh_claim_services,
    build_real_p25_attempt_zero_claim_context,
)


@dataclass(slots=True)
class RecordingBoundedReworkExecutor(ProjectDirectorBoundedReworkExecutorProtocol):
    session: object
    call_count: int = 0
    requests: list[ProjectDirectorBoundedReworkExecutorRequest] = field(
        default_factory=list
    )
    session_states_at_call: list[bool] = field(default_factory=list)
    declared_changed_paths: tuple[str, ...] = ("src/example.py",)

    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult:
        assert self.session.in_transaction() is False
        assert request.executor_adapter_kind == "bounded_sandbox_rework_executor.v1"
        assert request.allowed_scope_paths == ("src/example.py",)
        assert len(request.blocking_findings) == 1
        assert request.required_corrections
        assert request.rework_attempt_index == 0
        assert request.rework_attempt_limit == 3
        assert request.product_runtime_git_write_allowed is False
        assert request.main_project_write_allowed is False
        self.call_count += 1
        self.requests.append(request)
        self.session_states_at_call.append(self.session.in_transaction())
        workspace_file = Path(request.workspace_path) / "src/example.py"
        workspace_file.write_text("value = 'candidate'\n# bounded rework attempt 0\n")
        return ProjectDirectorBoundedReworkExecutorResult(
            result_status="returned",
            declared_changed_paths=self.declared_changed_paths,
            safe_summary="Applied the bounded correction to src/example.py.",
            git_add=False,
            git_commit=False,
            git_push=False,
            branch_create=False,
            branch_delete=False,
            checkout=False,
            switch=False,
            reset=False,
            stash=False,
            rebase=False,
            tag=False,
            pull_request=False,
            merge=False,
            ci_trigger=False,
            main_project_write=False,
            workspace_escape=False,
        )


@dataclass(slots=True)
class RaisingBoundedReworkExecutor(ProjectDirectorBoundedReworkExecutorProtocol):
    session: object
    call_count: int = 0
    session_states_at_call: list[bool] = field(default_factory=list)

    def execute_bounded_rework(
        self,
        request: ProjectDirectorBoundedReworkExecutorRequest,
    ) -> ProjectDirectorBoundedReworkExecutorResult:
        assert self.session.in_transaction() is False
        self.call_count += 1
        self.session_states_at_call.append(self.session.in_transaction())
        raise RuntimeError("bounded test failure api_key=not-persisted")


@dataclass(slots=True)
class RealP25AttemptZeroOutcomeContext:
    claim_context: RealP25AttemptZeroClaimContext
    outcome_service: ProjectDirectorBoundedReworkInvocationOutcomeService
    executor: ProjectDirectorBoundedReworkExecutorProtocol

    @property
    def session(self):
        return self.claim_context.session

    @property
    def session_id(self):
        return self.claim_context.session_id

    @property
    def task_id(self):
        return self.claim_context.task_id

    @property
    def environment(self):
        return self.claim_context.environment

    def close(self) -> None:
        self.claim_context.close()


@dataclass(slots=True)
class FreshP25OutcomeServices:
    claim_services: FreshP25ClaimServices
    outcome_service: ProjectDirectorBoundedReworkInvocationOutcomeService

    @property
    def session(self):
        return self.claim_services.session

    def close(self) -> None:
        self.claim_services.close()


def build_real_p25_attempt_zero_outcome_context(
    tmp_path,
    *,
    executor: ProjectDirectorBoundedReworkExecutorProtocol | None = None,
) -> RealP25AttemptZeroOutcomeContext:
    """Persist package and reservation only; P25-F creates Claim and Outcome."""

    claim_context = build_real_p25_attempt_zero_claim_context(tmp_path)
    selected_executor = executor or RecordingBoundedReworkExecutor(
        session=claim_context.session
    )
    return RealP25AttemptZeroOutcomeContext(
        claim_context=claim_context,
        outcome_service=ProjectDirectorBoundedReworkInvocationOutcomeService(
            message_repository=claim_context.package_context.msg_repo,
            claim_service=claim_context.claim_service,
            bounded_rework_executor=selected_executor,
        ),
        executor=selected_executor,
    )


def build_fresh_outcome_services(
    context: RealP25AttemptZeroOutcomeContext,
) -> FreshP25OutcomeServices:
    """Rebuild the P25-B/D/E/F graph while preserving executor call evidence."""

    claim_services = build_fresh_claim_services(context.claim_context)
    if hasattr(context.executor, "session"):
        context.executor.session = claim_services.session
    return FreshP25OutcomeServices(
        claim_services=claim_services,
        outcome_service=ProjectDirectorBoundedReworkInvocationOutcomeService(
            message_repository=claim_services.reservation_services.message_repository,
            claim_service=claim_services.claim_service,
            bounded_rework_executor=context.executor,
        ),
    )
