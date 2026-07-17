"""Real P25-E Claim support composed from committed P25-B and P25-D paths."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.project_director_bounded_rework_invocation_claim_service import (
    ProjectDirectorBoundedReworkInvocationClaimService,
)
from tests.p25_package_real_chain_test_support import (
    RealP25AttemptZeroPackageContext,
    build_real_p25_attempt_zero_package_context,
)
from tests.p25_reservation_real_chain_test_support import (
    FreshP25ReservationServices,
    build_fresh_reservation_services,
    build_reservation_service_from_context,
)


@dataclass(slots=True)
class RealP25AttemptZeroClaimContext:
    package_context: RealP25AttemptZeroPackageContext
    package_result: object
    reservation_result: object
    claim_service: ProjectDirectorBoundedReworkInvocationClaimService

    @property
    def session(self):
        return self.package_context.session

    @property
    def session_id(self):
        return self.package_context.session_id

    @property
    def project_id(self):
        return self.package_context.project_id

    @property
    def task_id(self):
        return self.package_context.task_id

    @property
    def environment(self):
        return self.package_context.environment

    def close(self) -> None:
        self.package_context.close()


@dataclass(slots=True)
class FreshP25ClaimServices:
    reservation_services: FreshP25ReservationServices
    claim_service: ProjectDirectorBoundedReworkInvocationClaimService

    @property
    def session(self):
        return self.reservation_services.session

    def close(self) -> None:
        self.reservation_services.close()


def build_real_p25_attempt_zero_claim_context(tmp_path) -> RealP25AttemptZeroClaimContext:
    """Create P25-B and P25-D through their public APIs, then compose P25-E."""

    package_context = build_real_p25_attempt_zero_package_context(tmp_path)
    package_result = (
        package_context.package_service.prepare_bounded_rework_instruction_package(
            session_id=package_context.session_id,
            source_task_id=package_context.task_id,
            source_p23_dispatch_consumption_message_id=(
                package_context.source_p23_consumption_message_id
            ),
        )
    )
    assert package_result.status == "package_prepared", package_result.blocked_reasons
    assert package_result.message is not None

    reservation_service = build_reservation_service_from_context(package_context)
    reservation_result = reservation_service.reserve_bounded_rework_attempt(
        session_id=package_context.session_id,
        source_task_id=package_context.task_id,
        source_package_message_id=package_result.message.id,
    )
    assert reservation_result.status == "reservation_reserved", reservation_result.blocked_reasons
    assert reservation_result.message is not None
    assert package_context.session.in_transaction() is False

    return RealP25AttemptZeroClaimContext(
        package_context=package_context,
        package_result=package_result,
        reservation_result=reservation_result,
        claim_service=ProjectDirectorBoundedReworkInvocationClaimService(
            message_repository=package_context.msg_repo,
            attempt_reservation_service=reservation_service,
        ),
    )


def build_fresh_claim_services(
    context: RealP25AttemptZeroClaimContext,
) -> FreshP25ClaimServices:
    """Rebuild the complete P25-B/D/E dependency graph with a new Session."""

    reservation_services = build_fresh_reservation_services(context.package_context)
    return FreshP25ClaimServices(
        reservation_services=reservation_services,
        claim_service=ProjectDirectorBoundedReworkInvocationClaimService(
            message_repository=reservation_services.message_repository,
            attempt_reservation_service=reservation_services.reservation_service,
        ),
    )
