"""健康检查接口。

这是 Day 1 最重要的最小接口：

- 用来验证 FastAPI 服务是否成功启动
- 用来验证路由注册是否正常
- 用来验证接口文档是否能正确展示
"""

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """健康检查响应模型。

    可以把它理解成 Java 后端里的 Response DTO。
    FastAPI 会根据这个模型：

    - 自动校验返回结构
    - 自动生成 OpenAPI 文档
    - 自动在 Swagger UI 中展示字段说明
    """

    status: str
    service: str


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="健康检查")
def health_check() -> HealthResponse:
    """返回最小健康检查结果。

    这里先返回固定值即可。
    等后面接入数据库、队列或其他依赖后，
    再决定是否扩展为更完整的系统状态检查。
    """

    return HealthResponse(
        status="ok",
        service="orchestrator-backend",
    )

