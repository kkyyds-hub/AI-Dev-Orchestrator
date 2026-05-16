"""Runtime settings for repository workspace safety boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class RepositoryWorkspaceSettingsSummary:
    """Safe summary of configured repository workspace roots."""

    allowed_workspace_roots: list[str]
    default_workspace_root: str
    using_default: bool


class RepositoryWorkspaceSettingsError(ValueError):
    """Raised when repository workspace settings are invalid."""


class RepositoryWorkspaceSettingsService:
    """Read and persist user-maintained repository workspace roots.

    The configured list acts as an explicit allow-list for repository binding.
    When users have not saved any roots, the legacy
    REPOSITORY_WORKSPACE_ROOT_DIR behavior remains the effective fallback.
    """

    def __init__(self, *, config_path: Path | None = None) -> None:
        self.config_path = (
            config_path
            if config_path is not None
            else settings.runtime_data_dir
            / "repository-workspace-settings"
            / "allowed-workspace-roots.json"
        )

    def get_summary(self) -> RepositoryWorkspaceSettingsSummary:
        """Return the effective allowed roots shown by the settings page."""

        configured_roots = self._load_configured_roots()
        using_default = len(configured_roots) == 0
        effective_roots = (
            [self._get_default_workspace_root()]
            if using_default
            else configured_roots
        )
        return RepositoryWorkspaceSettingsSummary(
            allowed_workspace_roots=[str(path) for path in effective_roots],
            default_workspace_root=str(self._get_default_workspace_root()),
            using_default=using_default,
        )

    def update_allowed_workspace_roots(
        self,
        roots: list[str],
    ) -> RepositoryWorkspaceSettingsSummary:
        """Persist a normalized root allow-list and return the new summary."""

        normalized_roots = self._normalize_roots_for_save(roots)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "allowed_workspace_roots": [str(path) for path in normalized_roots],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return self.get_summary()

    def get_effective_allowed_workspace_roots(self) -> list[Path]:
        """Return validated roots used by repository binding path checks."""

        configured_roots = self._load_configured_roots()
        if configured_roots:
            return configured_roots

        return [self._get_default_workspace_root()]

    def _load_configured_roots(self) -> list[Path]:
        """Load normalized saved roots.

        Only an absent config file means "no user configuration".  Once the
        file exists, malformed or stale contents fail closed instead of
        widening the effective boundary back to the default root.
        """

        if not self.config_path.exists():
            return []

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RepositoryWorkspaceSettingsError(
                "Failed to read repository workspace settings."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RepositoryWorkspaceSettingsError(
                "Repository workspace settings file is not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise RepositoryWorkspaceSettingsError(
                "Repository workspace settings file must contain one JSON object."
            )

        raw_roots = payload.get("allowed_workspace_roots")
        if not isinstance(raw_roots, list):
            raise RepositoryWorkspaceSettingsError(
                "Repository workspace settings must include allowed_workspace_roots."
            )

        if not all(isinstance(item, str) for item in raw_roots):
            raise RepositoryWorkspaceSettingsError(
                "Repository workspace roots must be strings."
            )

        return self._normalize_roots_for_save(raw_roots)

    def _normalize_roots_for_save(self, roots: list[str]) -> list[Path]:
        """Normalize, validate and deduplicate one root allow-list."""

        normalized_roots: list[Path] = []
        seen_roots: set[str] = set()
        for root in roots:
            normalized_root = self._normalize_one_root(root)
            root_key = str(normalized_root).casefold()
            if root_key in seen_roots:
                continue
            normalized_roots.append(normalized_root)
            seen_roots.add(root_key)
        return normalized_roots

    def _normalize_one_root(self, root: str) -> Path:
        """Validate one workspace root without expanding the safety boundary."""

        normalized_input = root.strip()
        if not normalized_input:
            raise RepositoryWorkspaceSettingsError(
                "Allowed workspace root cannot be blank."
            )

        candidate_root = Path(normalized_input).expanduser()
        if not candidate_root.is_absolute():
            raise RepositoryWorkspaceSettingsError(
                "Allowed workspace root must be an absolute local path."
            )

        try:
            resolved_root = candidate_root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise RepositoryWorkspaceSettingsError(
                f"Allowed workspace root does not exist: {normalized_input}"
            ) from exc

        if not resolved_root.is_dir():
            raise RepositoryWorkspaceSettingsError(
                f"Allowed workspace root must be a directory: {normalized_input}"
            )

        if resolved_root.parent == resolved_root:
            raise RepositoryWorkspaceSettingsError(
                "Allowed workspace root cannot be the filesystem root."
            )

        runtime_data_dir = settings.runtime_data_dir.resolve(strict=False)
        if resolved_root == runtime_data_dir or runtime_data_dir in resolved_root.parents:
            raise RepositoryWorkspaceSettingsError(
                "Allowed workspace root cannot point inside the orchestrator runtime data directory."
            )

        system_temp_dir = Path(tempfile.gettempdir()).resolve(strict=False)
        if resolved_root == system_temp_dir or system_temp_dir in resolved_root.parents:
            raise RepositoryWorkspaceSettingsError(
                "Allowed workspace root cannot point inside the system temporary directory."
            )

        return resolved_root

    @staticmethod
    def _get_default_workspace_root() -> Path:
        """Return the legacy env-configured workspace root as an existing directory."""

        candidate_root = settings.repository_workspace_root_dir
        if not candidate_root.exists():
            raise RepositoryWorkspaceSettingsError(
                "Configured allowed workspace root does not exist."
            )
        if not candidate_root.is_dir():
            raise RepositoryWorkspaceSettingsError(
                "Configured allowed workspace root must be a directory."
            )

        return candidate_root.resolve(strict=True)
