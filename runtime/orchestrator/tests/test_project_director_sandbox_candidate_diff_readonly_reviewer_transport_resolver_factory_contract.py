"""Contract tests for readonly reviewer transport resolver factory."""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.external_executors.readonly_reviewer_transport_resolver import (
    ReadonlyReviewerTransportResolver,
)
from app.external_executors.readonly_reviewer_transport_resolver_factory import (
    ReadonlyReviewerTransportResolverFactory,
)


class SpyResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.kwargs: dict[str, Any] = {}

    def __call__(self, executor: str) -> Any:
        self.calls.append(executor)
        return MagicMock()


class SpyPopenFactory:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return MagicMock()


def _make_factory(
    *,
    workspace_root_path: str | None = None,
    tmp_path: Any = None,
    timeout_seconds: float = 180.0,
    max_output_bytes: int = 256 * 1024,
    process_supervisor: Any = None,
    popen_factory: Any = None,
    terminate_wait_seconds: float = 0.2,
    claude_code_child_environment: dict[str, str] | None = None,
) -> ReadonlyReviewerTransportResolverFactory:
    if workspace_root_path is None:
        assert tmp_path is not None
        root = tmp_path / "root"
        root.mkdir()
        workspace_root_path = str(root)
    return ReadonlyReviewerTransportResolverFactory(
        workspace_root_path=workspace_root_path,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        process_supervisor=process_supervisor or MagicMock(),
        popen_factory=popen_factory or MagicMock(),
        terminate_wait_seconds=terminate_wait_seconds,
        claude_code_child_environment=claude_code_child_environment,
    )


# ══════════════════════════════════════════════════════════════════════
# A1. Constructor does not create Resolver
# ══════════════════════════════════════════════════════════════════════


class TestConstructorNoResolver:
    def test_construct_does_not_create_resolver(self, tmp_path, monkeypatch) -> None:
        spy_cls = MagicMock()
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver_factory"
            ".ReadonlyReviewerTransportResolver",
            spy_cls,
        )
        popen_spy = SpyPopenFactory()
        _make_factory(tmp_path=tmp_path, popen_factory=popen_spy)
        assert spy_cls.call_count == 0
        assert popen_spy.calls == []


# ══════════════════════════════════════════════════════════════════════
# A2. Workspace root input validation
# ══════════════════════════════════════════════════════════════════════


class TestWorkspaceRootValidation:
    def test_empty_root_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _make_factory(workspace_root_path="")

    def test_blank_root_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _make_factory(workspace_root_path="   ")

    def test_relative_root_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="absolute"):
            _make_factory(workspace_root_path="relative/path")

    def test_nonexistent_root_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="must exist"):
            _make_factory(workspace_root_path=str(tmp_path / "nonexistent"))

    def test_file_root_raises(self, tmp_path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="directory"):
            _make_factory(workspace_root_path=str(f))

    def test_none_root_raises(self) -> None:
        with pytest.raises((ValueError, TypeError, AssertionError)):
            ReadonlyReviewerTransportResolverFactory(
                workspace_root_path=None,
                timeout_seconds=1.0,
                max_output_bytes=1000,
                process_supervisor=MagicMock(),
                popen_factory=MagicMock(),
            )


# ══════════════════════════════════════════════════════════════════════
# A3. Root revalidation after deletion
# ══════════════════════════════════════════════════════════════════════


class TestRootRevalidation:
    def test_root_deleted_after_construct_raises_on_call(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        workspace = root / "workspace"
        workspace.mkdir()
        factory = _make_factory(workspace_root_path=str(root))
        import shutil
        shutil.rmtree(str(root))
        popen_spy = SpyPopenFactory()
        with pytest.raises(ValueError, match="must exist"):
            factory(str(workspace))
        assert popen_spy.calls == []


# ══════════════════════════════════════════════════════════════════════
# A4. Workspace input validation
# ══════════════════════════════════════════════════════════════════════


class TestWorkspaceValidation:
    def test_empty_workspace_raises(self, tmp_path) -> None:
        factory = _make_factory(tmp_path=tmp_path)
        with pytest.raises(ValueError, match="non-empty"):
            factory("")

    def test_blank_workspace_raises(self, tmp_path) -> None:
        factory = _make_factory(tmp_path=tmp_path)
        with pytest.raises(ValueError, match="non-empty"):
            factory("   ")

    def test_relative_workspace_raises(self, tmp_path) -> None:
        factory = _make_factory(tmp_path=tmp_path)
        with pytest.raises(ValueError, match="absolute"):
            factory("relative/path")

    def test_workspace_equals_root_raises(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        factory = _make_factory(workspace_root_path=str(root))
        with pytest.raises(ValueError, match="strict subdirectory"):
            factory(str(root))

    def test_sibling_outside_root_raises(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        factory = _make_factory(workspace_root_path=str(root))
        with pytest.raises(ValueError, match="strict subdirectory"):
            factory(str(sibling))

    def test_nonexistent_workspace_raises(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        factory = _make_factory(workspace_root_path=str(root))
        with pytest.raises(ValueError, match="must exist"):
            factory(str(root / "nonexistent"))

    def test_file_workspace_raises(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = root / "file.txt"
        f.write_text("x")
        factory = _make_factory(workspace_root_path=str(root))
        with pytest.raises(ValueError, match="directory"):
            factory(str(f))

    def test_none_workspace_raises(self, tmp_path) -> None:
        factory = _make_factory(tmp_path=tmp_path)
        with pytest.raises(ValueError, match="non-empty"):
            factory(None)


# ══════════════════════════════════════════════════════════════════════
# A5. Strict subdirectory contract
# ══════════════════════════════════════════════════════════════════════


class TestStrictSubdirectory:
    def test_root_itself_rejected(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        factory = _make_factory(workspace_root_path=str(root))
        with pytest.raises(ValueError, match="strict subdirectory"):
            factory(str(root))

    def test_child_accepted(self, tmp_path, monkeypatch) -> None:
        root = tmp_path / "root"
        root.mkdir()
        child = root / "child"
        child.mkdir()
        spy_cls = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver_factory"
            ".ReadonlyReviewerTransportResolver",
            spy_cls,
        )
        factory = _make_factory(workspace_root_path=str(root))
        result = factory(str(child))
        assert spy_cls.call_count == 1
        assert result is spy_cls.return_value


# ══════════════════════════════════════════════════════════════════════
# A6. Symlink escape
# ══════════════════════════════════════════════════════════════════════


class TestSymlinkEscape:
    def test_symlink_escape_rejected(self, tmp_path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        link = root / "link"
        try:
            os.symlink(str(outside), str(link))
        except OSError:
            pytest.skip("symlink not supported on this platform")
        factory = _make_factory(workspace_root_path=str(root))
        with pytest.raises(ValueError, match="strict subdirectory"):
            factory(str(link))


# ══════════════════════════════════════════════════════════════════════
# A7. Valid workspace creates Resolver exactly once
# ══════════════════════════════════════════════════════════════════════


class TestValidWorkspaceCreatesResolver:
    def test_creates_resolver_once(self, tmp_path, monkeypatch) -> None:
        sentinel = MagicMock()
        spy_cls = MagicMock(return_value=sentinel)
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver_factory"
            ".ReadonlyReviewerTransportResolver",
            spy_cls,
        )
        root = tmp_path / "root"
        root.mkdir()
        workspace = root / "workspace"
        workspace.mkdir()
        factory = _make_factory(workspace_root_path=str(root))
        result = factory(str(workspace))
        assert spy_cls.call_count == 1
        assert result is sentinel


# ══════════════════════════════════════════════════════════════════════
# A8. Resolved absolute workspace
# ══════════════════════════════════════════════════════════════════════


class TestResolvedAbsoluteWorkspace:
    def test_passes_resolved_path(self, tmp_path, monkeypatch) -> None:
        spy_cls = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver_factory"
            ".ReadonlyReviewerTransportResolver",
            spy_cls,
        )
        root = tmp_path / "root"
        root.mkdir()
        child = root / "child"
        child.mkdir()
        raw_path = str(child) + "/."
        factory = _make_factory(workspace_root_path=str(root))
        factory(raw_path)
        kwargs = spy_cls.call_args[1]
        expected = Path(raw_path).resolve(strict=False)
        assert kwargs["workspace_path"] == str(expected)


# ══════════════════════════════════════════════════════════════════════
# A9. Dependency passthrough
# ══════════════════════════════════════════════════════════════════════


class TestDependencyPassthrough:
    def test_all_dependencies_passed(self, tmp_path, monkeypatch) -> None:
        spy_cls = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver_factory"
            ".ReadonlyReviewerTransportResolver",
            spy_cls,
        )
        root = tmp_path / "root"
        root.mkdir()
        workspace = root / "ws"
        workspace.mkdir()
        supervisor = MagicMock()
        popen = MagicMock()
        env = {"KEY": "val"}
        factory = ReadonlyReviewerTransportResolverFactory(
            workspace_root_path=str(root),
            timeout_seconds=99.0,
            max_output_bytes=12345,
            process_supervisor=supervisor,
            popen_factory=popen,
            terminate_wait_seconds=0.5,
            claude_code_child_environment=env,
        )
        factory(str(workspace))
        kwargs = spy_cls.call_args[1]
        assert kwargs["timeout_seconds"] == 99.0
        assert kwargs["max_output_bytes"] == 12345
        assert kwargs["process_supervisor"] is supervisor
        assert kwargs["popen_factory"] is popen
        assert kwargs["terminate_wait_seconds"] == 0.5
        assert kwargs["claude_code_child_environment"] is env


# ══════════════════════════════════════════════════════════════════════
# A10. Factory does not call popen_factory
# ══════════════════════════════════════════════════════════════════════


class TestNoPopenCall:
    def test_factory_does_not_call_popen(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.external_executors.readonly_reviewer_transport_resolver_factory"
            ".ReadonlyReviewerTransportResolver",
            MagicMock(return_value=MagicMock()),
        )
        popen_spy = SpyPopenFactory()
        root = tmp_path / "root"
        root.mkdir()
        workspace = root / "ws"
        workspace.mkdir()
        factory = _make_factory(workspace_root_path=str(root), popen_factory=popen_spy)
        factory(str(workspace))
        assert popen_spy.calls == []


# ══════════════════════════════════════════════════════════════════════
# A11. Factory does not create process supervisor
# ══════════════════════════════════════════════════════════════════════


class TestNoSupervisorCreation:
    def test_factory_module_has_no_supervisor_constructor_call(self) -> None:
        import app.external_executors.readonly_reviewer_transport_resolver_factory as mod
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "RealExecutorProcessSupervisor":
                    pytest.fail(
                        f"Factory module must not call RealExecutorProcessSupervisor() "
                        f"at line {node.lineno}"
                    )


# ══════════════════════════════════════════════════════════════════════
# A12. Factory module boundary
# ══════════════════════════════════════════════════════════════════════


class TestModuleBoundary:
    def test_no_forbidden_imports(self) -> None:
        import app.external_executors.readonly_reviewer_transport_resolver_factory as mod
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
        forbidden_tops = {"os", "subprocess"}
        for mod_name in imported_modules:
            top = mod_name.split(".")[0]
            assert top not in forbidden_tops, f"Forbidden import: {mod_name}"
        for mod_name in imported_modules:
            assert not mod_name.startswith("app.services"), f"Forbidden: {mod_name}"
            assert not mod_name.startswith("app.repositories"), f"Forbidden: {mod_name}"
            assert not mod_name.startswith("app.api"), f"Forbidden: {mod_name}"
            assert not mod_name.startswith("app.core"), f"Forbidden: {mod_name}"

    def test_no_provider_binding(self) -> None:
        import app.external_executors.readonly_reviewer_transport_resolver_factory as mod
        source = inspect.getsource(mod)
        for forbidden in [
            "MiMo", "DeepSeek", "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL", "credential", "provider_profile",
        ]:
            assert forbidden not in source, f"Forbidden reference: {forbidden}"
