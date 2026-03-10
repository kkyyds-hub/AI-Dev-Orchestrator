"""FastAPI 应用入口。

如果你熟悉 Java / Spring Boot，可以这样理解：

- 这个文件类似“应用启动入口”
- `create_application()` 类似“创建并装配应用上下文”
- 最终暴露出去的 `app` 变量，会被 Uvicorn 当成启动对象
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.db import init_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期。

    当前阶段只做一件 Day 3 需要的事情：

    - 启动时初始化本地 SQLite 数据库和核心表结构
    """

    init_database()
    yield


def create_application() -> FastAPI:
    """创建 FastAPI 应用实例。

    这里先做 Day 1 到 Day 3 需要的最小装配：

    1. 创建应用对象
    2. 配置应用标题和版本
    3. 注册统一路由
    4. 启动时初始化 SQLite 数据库

    以后如果要加中间件、异常处理、生命周期钩子，
    也会优先放在这个函数里继续扩展。
    """

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        description=(
            "AI 开发调度系统后端最小骨架。"
            "当前阶段已具备基础健康检查接口和 SQLite 最小持久化能力。"
        ),
    )

    # 统一注册 API 路由。
    # 这样做的好处是：后续新增接口时，不需要每次都回到 main.py 修改很多地方。
    application.include_router(api_router)

    return application


# 这个变量名必须叫 app，或者在启动命令里显式指定别的变量名。
# Uvicorn 启动时会读取 `app.main:app`，意思就是：
# - 导入 app/main.py
# - 找到其中名为 app 的应用对象
app = create_application()
