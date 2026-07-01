from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.model_policy import (
    ExecutorModelRoutingContract,
    ExecutorRouteMode,
    ExecutorRoutingStrategyHint,
    ExecutorRoutingTarget,
)
from app.domain.prompt_contract import (
    BuiltPromptEnvelope,
    PromptSection,
    PromptTemplateRef,
    ProviderReceiptSource,
)
from app.domain.task import Task


def _routing_contract(
    *,
    provider_key: str = "openai",
    model_name: str = "gpt-4.1-mini",
    api_family: str = "responses",
) -> ExecutorModelRoutingContract:
    return ExecutorModelRoutingContract(
        primary_mode=ExecutorRouteMode.PROVIDER,
        primary_target=ExecutorRoutingTarget(
            provider_key=provider_key,
            model_name=model_name,
            api_family=api_family,
        ),
        route_reason="测试 provider 路由",
        strategy_hint=ExecutorRoutingStrategyHint(
            strategy_code="test-provider-route",
            model_tier="balanced",
        ),
    )


def _prompt_envelope(prompt_text: str = "请总结当前任务。") -> BuiltPromptEnvelope:
    return BuiltPromptEnvelope(
        template_ref=PromptTemplateRef(
            prompt_key="test_prompt",
            version="v1",
        ),
        provider_key="openai",
        model_name="gpt-4.1-mini",
        sections=[
            PromptSection(
                key="body",
                title="正文",
                content=prompt_text,
            )
        ],
        prompt_text=prompt_text,
        prompt_char_count=len(prompt_text.encode("utf-8")),
    )


def test_is_enabled_requires_api_key() -> None:
    from app.services.openai_provider_executor_service_v2 import (
        OpenAIProviderExecutorService,
    )

    assert OpenAIProviderExecutorService(api_key=None).is_enabled is False
    assert OpenAIProviderExecutorService(api_key="").is_enabled is False
    assert OpenAIProviderExecutorService(api_key=" sk-test ").is_enabled is True


def test_generate_text_responses_api_success(monkeypatch) -> None:
    from app.services import openai_provider_executor_service_v2 as module

    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp-001",
                output_text="响应 API 已成功生成中文摘要。",
                usage=SimpleNamespace(
                    input_tokens=11,
                    output_tokens=7,
                    total_tokens=18,
                    input_tokens_details=SimpleNamespace(cached_tokens=3),
                ),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr(module, "OpenAI", FakeOpenAI)

    executor = module.OpenAIProviderExecutorService(api_key="sk-test")
    response = executor.generate_text(
        model_name="gpt-4.1-mini",
        prompt_text="请生成摘要。",
        request_id="req-001",
    )

    assert response.output_text == "响应 API 已成功生成中文摘要。"
    assert captured["model"] == "gpt-4.1-mini"
    assert captured["input"][0]["content"][0]["text"] == "请生成摘要。"
    assert response.provider_usage_receipt is not None
    assert response.provider_usage_receipt.receipt_id == "resp-001"
    assert response.provider_usage_receipt.prompt_tokens == 11
    assert response.provider_usage_receipt.completion_tokens == 7
    assert response.provider_usage_receipt.total_tokens == 18
    assert response.provider_usage_receipt.cache_read_tokens == 3
    assert response.provider_usage_receipt.cache_source == "provider_reported"
    assert response.provider_usage_receipt.pricing_source == "openai.responses.usage"


def test_generate_text_chat_completions_success(monkeypatch) -> None:
    from app.services import openai_provider_executor_service_v2 as module

    captured: dict[str, object] = {}

    class FakeChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="chat-001",
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Chat Completions 已成功生成。")
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=13,
                    completion_tokens=5,
                    total_tokens=18,
                ),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setattr(module, "OpenAI", FakeOpenAI)

    executor = module.OpenAIProviderExecutorService(
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
    )
    response = executor.generate_text(
        model_name="deepseek-chat",
        prompt_text="请生成摘要。",
        request_id="req-002",
        provider_key="deepseek",
    )

    assert response.output_text == "Chat Completions 已成功生成。"
    assert captured["model"] == "deepseek-chat"
    assert captured["messages"] == [{"role": "user", "content": "请生成摘要。"}]
    assert response.provider_usage_receipt is not None
    assert response.provider_usage_receipt.provider_key == "deepseek"
    assert response.provider_usage_receipt.prompt_tokens == 13
    assert response.provider_usage_receipt.completion_tokens == 5
    assert response.provider_usage_receipt.cache_source == "not_reported"
    assert response.provider_usage_receipt.pricing_source == "openai.chat_completions.usage"


def test_execute_uses_prompt_envelope_and_routing_target(monkeypatch) -> None:
    from app.services import openai_provider_executor_service_v2 as module

    captured: dict[str, object] = {}

    class FakeChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="chat-exec-001",
                choices=[SimpleNamespace(message=SimpleNamespace(content="执行完成。"))],
                usage=SimpleNamespace(prompt_tokens=9, completion_tokens=4, total_tokens=13),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setattr(module, "OpenAI", FakeOpenAI)

    executor = module.OpenAIProviderExecutorService(
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
    )
    prompt = _prompt_envelope("这是 BuiltPromptEnvelope 内部渲染好的 prompt。")
    response = executor.execute(
        task=Task(title="provider task", input_summary="payload 不应覆盖 prompt"),
        payload="payload 不应被传入 SDK",
        routing_contract=_routing_contract(
            provider_key="deepseek",
            model_name="deepseek-v4-pro",
            api_family="chat_completions",
        ),
        prompt_envelope=prompt,
    )

    assert captured["model"] == "deepseek-v4-pro"
    assert captured["messages"][0]["content"] == prompt.prompt_text
    assert response.provider_usage_receipt is not None
    assert response.provider_usage_receipt.provider_key == "deepseek"
    assert response.provider_usage_receipt.model_name == "deepseek-v4-pro"
    assert response.provider_usage_receipt.receipt_source is ProviderReceiptSource.REAL_PROVIDER


def test_sdk_errors_are_mapped_to_project_error(monkeypatch) -> None:
    from app.services import openai_provider_executor_service_v2 as module

    class FakeResponses:
        def create(self, **kwargs):
            raise module.APIConnectionError(request=SimpleNamespace(url="https://api.openai.com/v1/responses"))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr(module, "OpenAI", FakeOpenAI)

    executor = module.OpenAIProviderExecutorService(api_key="sk-test")
    with pytest.raises(module.OpenAIProviderExecutionError) as error:
        executor.generate_text(
            model_name="gpt-4.1-mini",
            prompt_text="请生成摘要。",
            request_id="req-003",
        )

    assert error.value.category == "network_error"
    assert error.value.api_family == "responses"
    assert len(error.value.message) <= 500


def test_compatible_gateway_falls_back_between_api_families(monkeypatch) -> None:
    from app.services import openai_provider_executor_service_v2 as module

    calls: list[str] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append("responses")
            return SimpleNamespace(
                id="fallback-resp-001",
                output_text="fallback 后响应成功。",
                usage=SimpleNamespace(input_tokens=6, output_tokens=4, total_tokens=10),
            )

    class FakeChatCompletions:
        def create(self, **kwargs):
            calls.append("chat_completions")
            raise module.OpenAIProviderExecutionError(
                category="endpoint_not_found",
                message="兼容网关不支持 Chat Completions。",
                status_code=404,
                api_family="chat_completions",
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setattr(module, "OpenAI", FakeOpenAI)

    executor = module.OpenAIProviderExecutorService(
        api_key="sk-test",
        base_url="https://compatible.example.com/v1",
    )
    response = executor.generate_text(
        model_name="compatible-model",
        prompt_text="请生成摘要。",
        request_id="req-004",
    )

    assert calls == ["chat_completions", "responses"]
    assert response.output_text == "fallback 后响应成功。"


def test_v1_import_path_exports_v2_default_service() -> None:
    from app.services.openai_provider_executor_service import OpenAIProviderExecutorService
    from app.services.openai_provider_executor_service_v2 import (
        OpenAIProviderExecutorService as OpenAIProviderExecutorServiceV2,
    )

    assert OpenAIProviderExecutorService is OpenAIProviderExecutorServiceV2


def test_provider_key_not_supported_keeps_project_error() -> None:
    from app.services.openai_provider_executor_service_v2 import (
        OpenAIProviderExecutionError,
        OpenAIProviderExecutorService,
    )

    executor = OpenAIProviderExecutorService(api_key="sk-test")
    with pytest.raises(OpenAIProviderExecutionError) as error:
        executor.execute(
            task=Task(title="provider task", input_summary="payload"),
            payload="payload",
            routing_contract=_routing_contract(provider_key="unsupported_vendor"),
            prompt_envelope=_prompt_envelope(),
        )

    assert error.value.category == "provider_not_supported"
