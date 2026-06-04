"""Dry-run worktree planning services.

P1-C deliberately performs pure computation only.  It does not call git,
create directories, create branches, or persist AgentSession workspace state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
from uuid import UUID

from app.domain.agent_session import AgentSession
from app.domain.repository_workspace import RepositoryWorkspace
from app.domain.worktree_plan import WorktreePlan
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository


_BRANCH_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,198}[A-Za-z0-9]$")
_SAFE_TOKEN_PATTERN = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True, slots=True)
class WorktreeGuardResult:
    """Result from pure path/branch validation."""

    safe: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BranchNamePolicy:
    """Generate predictable, git-safe per-session branch names without git calls."""

    max_length = 50

    def generate(self, *, project_prefix: str, session_id: UUID) -> str:
        """Return a branch name such as ``session/my-proj-a1b2c3d4``."""

        normalized_prefix = self._normalize_project_prefix(project_prefix)
        session_short = session_id.hex[:8]
        branch_name = f"session/{normalized_prefix}-{session_short}"
        if len(branch_name) <= self.max_length:
            return branch_name

        suffix = f"-{session_short}"
        prefix_budget = self.max_length - len("session/") - len(suffix)
        return f"session/{normalized_prefix[:prefix_budget].rstrip('-')}{suffix}"

    def validate(self, branch_name: str) -> bool:
        """Return whether one branch name is safe for the future create step."""

        if not branch_name or len(branch_name) > 200:
            return False
        if branch_name.startswith("/") or branch_name.endswith("/"):
            return False
        if any(part in {"", ".", ".."} for part in branch_name.split("/")):
            return False
        if branch_name.endswith(".lock") or "@{" in branch_name:
            return False
        if ".." in branch_name or "\\" in branch_name:
            return False
        return bool(_BRANCH_NAME_PATTERN.fullmatch(branch_name))

    @staticmethod
    def _normalize_project_prefix(project_prefix: str) -> str:
        """Normalize free-form project text into a stable branch token."""

        normalized = project_prefix.strip().lower()
        normalized = _SAFE_TOKEN_PATTERN.sub("-", normalized)
        normalized = normalized.strip("-")
        return normalized or "project"


class WorktreeGuardService:
    """Pure guard checks for planned worktree path and branch name."""

    def __init__(self, *, branch_name_policy: BranchNamePolicy | None = None) -> None:
        self.branch_name_policy = branch_name_policy or BranchNamePolicy()

    def validate_branch_name(self, branch_name: str) -> WorktreeGuardResult:
        """Validate future branch name without querying local git refs."""

        if self.branch_name_policy.validate(branch_name):
            return WorktreeGuardResult(safe=True)
        return WorktreeGuardResult(
            safe=False,
            blockers=[f"invalid branch name: {branch_name}"],
        )

    def validate_path(
        self,
        *,
        worktree_path: str,
        allowed_root: str,
        repository_root_path: str,
    ) -> WorktreeGuardResult:
        """Validate planned worktree path stays isolated and non-overwriting."""

        blockers: list[str] = []
        warnings: list[str] = []
        planned_path = Path(worktree_path).expanduser()
        allowed_root_path = Path(allowed_root).expanduser()
        repository_root = Path(repository_root_path).expanduser()

        if not planned_path.is_absolute():
            blockers.append("worktree path must be absolute")
        if not allowed_root_path.is_absolute():
            blockers.append("allowed workspace root must be absolute")
        if not repository_root.is_absolute():
            blockers.append("repository root path must be absolute")
        if blockers:
            return WorktreeGuardResult(safe=False, blockers=blockers, warnings=warnings)

        planned_resolved = planned_path.resolve(strict=False)
        allowed_resolved = allowed_root_path.resolve(strict=False)
        repository_resolved = repository_root.resolve(strict=False)

        if planned_resolved == allowed_resolved:
            blockers.append("worktree path cannot equal allowed workspace root")
        if not self._is_within(planned_resolved, allowed_resolved):
            blockers.append("worktree path is outside allowed workspace root")
        if planned_resolved == repository_resolved or self._is_within(
            planned_resolved,
            repository_resolved,
        ):
            blockers.append("worktree path cannot be inside the source repository")
        if self._is_within(repository_resolved, planned_resolved):
            blockers.append("worktree path cannot contain the source repository")
        if planned_resolved.exists():
            if planned_resolved.is_dir():
                try:
                    is_empty_dir = not any(planned_resolved.iterdir())
                except OSError:
                    is_empty_dir = False
                if is_empty_dir:
                    warnings.append("worktree path already exists as an empty directory")
                else:
                    blockers.append("worktree path already exists and is not empty")
            else:
                blockers.append("worktree path already exists and is not a directory")

        return WorktreeGuardResult(
            safe=len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
        )

    @staticmethod
    def _is_within(child: Path, parent: Path) -> bool:
        """Return True when ``child`` is inside ``parent``."""

        try:
            child.relative_to(parent)
        except ValueError:
            return False
        return True


class WorktreePlanService:
    """Generate dry-run worktree plans without repository writes."""

    def __init__(
        self,
        *,
        agent_session_repository: AgentSessionRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        branch_name_policy: BranchNamePolicy | None = None,
        guard_service: WorktreeGuardService | None = None,
    ) -> None:
        self.agent_session_repository = agent_session_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.branch_name_policy = branch_name_policy or BranchNamePolicy()
        self.guard_service = guard_service or WorktreeGuardService(
            branch_name_policy=self.branch_name_policy,
        )

    def build_plan(self, *, agent_session_id: UUID) -> WorktreePlan:
        """Build one descriptive future worktree plan for an AgentSession."""

        session = self.agent_session_repository.get_by_id(agent_session_id)
        if session is None:
            raise ValueError(f"Agent session not found: {agent_session_id}")

        repository_workspace = self.repository_workspace_repository.get_by_project_id(
            session.project_id
        )
        blockers: list[str] = []
        warnings: list[str] = []

        if repository_workspace is None:
            blockers.append("repository workspace is not bound for this project")
            return self._build_plan_payload(
                session=session,
                repository_workspace=None,
                branch_name=None,
                worktree_path=None,
                blockers=blockers,
                warnings=warnings,
            )

        branch_name = self.branch_name_policy.generate(
            project_prefix=self._project_prefix(session.project_id),
            session_id=session.id,
        )
        branch_result = self.guard_service.validate_branch_name(branch_name)
        blockers.extend(branch_result.blockers)
        warnings.extend(branch_result.warnings)

        if not Path(repository_workspace.root_path).exists():
            blockers.append("repository root path does not exist")
        elif not (Path(repository_workspace.root_path) / ".git").exists():
            blockers.append("repository root path does not contain .git")

        worktree_path = self._planned_worktree_path(
            repository_workspace=repository_workspace,
            session=session,
        )
        path_result = self.guard_service.validate_path(
            worktree_path=worktree_path,
            allowed_root=repository_workspace.allowed_workspace_root,
            repository_root_path=repository_workspace.root_path,
        )
        blockers.extend(path_result.blockers)
        warnings.extend(path_result.warnings)

        if session.branch_name is not None:
            warnings.append(
                "agent session already has a branch_name; dry-run plan will not mutate it"
            )
        if session.workspace_path is not None:
            warnings.append(
                "agent session already has a workspace_path; dry-run plan will not mutate it"
            )

        return self._build_plan_payload(
            session=session,
            repository_workspace=repository_workspace,
            branch_name=branch_name,
            worktree_path=worktree_path,
            blockers=blockers,
            warnings=warnings,
        )

    def _build_plan_payload(
        self,
        *,
        session: AgentSession,
        repository_workspace: RepositoryWorkspace | None,
        branch_name: str | None,
        worktree_path: str | None,
        blockers: list[str],
        warnings: list[str],
    ) -> WorktreePlan:
        """Assemble the immutable plan response."""

        base_branch = (
            repository_workspace.default_base_branch
            if repository_workspace is not None
            else None
        )
        commands: list[str] = []
        if repository_workspace is not None and branch_name is not None and worktree_path:
            commands = [
                (
                    "git worktree add "
                    f"{shlex.quote(worktree_path)} "
                    f"origin/{shlex.quote(repository_workspace.default_base_branch)}"
                ),
                (
                    f"git -C {shlex.quote(worktree_path)} "
                    f"checkout -b {shlex.quote(branch_name)}"
                ),
            ]

        return WorktreePlan(
            agent_session_id=session.id,
            project_id=session.project_id,
            repository_workspace_id=(
                repository_workspace.id if repository_workspace is not None else None
            ),
            safe=len(blockers) == 0,
            plan_hash=self._compute_plan_hash(
                agent_session_id=session.id,
                project_id=session.project_id,
                repository_workspace_id=(
                    repository_workspace.id
                    if repository_workspace is not None
                    else None
                ),
                worktree_path=worktree_path,
                branch_name=branch_name,
                base_branch=base_branch,
                base_commit_sha=None,
            ),
            worktree_path=worktree_path,
            branch_name=branch_name,
            base_branch=base_branch,
            base_commit_sha=None,
            git_commands_to_run=commands,
            blockers=blockers,
            warnings=warnings,
        )

    @staticmethod
    def _compute_plan_hash(
        *,
        agent_session_id: UUID,
        project_id: UUID,
        repository_workspace_id: UUID | None,
        worktree_path: str | None,
        branch_name: str | None,
        base_branch: str | None,
        base_commit_sha: str | None,
    ) -> str:
        """Return a stable SHA-256 hash for stale-plan detection."""

        payload = {
            "agent_session_id": str(agent_session_id),
            "project_id": str(project_id),
            "repository_workspace_id": (
                str(repository_workspace_id)
                if repository_workspace_id is not None
                else None
            ),
            "worktree_path": worktree_path,
            "branch_name": branch_name,
            "base_branch": base_branch,
            "base_commit_sha": base_commit_sha,
        }
        canonical_payload = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical_payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _project_prefix(project_id: UUID) -> str:
        """Use a stable project-id prefix without loading extra project state."""

        return f"proj-{project_id.hex[:8]}"

    @staticmethod
    def _planned_worktree_path(
        *,
        repository_workspace: RepositoryWorkspace,
        session: AgentSession,
    ) -> str:
        """Compute the future worktree path under the allowed workspace root."""

        return str(
            Path(repository_workspace.allowed_workspace_root)
            / ".aido-worktrees"
            / f"project-{session.project_id.hex[:8]}"
            / f"session-{session.id.hex[:8]}"
        )
