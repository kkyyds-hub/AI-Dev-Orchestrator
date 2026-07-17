"""Real P25-H-B support composed from the committed P25-B through P25-H-A chain."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportRawResult,
    ReadonlyReviewerTransportRequest,
)
from app.services.project_director_bounded_rework_review_execution_service import (
    ProjectDirectorBoundedReworkReviewExecutionService,
)
from tests.p25_review_reentry_preflight_real_chain_test_support import (
    FreshP25ReviewPreflightServices,
    RealP25AttemptZeroReviewPreflightContext,
    build_fresh_review_preflight_services,
    build_real_p25_attempt_zero_review_preflight_context,
)


VALID_REVIEW_OUTPUT = """{
  \"review_status\": \"reviewed\",
  \"verdict\": \"no_blocking_findings\",
  \"risk_level\": \"low\",
  \"summary\": \"The bounded candidate satisfies the requested correction.\",
  \"findings\": [],
  \"recommended_next_step\": \"Continue to bounded convergence evaluation.\"
}"""


@dataclass(slots=True)
class RecordingReadonlyReviewerTransport:
    """Test-only transport that proves reviewer execution is outside a transaction."""

    session: object
    raw_output_text: str = VALID_REVIEW_OUTPUT
    execute_calls: int = 0
    requests: list[ReadonlyReviewerTransportRequest] = field(default_factory=list)
    session_states_at_call: list[bool] = field(default_factory=list)

    def execute(
        self,
        request: ReadonlyReviewerTransportRequest,
    ) -> ReadonlyReviewerTransportRawResult:
        in_transaction = self.session.in_transaction()
        self.session_states_at_call.append(in_transaction)
        assert in_transaction is False
        self.execute_calls += 1
        self.requests.append(request)
        return ReadonlyReviewerTransportRawResult(
            transport_status="completed",
            requested_reviewer_executor=request.requested_reviewer_executor,
            raw_output_text=self.raw_output_text,
            transport_invoked=True,
            execution_mode="fake_transport",
            real_reviewer_started=False,
            real_reviewer_executed=False,
            native_process_started=False,
            provider_called=False,
            codex_started=False,
            claude_code_started=False,
        )


@dataclass(slots=True)
class RecordingReadonlyReviewerResolverFactory:
    transport: RecordingReadonlyReviewerTransport
    factory_calls: int = 0
    workspace_paths: list[str] = field(default_factory=list)
    resolver_calls: int = 0
    requested_reviewer_executors: list[str] = field(default_factory=list)
    factory_exception: Exception | None = None

    def __call__(self, workspace_path: str):
        self.factory_calls += 1
        self.workspace_paths.append(workspace_path)
        if self.factory_exception is not None:
            raise self.factory_exception
        return self._resolve

    def _resolve(self, requested_reviewer_executor: str):
        self.resolver_calls += 1
        self.requested_reviewer_executors.append(requested_reviewer_executor)
        return self.transport


@dataclass(slots=True)
class RealP25AttemptZeroReviewExecutionContext:
    review_preflight_context: RealP25AttemptZeroReviewPreflightContext
    h_a_result: object
    review_execution_service: ProjectDirectorBoundedReworkReviewExecutionService
    resolver_factory: RecordingReadonlyReviewerResolverFactory
    transport: RecordingReadonlyReviewerTransport

    @property
    def session(self):
        return self.review_preflight_context.session

    @property
    def session_id(self):
        return self.review_preflight_context.session_id

    @property
    def task_id(self):
        return self.review_preflight_context.task_id

    @property
    def environment(self):
        return self.review_preflight_context.environment

    @property
    def message_repository(self):
        return self.review_preflight_context.message_repository

    def close(self) -> None:
        self.review_preflight_context.close()


@dataclass(slots=True)
class FreshP25ReviewExecutionServices:
    review_preflight_services: FreshP25ReviewPreflightServices
    review_execution_service: ProjectDirectorBoundedReworkReviewExecutionService

    @property
    def session(self):
        return self.review_preflight_services.session

    def close(self) -> None:
        self.review_preflight_services.close()


def build_real_p25_attempt_zero_review_execution_context(tmp_path):
    preflight_context = build_real_p25_attempt_zero_review_preflight_context(tmp_path)
    h_a_result = (
        preflight_context.review_preflight_service.prepare_review_reentry_preflight_and_claim(
            session_id=preflight_context.session_id,
            source_task_id=preflight_context.task_id,
            source_candidate_diff_message_id=preflight_context.candidate_diff_result.diff_message.id,
        )
    )
    assert h_a_result.status == "review_preflight_claimed", h_a_result.blocked_reasons
    transport = RecordingReadonlyReviewerTransport(session=preflight_context.session)
    resolver_factory = RecordingReadonlyReviewerResolverFactory(transport=transport)
    return RealP25AttemptZeroReviewExecutionContext(
        review_preflight_context=preflight_context,
        h_a_result=h_a_result,
        review_execution_service=ProjectDirectorBoundedReworkReviewExecutionService(
            message_repository=preflight_context.message_repository,
            preflight_service=preflight_context.review_preflight_service,
            transport_resolver_factory=resolver_factory,
        ),
        resolver_factory=resolver_factory,
        transport=transport,
    )


def build_fresh_review_execution_services(
    context: RealP25AttemptZeroReviewExecutionContext,
) -> FreshP25ReviewExecutionServices:
    review_preflight_services = build_fresh_review_preflight_services(
        context.review_preflight_context
    )
    context.transport.session = review_preflight_services.session
    return FreshP25ReviewExecutionServices(
        review_preflight_services=review_preflight_services,
        review_execution_service=ProjectDirectorBoundedReworkReviewExecutionService(
            message_repository=(
                review_preflight_services.candidate_services.outcome_services.claim_services
                .reservation_services.message_repository
            ),
            preflight_service=review_preflight_services.review_preflight_service,
            transport_resolver_factory=context.resolver_factory,
        ),
    )
