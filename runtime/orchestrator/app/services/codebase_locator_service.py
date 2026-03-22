"""Minimal Day05 file-location service for task-scoped repository exploration."""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath
from uuid import UUID

from app.domain._base import utc_now
from app.domain.code_context_pack import (
    FileLocatorCandidate,
    FileLocatorQuery,
    FileLocatorResult,
)
from app.domain.task import Task
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.repository_workspace_service import (
    DEFAULT_REPOSITORY_IGNORE_RULE_SUMMARY,
)


_DEFAULT_LIMIT = 12
_MAX_LIMIT = 50
_MAX_SCAN_FILE_BYTES = 256 * 1024
_PREVIEW_MAX_LENGTH = 180
_MAX_KEYWORDS = 12

_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_./-]{1,}|[\u4e00-\u9fff]{2,}")
_PATH_SPLIT_PATTERN = re.compile(r"[._/\-]+")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "api",
    "app",
    "build",
    "code",
    "day",
    "file",
    "files",
    "for",
    "from",
    "in",
    "into",
    "locator",
    "module",
    "of",
    "on",
    "or",
    "pack",
    "path",
    "paths",
    "plan",
    "planning",
    "project",
    "query",
    "repo",
    "repository",
    "service",
    "task",
    "the",
    "to",
    "update",
    "with",
}

_EXCLUDED_FILE_NAMES = {
    "package-lock.json",
    "poetry.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
}
_EXCLUDED_FILE_SUFFIXES = {
    ".7z",
    ".bin",
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".pyd",
    ".pyo",
    ".so",
    ".svg",
    ".tar",
    ".tgz",
    ".wasm",
    ".webp",
    ".zip",
}

_LANGUAGE_BY_NAME = {
    "dockerfile": "Docker",
    "makefile": "Makefile",
}
_LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript",
    ".md": "Markdown",
    ".mjs": "JavaScript",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".txt": "Text",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}
_FILE_TYPE_BY_NAME = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}
_FILE_TYPE_ALIASES = {
    "c++": "cpp",
    "docker": "dockerfile",
    "javascript": "js",
    "json": "json",
    "markdown": "md",
    "md": "md",
    "powershell": "ps1",
    "py": "py",
    "python": "py",
    "shell": "sh",
    "text": "txt",
    "toml": "toml",
    "ts": "ts",
    "tsx": "tsx",
    "typescript": "ts",
    "yaml": "yml",
    "yml": "yml",
}


class CodebaseLocatorError(ValueError):
    """Base error raised by the Day05 file-location service."""


class CodebaseLocatorProjectNotFoundError(CodebaseLocatorError):
    """Raised when one project is missing during Day05 file location."""


class CodebaseLocatorWorkspaceNotFoundError(CodebaseLocatorError):
    """Raised when one project has no bound repository workspace."""


class CodebaseLocatorTaskNotFoundError(CodebaseLocatorError):
    """Raised when one task cannot be resolved for the current project."""


class CodebaseLocatorRequestError(CodebaseLocatorError):
    """Raised when one locator request is missing all useful signals."""


class CodebaseLocatorService:
    """Locate a minimal candidate file set for one task or planning brief."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        task_repository: TaskRepository,
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.task_repository = task_repository

    def locate_files(
        self,
        project_id: UUID,
        *,
        task_id: UUID | None = None,
        task_query: str | None = None,
        keywords: list[str] | None = None,
        path_prefixes: list[str] | None = None,
        module_names: list[str] | None = None,
        file_types: list[str] | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> FileLocatorResult:
        """Return one bounded candidate file set for the provided Day05 query."""

        workspace, root_path = self._resolve_project_workspace(project_id)
        resolved_task = self._resolve_task(project_id=project_id, task_id=task_id)
        query = self._build_query(
            resolved_task=resolved_task,
            task_query=task_query,
            keywords=keywords,
            path_prefixes=path_prefixes,
            module_names=module_names,
            file_types=file_types,
            limit=limit,
        )

        ignored_directory_names = self._build_ignored_directory_names(
            workspace.ignore_rule_summary
        )
        matched_candidates: list[FileLocatorCandidate] = []
        scanned_file_count = 0

        for directory_path, directory_names, file_names in os.walk(root_path):
            directory_names[:] = [
                directory_name
                for directory_name in sorted(directory_names)
                if directory_name not in ignored_directory_names
                and not (Path(directory_path) / directory_name).is_symlink()
            ]

            for file_name in sorted(file_names):
                file_path = Path(directory_path) / file_name
                if self._should_skip_file(file_path):
                    continue

                text_content = self._read_text_file(file_path)
                if text_content is None:
                    continue

                scanned_file_count += 1
                candidate = self._build_candidate(
                    file_path=file_path,
                    root_path=root_path,
                    text_content=text_content,
                    query=query,
                )
                if candidate is not None:
                    matched_candidates.append(candidate)

        matched_candidates.sort(
            key=lambda item: (
                -item.score,
                -len(item.match_reasons),
                item.relative_path,
            )
        )
        total_match_count = len(matched_candidates)
        kept_candidates = matched_candidates[: query.limit]

        return FileLocatorResult(
            project_id=project_id,
            repository_root_path=str(root_path),
            ignored_directory_names=ignored_directory_names,
            query=query,
            scanned_file_count=scanned_file_count,
            candidate_count=len(kept_candidates),
            total_match_count=total_match_count,
            truncated=total_match_count > len(kept_candidates),
            generated_at=utc_now(),
            candidates=kept_candidates,
        )

    def get_project_repository_root_path(self, project_id: UUID) -> str:
        """Return one validated repository root path for Day05 context-pack actions."""

        _, root_path = self._resolve_project_workspace(project_id)
        return str(root_path)

    def _resolve_task(self, *, project_id: UUID, task_id: UUID | None) -> Task | None:
        """Resolve one optional task and keep it scoped to the current project."""

        if task_id is None:
            return None

        task = self.task_repository.get_by_id(task_id)
        if task is None or task.project_id != project_id:
            raise CodebaseLocatorTaskNotFoundError(
                f"Task not found in project: {task_id}"
            )

        return task

    def _resolve_project_workspace(self, project_id: UUID):
        """Validate one project workspace and return both the row and resolved root path."""

        if not self.project_repository.exists(project_id):
            raise CodebaseLocatorProjectNotFoundError(f"Project not found: {project_id}")

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise CodebaseLocatorWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        try:
            root_path = Path(workspace.root_path).resolve(strict=True)
        except FileNotFoundError as exc:
            raise CodebaseLocatorRequestError(
                "Repository root_path does not exist during file location."
            ) from exc

        if not root_path.is_dir():
            raise CodebaseLocatorRequestError(
                "Repository root_path must point to one local directory during file location."
            )

        return workspace, root_path

    def _build_query(
        self,
        *,
        resolved_task: Task | None,
        task_query: str | None,
        keywords: list[str] | None,
        path_prefixes: list[str] | None,
        module_names: list[str] | None,
        file_types: list[str] | None,
        limit: int,
    ) -> FileLocatorQuery:
        """Normalize one Day05 query into a stable domain payload."""

        normalized_limit = max(1, min(limit, _MAX_LIMIT))
        normalized_task_query = (task_query or "").strip() or None

        extracted_keywords = self._extract_keywords(
            " ".join(
                part
                for part in [
                    resolved_task.title if resolved_task is not None else None,
                    resolved_task.input_summary if resolved_task is not None else None,
                    normalized_task_query,
                ]
                if part
            )
        )

        explicit_keywords = self._normalize_keywords(keywords or [])
        merged_keywords = self._merge_lists(
            explicit_keywords,
            extracted_keywords,
            limit=_MAX_KEYWORDS,
        )
        normalized_path_prefixes = self._normalize_path_prefixes(path_prefixes or [])
        normalized_module_names = self._normalize_module_names(module_names or [])
        normalized_file_types = self._normalize_file_types(file_types or [])

        if not any(
            [
                merged_keywords,
                normalized_path_prefixes,
                normalized_module_names,
                normalized_file_types,
            ]
        ):
            raise CodebaseLocatorRequestError(
                "File locator requires at least one task signal, keyword, path prefix, module name or file type."
            )

        return FileLocatorQuery(
            task_id=resolved_task.id if resolved_task is not None else None,
            task_title=resolved_task.title if resolved_task is not None else None,
            task_query=normalized_task_query,
            keywords=merged_keywords,
            path_prefixes=normalized_path_prefixes,
            module_names=normalized_module_names,
            file_types=normalized_file_types,
            limit=normalized_limit,
            summary=self._build_query_summary(
                task=resolved_task,
                task_query=normalized_task_query,
                keywords=merged_keywords,
                path_prefixes=normalized_path_prefixes,
                module_names=normalized_module_names,
                file_types=normalized_file_types,
            ),
        )

    @staticmethod
    def _build_ignored_directory_names(ignore_rule_summary: list[str]) -> list[str]:
        """Merge the Day01 default ignore baseline with repository-specific rules."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in (*DEFAULT_REPOSITORY_IGNORE_RULE_SUMMARY, *ignore_rule_summary):
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items

    @staticmethod
    def _merge_lists(*groups: list[str], limit: int) -> list[str]:
        """Merge multiple ordered string groups while keeping the first unique values."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for group in groups:
            for item in group:
                normalized_item = item.strip()
                if not normalized_item or normalized_item in seen_items:
                    continue

                normalized_items.append(normalized_item)
                seen_items.add(normalized_item)
                if len(normalized_items) >= limit:
                    return normalized_items

        return normalized_items

    def _normalize_keywords(self, keywords: list[str]) -> list[str]:
        """Normalize explicit keyword filters and split path-like composite tokens."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for keyword in keywords:
            for token in self._extract_keywords(keyword):
                if token in seen_items:
                    continue
                normalized_items.append(token)
                seen_items.add(token)
                if len(normalized_items) >= _MAX_KEYWORDS:
                    return normalized_items

        return normalized_items

    @staticmethod
    def _normalize_path_prefixes(path_prefixes: list[str]) -> list[str]:
        """Normalize one path-prefix filter list into safe POSIX strings."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for raw_value in path_prefixes:
            normalized_value = raw_value.replace("\\", "/").strip()
            normalized_value = normalized_value.lstrip("./").strip("/")
            if not normalized_value:
                continue

            normalized_path = PurePosixPath(normalized_value)
            if normalized_path.is_absolute() or ".." in normalized_path.parts:
                continue

            serialized_path = normalized_path.as_posix()
            if serialized_path in seen_items:
                continue

            normalized_items.append(serialized_path.lower())
            seen_items.add(serialized_path)

        return normalized_items

    @staticmethod
    def _normalize_module_names(module_names: list[str]) -> list[str]:
        """Normalize one module-name filter list."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for raw_value in module_names:
            normalized_value = raw_value.strip().lower()
            normalized_value = normalized_value.strip("._/-")
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @staticmethod
    def _normalize_file_types(file_types: list[str]) -> list[str]:
        """Normalize one file-type filter list into stable extension-like values."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for raw_value in file_types:
            normalized_value = raw_value.strip().lower().lstrip(".")
            normalized_value = _FILE_TYPE_ALIASES.get(normalized_value, normalized_value)
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract a compact keyword set from task or planning text."""

        if not text.strip():
            return []

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for raw_token in _TOKEN_PATTERN.findall(text):
            token_candidates = [raw_token.lower()]
            if any(separator in raw_token for separator in ("_", "-", "/", ".")):
                token_candidates.extend(
                    fragment
                    for fragment in _PATH_SPLIT_PATTERN.split(raw_token.lower())
                    if fragment
                )

            for token in token_candidates:
                normalized_token = token.strip("._/-")
                if len(normalized_token) < 2 or normalized_token in _STOPWORDS:
                    continue
                if normalized_token in seen_items:
                    continue

                normalized_items.append(normalized_token)
                seen_items.add(normalized_token)
                if len(normalized_items) >= _MAX_KEYWORDS:
                    return normalized_items

        return normalized_items

    def _build_candidate(
        self,
        *,
        file_path: Path,
        root_path: Path,
        text_content: str,
        query: FileLocatorQuery,
    ) -> FileLocatorCandidate | None:
        """Compute one ranked candidate for a text file, if it matches the query."""

        relative_path = file_path.relative_to(root_path).as_posix()
        normalized_relative_path = relative_path.lower()
        normalized_file_name = file_path.name.lower()
        normalized_segments = {
            part.lower()
            for part in file_path.relative_to(root_path).parts
        }
        normalized_segments.update(
            fragment
            for fragment in _PATH_SPLIT_PATTERN.split(file_path.stem.lower())
            if fragment
        )
        normalized_content = text_content.lower()
        file_type = self._infer_file_type(file_path)
        language = self._infer_language(file_path)

        score = 0
        match_reasons: list[str] = []
        matched_keywords: list[str] = []

        for path_prefix in query.path_prefixes:
            if normalized_relative_path.startswith(path_prefix):
                score += 120
                match_reasons.append(f"路径前缀命中：{path_prefix}")

        for module_name in query.module_names:
            if module_name in normalized_segments:
                score += 70
                match_reasons.append(f"模块命中：{module_name}")
            elif module_name in normalized_relative_path:
                score += 40
                match_reasons.append(f"路径包含模块词：{module_name}")

        for requested_file_type in query.file_types:
            if requested_file_type == file_type or requested_file_type == self._normalize_language(
                language
            ):
                score += 45
                match_reasons.append(f"文件类型命中：{requested_file_type}")

        for keyword in query.keywords:
            if keyword in normalized_segments or keyword in normalized_file_name:
                score += 40
                matched_keywords.append(keyword)
                match_reasons.append(f"文件名/模块命中：{keyword}")
            elif keyword in normalized_relative_path:
                score += 28
                matched_keywords.append(keyword)
                match_reasons.append(f"路径命中：{keyword}")
            elif keyword in normalized_content:
                score += 12
                matched_keywords.append(keyword)
                match_reasons.append(f"内容命中：{keyword}")

        if score <= 0:
            return None

        return FileLocatorCandidate(
            relative_path=relative_path,
            language=language,
            file_type=file_type,
            byte_size=len(text_content.encode("utf-8")),
            line_count=len(text_content.splitlines()),
            score=score,
            match_reasons=match_reasons,
            matched_keywords=matched_keywords,
            preview=self._build_preview(
                text_content=text_content,
                matched_keywords=matched_keywords,
            ),
        )

    @staticmethod
    def _should_skip_file(file_path: Path) -> bool:
        """Return whether one file is obviously irrelevant for Day05 location."""

        if file_path.is_symlink():
            return True

        normalized_name = file_path.name.lower()
        if normalized_name in _EXCLUDED_FILE_NAMES:
            return True

        if file_path.suffix.lower() in _EXCLUDED_FILE_SUFFIXES:
            return True

        try:
            return file_path.stat().st_size > _MAX_SCAN_FILE_BYTES
        except OSError:
            return True

    @staticmethod
    def _read_text_file(file_path: Path) -> str | None:
        """Read one candidate file as UTF-8 text, skipping obvious binary payloads."""

        try:
            raw_bytes = file_path.read_bytes()
        except OSError:
            return None

        if b"\x00" in raw_bytes:
            return None

        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw_bytes.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                return None

    @staticmethod
    def _build_preview(*, text_content: str, matched_keywords: list[str]) -> str | None:
        """Build one short preview line for the file-locator UI."""

        preview_line: str | None = None
        lowered_keywords = [keyword.lower() for keyword in matched_keywords]

        for line in text_content.splitlines():
            stripped_line = line.strip()
            if not stripped_line:
                continue

            if lowered_keywords and any(keyword in stripped_line.lower() for keyword in lowered_keywords):
                preview_line = stripped_line
                break
            if preview_line is None:
                preview_line = stripped_line

        if preview_line is None:
            return None

        if len(preview_line) <= _PREVIEW_MAX_LENGTH:
            return preview_line

        return preview_line[: _PREVIEW_MAX_LENGTH - 3].rstrip() + "..."

    @staticmethod
    def _infer_language(file_path: Path) -> str:
        """Map one file path to a coarse language bucket."""

        normalized_name = file_path.name.lower()
        if normalized_name in _LANGUAGE_BY_NAME:
            return _LANGUAGE_BY_NAME[normalized_name]

        return _LANGUAGE_BY_SUFFIX.get(file_path.suffix.lower(), "Other")

    @staticmethod
    def _infer_file_type(file_path: Path) -> str:
        """Map one file path to a stable extension-like file-type label."""

        normalized_name = file_path.name.lower()
        if normalized_name in _FILE_TYPE_BY_NAME:
            return _FILE_TYPE_BY_NAME[normalized_name]

        normalized_suffix = file_path.suffix.lower().lstrip(".")
        if normalized_suffix:
            return normalized_suffix

        return normalized_name

    @staticmethod
    def _normalize_language(language: str) -> str:
        """Normalize language labels for file-type matching."""

        return _FILE_TYPE_ALIASES.get(language.strip().lower(), language.strip().lower())

    def _build_query_summary(
        self,
        *,
        task: Task | None,
        task_query: str | None,
        keywords: list[str],
        path_prefixes: list[str],
        module_names: list[str],
        file_types: list[str],
    ) -> str:
        """Compress normalized locator signals into one readable summary."""

        summary_parts: list[str] = []

        if task is not None:
            summary_parts.append(f"任务：{task.title}")
        if task_query:
            summary_parts.append("规划摘要：已提供补充说明")
        if keywords:
            summary_parts.append("关键词：" + "、".join(keywords[:6]))
        if path_prefixes:
            summary_parts.append("路径前缀：" + "、".join(path_prefixes[:4]))
        if module_names:
            summary_parts.append("模块：" + "、".join(module_names[:4]))
        if file_types:
            summary_parts.append("文件类型：" + "、".join(file_types[:4]))

        summary = "；".join(summary_parts)
        if len(summary) <= 1_200:
            return summary

        return summary[:1_197].rstrip() + "..."
