"""执行器和工作者服务共享的模型路由合同原语。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from app.domain._base import DomainModel


class ExecutorRouteMode(StrEnum):
    """合并任务前缀和路由策略后选择的执行模式。"""

    SHELL = "shell"
    SIMULATE = "simulate"
    PROVIDER = "provider"


class ExecutorImplicitFallbackMode(StrEnum):
    """当提供者执行不可用时的回退模式。"""

    SIMULATE = "simulate"
    SHELL = "shell"


class ExecutorRoutingTarget(DomainModel):
    """路由策略选择的具体提供者目标。"""

    provider_key: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    api_family: str = Field(min_length=1, max_length=50)

    @field_validator("provider_key", "model_name", "api_family")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """标准化提供者目标字符串字段。"""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Routing target fields cannot be blank.")
        return normalized_value


class ExecutorRoutingStrategyHint(DomainModel):
    """通过执行规划传递的可解释策略快照。"""

    strategy_code: str = Field(min_length=1, max_length=100)
    model_tier: str | None = Field(default=None, max_length=40)
    selected_skill_codes: list[str] = Field(default_factory=list, max_length=12)
    selected_skill_names: list[str] = Field(default_factory=list, max_length=12)
    owner_role_code: str | None = Field(default=None, max_length=40)
    role_model_policy_source: str | None = Field(default=None, max_length=40)
    role_model_policy_desired_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_adjusted_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_final_tier: str | None = Field(default=None, max_length=40)
    role_model_policy_stage_override_applied: bool = False

    @field_validator("selected_skill_codes", "selected_skill_names")
    @classmethod
    def normalize_string_list(cls, value: list[str]) -> list[str]:
        """修剪和去重有序字符串列表。"""

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue
            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)
        return normalized_items


class ExecutorModelRoutingContract(DomainModel):
    """执行器消费的可序列化提供者路由合同。"""

    version: str = Field(default="day05.step1", min_length=1, max_length=40)
    primary_mode: ExecutorRouteMode = ExecutorRouteMode.PROVIDER
    primary_target: ExecutorRoutingTarget | None = None
    implicit_fallback_mode: ExecutorImplicitFallbackMode = (
        ExecutorImplicitFallbackMode.SIMULATE
    )
    route_reason: str = Field(min_length=1, max_length=2_000)
    strategy_hint: ExecutorRoutingStrategyHint

