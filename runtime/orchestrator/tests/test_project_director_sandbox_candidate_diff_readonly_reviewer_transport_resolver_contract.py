"""Contract tests for concrete readonly reviewer transport resolver."""

from __future__ import annotations

import ast
import inspect
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.external_executors.readonly_reviewer_codex_app_server_transport import (
    CodexAppServerReadonlyReviewerTransport,
)
from app.external_executors.readonly_reviewer_native_transport import (
    NativeReadonlyReviewerCaptureTransport,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportProtocol,
)
from app.external_executors.readonly_reviewer_transport_resolver import (
    ReadonlyReviewerTransportResolver,
)


# ── Spy factories ───────────────────────────────────────────────────


class SpyCodexTransport:
    """Sentinel that satisfies identity check."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class SpyNativeTransport:
    """Sentinel that satisfies identity check."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class SpyPopenFactory:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return MagicMock()


def _make_resolver(
    *,
    workspace_path: str = "/tmp/test-workspace",
    timeout_seconds: float = 180.0,
    max_output_bytes: int = 256 * 1024,
    process_supervisor: Any = None,
    popen_factory: Any = None,
    terminate_wait_seconds: float = 0.2,
    claude_code_child_environment: Mapping[str, str] | None = None,
) -> ReadonlyReviewerTransportResolver:
    return ReadonlyReviewerTransportResolver(
        workspace_path=workspace_path,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        process_supervisor=process_supervisor or MagicMock(),
        popen_factory=popen_factory or MagicMock(),
        terminate_wait_seconds=terminate_wait_seconds,
        claude_code_child_environment=claude_code_child_environment,
    )


# ══════════════════════════════════════════════════════════════════════
# A. Constructor does not create transport
# ══════════════════════════════════════════════════════════════════════


class TestConstructorNoTransport:
    def test_construct_does_not_create_transport(self, monkeypatch) -> None:
        codex_spy = MagicMock()
        native_spy = MagicMock()
        popen_spy = SpyPopenFactory()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        _make_resolver(popen_factory=popen_spy)
        assert codex_spy.call_count == 0
        assert native_spy.call_count == 0
        assert popen_spy.calls == []


# ══════════════════════════════════════════════════════════════════════
# B. codex exact mapping
# ══════════════════════════════════════════════════════════════════════


class TestCodexMapping:
    def test_codex_creates_codex_transport(self, monkeypatch) -> None:
        sentinel = SpyCodexTransport()
        codex_spy = MagicMock(return_value=sentinel)
        native_spy = MagicMock()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver()
        result = resolver("codex")
        assert result is sentinel
        assert codex_spy.call_count == 1
        assert native_spy.call_count == 0

    def test_codex_receives_exact_parameters(self, monkeypatch) -> None:
        codex_spy = MagicMock(return_value=SpyCodexTransport())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        supervisor = MagicMock()
        popen = MagicMock()
        env = {"KEY": "val"}
        resolver = _make_resolver(
            workspace_path="/ws",
            timeout_seconds=99.0,
            max_output_bytes=12345,
            process_supervisor=supervisor,
            popen_factory=popen,
            terminate_wait_seconds=0.5,
            claude_code_child_environment=env,
        )
        resolver("codex")
        kwargs = codex_spy.call_args[1]
        assert kwargs["workspace_path"] == "/ws"
        assert kwargs["timeout_seconds"] == 99.0
        assert kwargs["max_output_bytes"] == 12345
        assert kwargs["process_supervisor"] is supervisor
        assert kwargs["popen_factory"] is popen
        assert kwargs["terminate_wait_seconds"] == 0.5
        assert "claude_code_child_environment" not in kwargs

    def test_codex_no_claude_env_leak(self, monkeypatch) -> None:
        codex_spy = MagicMock(return_value=SpyCodexTransport())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        resolver = _make_resolver(claude_code_child_environment={"A": "B"})
        resolver("codex")
        kwargs = codex_spy.call_args[1]
        assert "claude_code_child_environment" not in kwargs


# ══════════════════════════════════════════════════════════════════════
# C. claude-code exact mapping
# ══════════════════════════════════════════════════════════════════════


class TestClaudeCodeMapping:
    def test_claude_code_creates_native_transport(self, monkeypatch) -> None:
        sentinel = SpyNativeTransport()
        codex_spy = MagicMock()
        native_spy = MagicMock(return_value=sentinel)
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver()
        result = resolver("claude-code")
        assert result is sentinel
        assert native_spy.call_count == 1
        assert codex_spy.call_count == 0

    def test_claude_code_receives_exact_parameters(self, monkeypatch) -> None:
        native_spy = MagicMock(return_value=SpyNativeTransport())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        supervisor = MagicMock()
        popen = MagicMock()
        env = {"ANTHROPIC_BASE_URL": "https://example.com"}
        resolver = _make_resolver(
            workspace_path="/ws2",
            timeout_seconds=77.0,
            max_output_bytes=99999,
            process_supervisor=supervisor,
            popen_factory=popen,
            terminate_wait_seconds=0.3,
            claude_code_child_environment=env,
        )
        resolver("claude-code")
        kwargs = native_spy.call_args[1]
        assert kwargs["workspace_path"] == "/ws2"
        assert kwargs["timeout_seconds"] == 77.0
        assert kwargs["max_output_bytes"] == 99999
        assert kwargs["process_supervisor"] is supervisor
        assert kwargs["popen_factory"] is popen
        assert kwargs["terminate_wait_seconds"] == 0.3
        assert kwargs["claude_code_child_environment"] is env

    def test_claude_code_none_env_passed_as_none(self, monkeypatch) -> None:
        native_spy = MagicMock(return_value=SpyNativeTransport())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver(claude_code_child_environment=None)
        resolver("claude-code")
        kwargs = native_spy.call_args[1]
        assert kwargs["claude_code_child_environment"] is None


# ══════════════════════════════════════════════════════════════════════
# D. Invalid executor
# ══════════════════════════════════════════════════════════════════════


class TestInvalidExecutor:
    @pytest.mark.parametrize(
        "value",
        ["", "claude", "deepseek", "mimo", "CODEX", "Claude-Code"],
    )
    def test_invalid_executor_raises(self, value, monkeypatch) -> None:
        codex_spy = MagicMock()
        native_spy = MagicMock()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver()
        with pytest.raises(ValueError, match=f"unsupported readonly reviewer executor: {value!r}"):
            resolver(value)
        assert codex_spy.call_count == 0
        assert native_spy.call_count == 0

    def test_none_executor_raises(self, monkeypatch) -> None:
        codex_spy = MagicMock()
        native_spy = MagicMock()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver()
        with pytest.raises(ValueError, match="unsupported readonly reviewer executor"):
            resolver(None)
        assert codex_spy.call_count == 0
        assert native_spy.call_count == 0


# ══════════════════════════════════════════════════════════════════════
# E. Concrete constructor failure no fallback
# ══════════════════════════════════════════════════════════════════════


class TestNoFallback:
    def test_codex_constructor_failure_propagates(self, monkeypatch) -> None:
        codex_spy = MagicMock(side_effect=RuntimeError("codex construction failed"))
        native_spy = MagicMock()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver()
        with pytest.raises(RuntimeError, match="codex construction failed"):
            resolver("codex")
        assert codex_spy.call_count == 1
        assert native_spy.call_count == 0

    def test_claude_code_constructor_failure_propagates(self, monkeypatch) -> None:
        codex_spy = MagicMock()
        native_spy = MagicMock(side_effect=RuntimeError("native construction failed"))
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            codex_spy,
        )
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            native_spy,
        )
        resolver = _make_resolver()
        with pytest.raises(RuntimeError, match="native construction failed"):
            resolver("claude-code")
        assert native_spy.call_count == 1
        assert codex_spy.call_count == 0


# ══════════════════════════════════════════════════════════════════════
# F. Resolver does not call popen_factory
# ══════════════════════════════════════════════════════════════════════


class TestNoPopenCall:
    def test_resolve_codex_does_not_call_popen(self, monkeypatch) -> None:
        popen_spy = SpyPopenFactory()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".CodexAppServerReadonlyReviewerTransport",
            lambda **kw: SpyCodexTransport(**kw),
        )
        resolver = _make_resolver(popen_factory=popen_spy)
        resolver("codex")
        assert popen_spy.calls == []

    def test_resolve_claude_code_does_not_call_popen(self, monkeypatch) -> None:
        popen_spy = SpyPopenFactory()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver"
            ".NativeReadonlyReviewerCaptureTransport",
            lambda **kw: SpyNativeTransport(**kw),
        )
        resolver = _make_resolver(popen_factory=popen_spy)
        resolver("claude-code")
        assert popen_spy.calls == []


# ══════════════════════════════════════════════════════════════════════
# G. Return objects satisfy transport contract
# ══════════════════════════════════════════════════════════════════════


class TestTransportContract:
    def test_codex_returns_codex_transport_instance(self) -> None:
        resolver = _make_resolver()
        result = resolver("codex")
        assert isinstance(result, CodexAppServerReadonlyReviewerTransport)
        assert isinstance(result, ReadonlyReviewerTransportProtocol)

    def test_claude_code_returns_native_transport_instance(self) -> None:
        resolver = _make_resolver()
        result = resolver("claude-code")
        assert isinstance(result, NativeReadonlyReviewerCaptureTransport)
        assert isinstance(result, ReadonlyReviewerTransportProtocol)


# ══════════════════════════════════════════════════════════════════════
# H. H-C2 Protocol structural compatibility
# ══════════════════════════════════════════════════════════════════════


class TestProtocolCompatibility:
    def test_resolver_is_callable(self) -> None:
        resolver = _make_resolver()
        assert callable(resolver)

    def test_resolver_signature_accepts_executor_string(self) -> None:
        sig = inspect.signature(ReadonlyReviewerTransportResolver.__call__)
        params = list(sig.parameters.keys())
        assert "requested_reviewer_executor" in params

    def test_resolver_returns_transport_protocol(self) -> None:
        resolver = _make_resolver()
        codex_result = resolver("codex")
        assert isinstance(codex_result, ReadonlyReviewerTransportProtocol)
        assert hasattr(codex_result, "execute")
        claude_result = resolver("claude-code")
        assert isinstance(claude_result, ReadonlyReviewerTransportProtocol)
        assert hasattr(claude_result, "execute")


# ══════════════════════════════════════════════════════════════════════
# I. Module import boundary
# ══════════════════════════════════════════════════════════════════════


class TestModuleImportBoundary:
    def test_module_has_no_forbidden_imports(self) -> None:
        import app.external_executors.readonly_reviewer_transport_resolver as mod
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_modules.add(node.module)
        forbidden = {
            "os",
            "subprocess",
        }
        for mod_name in imported_modules:
            top = mod_name.split(".")[0]
            assert top not in forbidden, f"Forbidden import: {mod_name}"
        for mod_name in imported_modules:
            assert not mod_name.startswith("app.services"), f"Must not import app.services: {mod_name}"
            assert not mod_name.startswith("app.repositories"), f"Must not import app.repositories: {mod_name}"
            assert not mod_name.startswith("app.api"), f"Must not import app.api: {mod_name}"
            assert not mod_name.startswith("app.core"), f"Must not import app.core: {mod_name}"

    def test_module_has_no_provider_binding(self) -> None:
        import app.external_executors.readonly_reviewer_transport_resolver as mod
        source = inspect.getsource(mod)
        for forbidden in [
            "MiMo", "DeepSeek", "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL", "credential", "provider_profile",
        ]:
            assert forbidden not in source, f"Forbidden reference: {forbidden}"


# ══════════════════════════════════════════════════════════════════════
# J. No caller / composition root responsibilities
# ══════════════════════════════════════════════════════════════════════


class TestNoCallerResponsibilities:
    def test_module_has_no_repository_or_settings_references(self) -> None:
        import app.external_executors.readonly_reviewer_transport_resolver as mod
        source = inspect.getsource(mod)
        for forbidden in [
            "ProjectDirectorMessageRepository",
            "ProjectDirectorSessionRepository",
            "TaskRepository",
            "settings",
            "os.environ",
            "workspace_root",
            "api_route",
        ]:
            assert forbidden not in source, f"Forbidden reference: {forbidden}"
