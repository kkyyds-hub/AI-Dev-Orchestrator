"""Readonly repository evidence collection for P10 Project Director work."""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path

from app.domain.project_director_evidence_pack import (
    ProjectDirectorEvidenceRef,
    ProjectDirectorRepoEvidencePack,
)


class ProjectDirectorRepoEvidenceService:
    """Build a bounded, readonly evidence pack from repository files."""

    _RELATED_CANDIDATES: tuple[tuple[str, tuple[str, ...], str], ...] = (
        (
            "runtime/orchestrator/README.md",
            ("Project Director", "P9-RUN-A", "product runtime Git write"),
            "backend runtime baseline and P9 safety notes",
        ),
        (
            "runtime/orchestrator/scripts/p9_run_backend_runnable_smoke.py",
            ("product_runtime_git_write_allowed", "frontend_required"),
            "P9 runnable smoke safety flags",
        ),
        (
            "runtime/orchestrator/app/api/routes/project_director.py",
            ("ProjectDirector", "read-only", "Plan"),
            "Project Director route surface",
        ),
        (
            "runtime/orchestrator/app/services/project_director_context_builder_service.py",
            ("read-only", "safety_boundary", "不写仓库"),
            "Project Director readonly context package",
        ),
        (
            "runtime/orchestrator/app/services/project_director_plan_service.py",
            ("source_detail", "不写仓库", "Worker"),
            "Project Director review-only plan generation",
        ),
        (
            "runtime/orchestrator/app/services/project_director_output_guardrails.py",
            ("execution_claim", "git", "worker"),
            "provider output execution-claim guardrails",
        ),
        (
            "runtime/orchestrator/app/domain/project_director_plan_version.py",
            ("ProposedTask", "AgentTeamSuggestion", "source_detail"),
            "plan draft domain model",
        ),
        (
            "runtime/orchestrator/app/domain/agent_session.py",
            ("AgentSession", "WorkspaceType", "READ_ONLY"),
            "agent session role and workspace vocabulary",
        ),
        (
            "runtime/orchestrator/app/repositories/project_director_plan_version_repository.py",
            ("ProjectDirectorPlanVersion", "list_by_session_id"),
            "plan version readback repository",
        ),
        (
            "runtime/orchestrator/tests/test_project_director_plan_versions.py",
            ("ProjectDirectorPlanService", "source_detail"),
            "existing targeted Project Director plan tests",
        ),
    )

    _FORBIDDEN_PATHS = [
        "apps/web/**",
        "docs/superpowers/**",
        "runtime/orchestrator/app/external_executors/**",
        "product runtime Git write surfaces",
    ]

    _IMPACT_PATHS = [
        "runtime/orchestrator/app/domain/project_director_evidence_pack.py",
        "runtime/orchestrator/app/services/project_director_repo_evidence_service.py",
        "runtime/orchestrator/tests/test_project_director_repo_evidence_pack.py",
    ]

    def __init__(self, *, repo_root: Path) -> None:
        self._repo_root = repo_root.resolve()

    def build_evidence_pack(self, *, goal_text: str) -> ProjectDirectorRepoEvidencePack:
        origin_main_commit = self._read_origin_main_commit()
        evidence_refs: list[ProjectDirectorEvidenceRef] = []
        related_files: list[str] = []
        missing_candidates: list[str] = []

        for relative_path, terms, reason in self._RELATED_CANDIDATES:
            path = self._repo_root / relative_path
            if not path.is_file():
                missing_candidates.append(relative_path)
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            matched_terms = [term for term in terms if term.lower() in text.lower()]
            if matched_terms:
                related_files.append(relative_path)
                evidence_refs.append(
                    ProjectDirectorEvidenceRef(
                        ref_id=f"repo:{len(evidence_refs) + 1}",
                        relative_path=relative_path,
                        reason=reason,
                        matched_terms=matched_terms,
                    )
                )

        pack_seed = "|".join([origin_main_commit, goal_text.strip(), *related_files])
        evidence_pack_id = f"p10-a-{sha1(pack_seed.encode('utf-8')).hexdigest()[:12]}"

        return ProjectDirectorRepoEvidencePack(
            origin_main_commit=origin_main_commit,
            evidence_pack_id=evidence_pack_id,
            repo_root=str(self._repo_root),
            related_files=related_files,
            impact_paths=list(self._IMPACT_PATHS),
            forbidden_paths=list(self._FORBIDDEN_PATHS),
            suggested_tests=[
                "runtime/orchestrator/tests/test_project_director_repo_evidence_pack.py"
            ],
            risks=[
                "Evidence can become stale if origin/main moves after pack creation.",
                "Readonly repo evidence is not execution approval.",
                "Agent assignment must not imply product runtime Git write permission.",
            ],
            unknowns=[
                "No live long-running Codex or Claude lifecycle is proven by this pack.",
                "The pack does not inspect frontend because frontend_required is false.",
                *[
                    f"Expected evidence file missing: {path}"
                    for path in missing_candidates
                ],
            ],
            evidence_refs=evidence_refs,
            source_detail={
                "inspection_mode": "readonly_path_and_keyword_scan",
                "candidate_count": len(self._RELATED_CANDIDATES),
                "matched_file_count": len(related_files),
                "goal_text_present": bool(goal_text.strip()),
                "writes_repository": False,
                "starts_executor": False,
            },
            product_runtime_git_write_allowed=False,
            frontend_required=False,
        )

    def _read_origin_main_commit(self) -> str:
        git_dir = self._resolve_git_dir()
        loose_ref = git_dir / "refs" / "remotes" / "origin" / "main"
        if loose_ref.is_file():
            value = loose_ref.read_text(encoding="utf-8").strip()
            if value:
                return value

        packed_refs = git_dir / "packed-refs"
        if packed_refs.is_file():
            for line in packed_refs.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split()
                if len(parts) == 2 and parts[1] == "refs/remotes/origin/main":
                    return parts[0]

        raise RuntimeError("origin_main_commit_unavailable")

    def _resolve_git_dir(self) -> Path:
        dot_git = self._repo_root / ".git"
        if dot_git.is_dir():
            return dot_git
        if dot_git.is_file():
            content = dot_git.read_text(encoding="utf-8").strip()
            prefix = "gitdir:"
            if content.startswith(prefix):
                git_path = Path(content[len(prefix) :].strip())
                if not git_path.is_absolute():
                    git_path = self._repo_root / git_path
                return git_path.resolve()
        raise RuntimeError("git_dir_unavailable")
