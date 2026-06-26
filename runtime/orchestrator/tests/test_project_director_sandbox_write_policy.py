"""Path policy tests for P20 sandbox write policy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.project_director_sandbox_write_policy import (
    ProjectDirectorSandboxPathPolicyResult,
    check_sandbox_path_policy,
    normalize_candidate_path,
)


# ── A. normalize_candidate_path accepts normal relative path ──────────


def test_normalize_accepts_normal_relative_path() -> None:
    assert normalize_candidate_path("runtime/orchestrator/app/domain/foo.py") == "runtime/orchestrator/app/domain/foo.py"


# ── B. normalize_candidate_path normalizes backslash and leading ./ ───


def test_normalize_normalizes_backslash_and_leading_dot_slash() -> None:
    assert normalize_candidate_path("./runtime\\orchestrator\\app\\domain\\foo.py") == "runtime/orchestrator/app/domain/foo.py"


# ── C. normalize_candidate_path rejects ───────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute/path.py",
        "../escape.py",
        "runtime/../escape.py",
        "runtime//foo.py",
        "./../escape.py",
        ".",
        "..",
    ],
)
def test_normalize_rejects_invalid_paths(path: str) -> None:
    assert normalize_candidate_path(path) is None


# ── D. default allowlist accepts ──────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "runtime/orchestrator/app/domain/foo.py",
        "runtime/orchestrator/tests/test_foo.py",
        "runtime/orchestrator/scripts/foo.py",
        "docs/product/ai-project-director/foo.md",
    ],
)
def test_default_allowlist_accepts(path: str) -> None:
    result = check_sandbox_path_policy(path)
    assert result.allowed is True, f"Expected allowed for {path}, got findings: {result.findings}"


# ── E. non-allowlisted path blocked ───────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "random/foo.py",
    ],
)
def test_non_allowlisted_path_blocked(path: str) -> None:
    result = check_sandbox_path_policy(path)
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "path_not_in_allowlist" in reasons


# ── F. denied prefixes blocked ────────────────────────────────────────


def test_denied_prefix_git_config_blocked() -> None:
    result = check_sandbox_path_policy(".git/config")
    assert result.allowed is False


def test_denied_prefix_node_modules_blocked() -> None:
    result = check_sandbox_path_policy("node_modules/pkg/index.js")
    assert result.allowed is False


def test_denied_prefix_dist_blocked() -> None:
    result = check_sandbox_path_policy("dist/app.js")
    assert result.allowed is False


def test_denied_prefix_build_blocked() -> None:
    result = check_sandbox_path_policy("build/app.js")
    assert result.allowed is False


def test_denied_prefix_docs_superpowers_blocked() -> None:
    result = check_sandbox_path_policy("docs/superpowers/plans/foo.md")
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "docs_superpowers_forbidden" in reasons


# ── G. .git embedded path blocked ────────────────────────────────────


def test_git_embedded_path_blocked() -> None:
    result = check_sandbox_path_policy("runtime/orchestrator/app/.git/config")
    assert result.allowed is False


# ── H. .env and env variants blocked ─────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "runtime/orchestrator/app/.env",
        "runtime/orchestrator/app/.env.local",
        "runtime/orchestrator/app/.env.production",
    ],
)
def test_env_variants_blocked(path: str) -> None:
    result = check_sandbox_path_policy(path)
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "denied_exact_name" in reasons


# ── I. sensitive substrings blocked ───────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "runtime/orchestrator/app/secret_config.py",
        "runtime/orchestrator/app/private_key.py",
        "runtime/orchestrator/app/api_key_store.py",
        "runtime/orchestrator/app/token_cache.py",
        "runtime/orchestrator/app/credentials.py",
    ],
)
def test_sensitive_substrings_blocked(path: str) -> None:
    result = check_sandbox_path_policy(path)
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "denied_sensitive_substring" in reasons


# ── J. lockfiles blocked by default ──────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "uv.lock",
        "poetry.lock",
        "Cargo.lock",
        "Gemfile.lock",
    ],
)
def test_lockfiles_blocked_by_default(path: str) -> None:
    result = check_sandbox_path_policy(path)
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "denied_lockfile" in reasons


# ── K. lockfiles allowed when allow_lockfile=true ────────────────────


def test_lockfile_allowed_when_flag_set() -> None:
    result = check_sandbox_path_policy(
        "runtime/orchestrator/uv.lock",
        allow_lockfile=True,
        allowed_path_prefixes=["runtime/orchestrator/"],
    )
    assert result.allowed is True


# ── L. binary suffixes blocked by default ────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "runtime/orchestrator/app/cert.pem",
        "runtime/orchestrator/app/server.key",
        "runtime/orchestrator/app/cert.p12",
        "runtime/orchestrator/app/cert.pfx",
        "runtime/orchestrator/app/cert.crt",
        "runtime/orchestrator/app/cert.cer",
        "runtime/orchestrator/app/cert.der",
        "runtime/orchestrator/app/data.bin",
        "runtime/orchestrator/app/app.exe",
        "runtime/orchestrator/app/lib.dll",
        "runtime/orchestrator/app/lib.so",
        "runtime/orchestrator/app/lib.dylib",
        "runtime/orchestrator/app/image.png",
        "runtime/orchestrator/app/photo.jpg",
        "runtime/orchestrator/app/photo.jpeg",
        "runtime/orchestrator/app/anim.gif",
        "runtime/orchestrator/app/cover.webp",
        "runtime/orchestrator/app/archive.zip",
        "runtime/orchestrator/app/archive.tar",
        "runtime/orchestrator/app/archive.gz",
        "runtime/orchestrator/app/archive.7z",
    ],
)
def test_binary_suffixes_blocked_by_default(path: str) -> None:
    result = check_sandbox_path_policy(path)
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "denied_binary_suffix" in reasons


# ── M. binary suffix allowed when allow_binary=true ──────────────────


def test_binary_allowed_when_flag_set() -> None:
    result = check_sandbox_path_policy("runtime/orchestrator/app/image.png", allow_binary=True)
    assert result.allowed is True


# ── N. apps/web blocked by default ───────────────────────────────────


def test_apps_web_blocked_by_default() -> None:
    result = check_sandbox_path_policy("apps/web/src/foo.tsx")
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "frontend_not_explicitly_allowed" in reasons


# ── O. apps/web allowed only with explicit allow_frontend + prefix ───


def test_apps_web_blocked_without_allow_frontend() -> None:
    result = check_sandbox_path_policy(
        "apps/web/src/foo.tsx",
        allowed_path_prefixes=["apps/web/"],
        allow_frontend=False,
    )
    assert result.allowed is False


def test_apps_web_blocked_without_prefix() -> None:
    result = check_sandbox_path_policy(
        "apps/web/src/foo.tsx",
        allow_frontend=True,
    )
    assert result.allowed is False


def test_apps_web_allowed_with_both_flags() -> None:
    result = check_sandbox_path_policy(
        "apps/web/src/foo.tsx",
        allowed_path_prefixes=["apps/web/"],
        allow_frontend=True,
    )
    assert result.allowed is True


# ── P. safety result validators reject dangerous true flags ───────────


@pytest.mark.parametrize(
    "field_name",
    [
        "product_runtime_git_write_allowed",
        "main_worktree_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "actual_patch_applied",
        "git_write_performed",
    ],
)
def test_safety_result_validator_rejects_true_flags(field_name: str) -> None:
    with pytest.raises(ValidationError, match="must remain false"):
        ProjectDirectorSandboxPathPolicyResult(
            allowed=True,
            path="test.py",
            normalized_path="test.py",
            **{field_name: True},
        )


# ── Q. unsupported operation behavior ────────────────────────────────


def test_unsupported_operation_blocked_via_check_function() -> None:
    result = check_sandbox_path_policy(
        "runtime/orchestrator/app/domain/foo.py",
        operation="delete",  # type: ignore[arg-type]
    )
    assert result.allowed is False
    reasons = [f.reason for f in result.findings]
    assert "unsupported_operation" in reasons
