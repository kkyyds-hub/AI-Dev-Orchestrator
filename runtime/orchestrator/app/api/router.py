"""统一路由入口。

这个文件的作用是集中管理所有 API 路由，
避免把所有接口都直接堆到 `app/main.py` 里。
"""

from fastapi import APIRouter

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.planning import router as planning_router
from app.api.routes.runs import router as runs_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.workers import router as workers_router

# 统一 API 路由对象。
# 后续如果有 task、run、budget 等接口，也都在这里继续注册。
api_router = APIRouter()

# 注册健康检查路由。
api_router.include_router(health_router)

# 注册实时事件流路由。
# Day 13 开始提供本地 SSE 状态流。
api_router.include_router(events_router)

# 注册任务相关路由。
# Day 4 先从任务创建接口开始，后续列表、详情等也会继续接在这里。
api_router.include_router(tasks_router)

# 注册规划相关路由。
# Day 16 开始提供最小 brief -> draft -> apply 规划链路。
api_router.include_router(planning_router)

# 注册运行相关路由。
# Day 12 开始提供最小日志读取能力。
api_router.include_router(runs_router)

# 注册 Worker 相关路由。
# Day 6 先提供单轮触发入口，后续再继续接入真正执行器。
api_router.include_router(workers_router)
