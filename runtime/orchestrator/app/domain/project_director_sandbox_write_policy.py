"""Policy-only path checks for Project Director sandbox write preflight."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator

from app.domain._base import DomainModel


DEFAULT_DENIED_PATH_PREFIXES = (
    ".git/",
    "node_modules/",
    "dist/",
    "build/",
    "docs/superpowers/",
)

DEFAULT_DENIED_EXACT_NAMES = (
    ".env",
    ".env.local",
    ".env.production",
)

DEFAULT_DENIED_SUBSTRINGS = (
    "secret",
    "secrets",
    "credential",
    "credentials",
    "private_key",
    "api_key",
    "token",
)

DEFAULT_DENIED_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    ".der",
    ".bin",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
)

DEFAULT_DENIED_LOCKFILES = (
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
    "Cargo.lock",
    "Gemfile.lock",
)

DEFAULT_ALLOWED_PATH_PREFIXES = (
    "runtime/orchestrator/app/",
    "runtime/orchestrator/tests/",
    "runtime/orchestrator/scripts/",
    "docs/product/ai-project-director/",
)

SandboxFileOperationType = Literal["create", "update"]


class ProjectDirectorSandboxPathPolicyFinding(DomainModel):
    """One policy finding for a candidate sandbox path."""

    path: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=200)
    rule: str = Field(min_length=1, max_length=200)


class ProjectDirectorSandboxPathPolicyResult(DomainModel):
    """Policy-only result for one candidate file operation path."""

    allowed: bool
    path: str = Field(min_length=1, max_length=1_000)
    normalized_path: str | None = None
    findings: list[ProjectDirectorSandboxPathPolicyFinding] = Field(
        default_factory=list
    )
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    git_write_performed: bool = False
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "product_runtime_git_write_allowed",
        "main_worktree_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "actual_patch_applied",
        "git_write_performed",
        mode="after",
    )
    @classmethod
    def reject_write_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("sandbox path policy write flags must remain false")
        return value


def normalize_candidate_path(path: str) -> str | None:
    """Normalize a relative candidate path without touching the filesystem."""

    candidate = path.replace("\\", "/").strip()
    while candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate:
        return None
    if candidate.startswith("/"):
        return None

    raw_parts = candidate.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        return None

    pure_path = PurePosixPath(candidate)
    if pure_path.is_absolute():
        return None
    if any(part in ("", ".", "..") for part in pure_path.parts):
        return None
    return pure_path.as_posix()


def check_sandbox_path_policy(
    path: str,
    *,
    allowed_path_prefixes: list[str] | None = None,
    allow_frontend: bool = False,
    allow_lockfile: bool = False,
    allow_binary: bool = False,
    operation: SandboxFileOperationType = "update",
) -> ProjectDirectorSandboxPathPolicyResult:
    """Check a path against P20 policy-only sandbox write boundaries."""

    normalized_path = normalize_candidate_path(path)
    findings: list[ProjectDirectorSandboxPathPolicyFinding] = []

    if operation not in ("create", "update"):
        findings.append(
            _finding(
                path=path,
                reason="unsupported_operation",
                rule="operation_must_be_create_or_update",
            )
        )

    if normalized_path is None:
        findings.append(
            _finding(
                path=path,
                reason="path_traversal_or_absolute",
                rule="relative_normalized_path_required",
            )
        )
        return ProjectDirectorSandboxPathPolicyResult(
            allowed=False,
            path=path,
            normalized_path=None,
            findings=findings,
        )

    prefixes = tuple(allowed_path_prefixes or DEFAULT_ALLOWED_PATH_PREFIXES)
    normalized_prefixes = tuple(
        prefix for prefix in (_normalize_prefix(item) for item in prefixes) if prefix
    )
    lower_path = normalized_path.lower()
    path_parts = normalized_path.split("/")
    basename = path_parts[-1]

    if not _matches_any_prefix(normalized_path, normalized_prefixes):
        findings.append(
            _finding(
                path=normalized_path,
                reason="path_not_in_allowlist",
                rule="allowed_path_prefixes",
            )
        )

    for denied_prefix in DEFAULT_DENIED_PATH_PREFIXES:
        if _matches_prefix(normalized_path, denied_prefix):
            reason = (
                "docs_superpowers_forbidden"
                if denied_prefix == "docs/superpowers/"
                else "denied_prefix"
            )
            findings.append(
                _finding(path=normalized_path, reason=reason, rule=denied_prefix)
            )

    if ".git" in path_parts:
        findings.append(
            _finding(
                path=normalized_path,
                reason="denied_prefix",
                rule=".git/",
            )
        )

    if _matches_prefix(normalized_path, "apps/web/"):
        frontend_prefix_allowed = any(
            _matches_prefix("apps/web/placeholder", prefix)
            or prefix.rstrip("/") == "apps/web"
            for prefix in normalized_prefixes
        )
        if not allow_frontend or not frontend_prefix_allowed:
            findings.append(
                _finding(
                    path=normalized_path,
                    reason="frontend_not_explicitly_allowed",
                    rule="allow_frontend_and_apps_web_prefix_required",
                )
            )

    denied_exact_name = next(
        (part for part in path_parts if part in DEFAULT_DENIED_EXACT_NAMES),
        None,
    )
    if denied_exact_name is not None:
        findings.append(
            _finding(
                path=normalized_path,
                reason="denied_exact_name",
                rule=denied_exact_name,
            )
        )

    for substring in DEFAULT_DENIED_SUBSTRINGS:
        if substring in lower_path:
            findings.append(
                _finding(
                    path=normalized_path,
                    reason="denied_sensitive_substring",
                    rule=substring,
                )
            )
            break

    if basename in DEFAULT_DENIED_LOCKFILES and not allow_lockfile:
        findings.append(
            _finding(
                path=normalized_path,
                reason="denied_lockfile",
                rule=basename,
            )
        )

    if not allow_binary:
        for suffix in DEFAULT_DENIED_SUFFIXES:
            if lower_path.endswith(suffix):
                findings.append(
                    _finding(
                        path=normalized_path,
                        reason="denied_binary_suffix",
                        rule=suffix,
                    )
                )
                break

    return ProjectDirectorSandboxPathPolicyResult(
        allowed=not findings,
        path=path,
        normalized_path=normalized_path,
        findings=findings,
    )


def _normalize_prefix(prefix: str) -> str | None:
    normalized = normalize_candidate_path(prefix.rstrip("/") + "/placeholder")
    if normalized is None:
        return None
    return normalized.removesuffix("placeholder")


def _matches_any_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(_matches_prefix(path, prefix) for prefix in prefixes)


def _matches_prefix(path: str, prefix: str) -> bool:
    normalized_prefix = prefix.rstrip("/")
    return path == normalized_prefix or path.startswith(normalized_prefix + "/")


def _finding(
    *,
    path: str,
    reason: str,
    rule: str,
) -> ProjectDirectorSandboxPathPolicyFinding:
    return ProjectDirectorSandboxPathPolicyFinding(path=path, reason=reason, rule=rule)


__all__ = (
    "DEFAULT_ALLOWED_PATH_PREFIXES",
    "DEFAULT_DENIED_EXACT_NAMES",
    "DEFAULT_DENIED_LOCKFILES",
    "DEFAULT_DENIED_PATH_PREFIXES",
    "DEFAULT_DENIED_SUBSTRINGS",
    "DEFAULT_DENIED_SUFFIXES",
    "ProjectDirectorSandboxPathPolicyFinding",
    "ProjectDirectorSandboxPathPolicyResult",
    "SandboxFileOperationType",
    "check_sandbox_path_policy",
    "normalize_candidate_path",
)
