"""Unified API router registration."""

from fastapi import APIRouter

from app.api.routes.agent_threads import router as agent_threads_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.console import router as console_router
from app.api.routes.deliverables import router as deliverables_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.planning import router as planning_router
from app.api.routes.provider_settings import router as provider_settings_router
from app.api.routes.projects import router as projects_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.roles import router as roles_router
from app.api.routes.runs import router as runs_router
from app.api.routes.skills import router as skills_router
from app.api.routes.strategy import router as strategy_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.team_control_center import router as team_control_center_router
from app.api.routes.workers import router as workers_router


api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(events_router)
api_router.include_router(console_router)
api_router.include_router(agent_threads_router)
api_router.include_router(approvals_router)
api_router.include_router(deliverables_router)
api_router.include_router(tasks_router)
api_router.include_router(provider_settings_router)
api_router.include_router(projects_router)
api_router.include_router(repositories_router)
api_router.include_router(roles_router)
api_router.include_router(skills_router)
api_router.include_router(strategy_router)
api_router.include_router(planning_router)
api_router.include_router(runs_router)
api_router.include_router(team_control_center_router)
api_router.include_router(workers_router)
