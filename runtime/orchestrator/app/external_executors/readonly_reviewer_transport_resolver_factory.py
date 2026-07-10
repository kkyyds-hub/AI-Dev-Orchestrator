"""Create readonly reviewer transport resolvers for trusted workspaces."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessSupervisor,
)
from app.external_executors.readonly_reviewer_transport_resolver import (
    ReadonlyReviewerTransportResolver,
)


class ReadonlyReviewerTransportResolverFactory:
    """Validate current workspace state before creating a resolver."""

    def __init__(
        self,
        *,
        workspace_root_path: str,
        timeout_seconds: float,
        max_output_bytes: int,
        process_supervisor: RealExecutorProcessSupervisor,
        popen_factory: Any,
        terminate_wait_seconds: float = 0.2,
        claude_code_child_environment: Mapping[str, str] | None = None,
    ) -> None:
        self._workspace_root_path = self._validated_workspace_root(
            workspace_root_path
        )
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._process_supervisor = process_supervisor
        self._popen_factory = popen_factory
        self._terminate_wait_seconds = terminate_wait_seconds
        self._claude_code_child_environment = claude_code_child_environment

    def __call__(
        self,
        workspace_path: str,
    ) -> ReadonlyReviewerTransportResolver:
        workspace_root = self._validated_workspace_root(
            str(self._workspace_root_path)
        )
        workspace = self._validated_workspace(
            workspace_path,
            workspace_root=workspace_root,
        )
        return ReadonlyReviewerTransportResolver(
            workspace_path=str(workspace),
            timeout_seconds=self._timeout_seconds,
            max_output_bytes=self._max_output_bytes,
            process_supervisor=self._process_supervisor,
            popen_factory=self._popen_factory,
            terminate_wait_seconds=self._terminate_wait_seconds,
            claude_code_child_environment=self._claude_code_child_environment,
        )

    @staticmethod
    def _validated_workspace_root(workspace_root_path: str) -> Path:
        if (
            not isinstance(workspace_root_path, str)
            or not workspace_root_path.strip()
        ):
            raise ValueError("workspace_root_path must be non-empty")
        path = Path(workspace_root_path)
        if not path.is_absolute():
            raise ValueError("workspace_root_path must be absolute")
        try:
            resolved_path = path.resolve(strict=False)
            exists = resolved_path.exists()
            is_directory = resolved_path.is_dir()
        except (OSError, RuntimeError) as exc:
            raise ValueError("workspace_root_path is unavailable") from exc
        if not exists:
            raise ValueError("workspace_root_path must exist")
        if not is_directory:
            raise ValueError("workspace_root_path must be a directory")
        return resolved_path

    @staticmethod
    def _validated_workspace(
        workspace_path: str,
        *,
        workspace_root: Path,
    ) -> Path:
        if not isinstance(workspace_path, str) or not workspace_path.strip():
            raise ValueError("workspace_path must be non-empty")
        path = Path(workspace_path)
        if not path.is_absolute():
            raise ValueError("workspace_path must be absolute")
        try:
            resolved_path = path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ValueError("workspace_path is unavailable") from exc
        if (
            resolved_path == workspace_root
            or workspace_root not in resolved_path.parents
        ):
            raise ValueError(
                "workspace_path must be a strict subdirectory of workspace_root_path"
            )
        try:
            exists = resolved_path.exists()
            is_directory = resolved_path.is_dir()
        except OSError as exc:
            raise ValueError("workspace_path is unavailable") from exc
        if not exists:
            raise ValueError("workspace_path must exist")
        if not is_directory:
            raise ValueError("workspace_path must be a directory")
        return resolved_path


__all__ = ("ReadonlyReviewerTransportResolverFactory",)
