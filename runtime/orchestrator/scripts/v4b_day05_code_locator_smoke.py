"""V4-B Day05 smoke checks for repository file location and CodeContextPack flows."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SMOKE_ROOT = RUNTIME_ROOT / "tmp" / "v4-day05-code-locator-smoke"
SMOKE_RUNTIME_DATA_DIR = SMOKE_ROOT / "runtime-data"
SMOKE_ALLOWED_WORKSPACE_ROOT = SMOKE_ROOT / "allowed-workspaces"
SMOKE_REPOSITORY_ROOT = SMOKE_ALLOWED_WORKSPACE_ROOT / "day05-code-locator"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _remove_readonly(func: Any, path: str, _: Any) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _run_git(*args: str) -> str:
    completed_process = subprocess.run(
        ["git", *args],
        cwd=SMOKE_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: {completed_process.stderr or completed_process.stdout}"
        )

    return (completed_process.stdout or "").strip()


def _prepare_env() -> None:
    if SMOKE_ROOT.exists():
        shutil.rmtree(SMOKE_ROOT, onerror=_remove_readonly)

    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "services"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "api"
        / "routes"
    ).mkdir(parents=True, exist_ok=True)
    (
        SMOKE_REPOSITORY_ROOT
        / "apps"
        / "web"
        / "src"
        / "features"
        / "repositories"
        / "components"
    ).mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "docs" / "notes").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "fake").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / "dist").mkdir(parents=True, exist_ok=True)
    (SMOKE_REPOSITORY_ROOT / ".venv").mkdir(parents=True, exist_ok=True)

    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "services"
        / "codebase_locator_service.py"
    ).write_text(
        "\n".join(
            [
                '"""Code locator smoke target."""',
                "",
                "class CodebaseLocatorService:",
                "    def locate_files(self):",
                "        return ['repositories.py', 'FileLocatorPanel.tsx']",
                "",
                "    def build_candidate_summary(self):",
                "        return 'candidate files for code context pack'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "services"
        / "context_builder_service.py"
    ).write_text(
        "\n".join(
            [
                '"""Context builder smoke target."""',
                "",
                "def build_code_context_pack(selected_paths):",
                "    return {'selected_paths': selected_paths, 'kind': 'CodeContextPack'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "runtime"
        / "orchestrator"
        / "app"
        / "api"
        / "routes"
        / "repositories.py"
    ).write_text(
        "\n".join(
            [
                '"""Repository routes smoke target."""',
                "",
                "def register_locator_routes(router):",
                "    router.append('/repositories/projects/{project_id}/file-locator/search')",
                "    router.append('/repositories/projects/{project_id}/context-pack')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (
        SMOKE_REPOSITORY_ROOT
        / "apps"
        / "web"
        / "src"
        / "features"
        / "repositories"
        / "components"
        / "FileLocatorPanel.tsx"
    ).write_text(
        "\n".join(
            [
                "export function FileLocatorPanel() {",
                "  return <div>CodeContextPack candidate viewer</div>;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "docs" / "notes" / "day05-context-pack.md").write_text(
        "# Day05\n\nGenerate a minimal CodeContextPack from selected files.\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "node_modules" / "fake" / "ignored.js").write_text(
        "console.log('ignore me');\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / "dist" / "bundle.js").write_text(
        "console.log('build artifact');\n",
        encoding="utf-8",
    )
    (SMOKE_REPOSITORY_ROOT / ".venv" / "ignored.py").write_text(
        "print('ignore me')\n",
        encoding="utf-8",
    )

    _run_git("init")
    _run_git("checkout", "-b", "main")
    _run_git("config", "user.email", "EMAIL_REDACTED")
    _run_git("config", "user.name", "Smoke Bot")
    _run_git("add", ".")
    _run_git("commit", "-m", "init day05 smoke repo")

    os.environ["RUNTIME_DATA_DIR"] = str(SMOKE_RUNTIME_DATA_DIR)
    os.environ["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(SMOKE_ALLOWED_WORKSPACE_ROOT)
    os.environ["DAILY_BUDGET_USD"] = "0.05"
    os.environ["SESSION_BUDGET_USD"] = "0.20"
    os.environ["MAX_TASK_RETRIES"] = "2"
    os.environ["MAX_CONCURRENT_WORKERS"] = "2"


def _request_json(
    client: Any,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> Any:
    response = client.request(method, path, json=json_body)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected {expected_status}, got {response.status_code}: {response.text}"
        )

    return response.json()


def main() -> None:
    _prepare_env()

    from fastapi.testclient import TestClient

    from app.main import create_application

    app = create_application()

    with TestClient(app) as client:
        project = _request_json(
            client,
            "POST",
            "/projects",
            expected_status=201,
            json_body={
                "name": "Day05 Code Locator Project",
                "summary": "Exercise candidate file location and bounded code context packs.",
            },
        )
        _request_json(
            client,
            "PUT",
            f"/repositories/projects/{project['id']}",
            expected_status=200,
            json_body={
                "root_path": str(SMOKE_REPOSITORY_ROOT),
                "display_name": "Day05 Smoke Repo",
                "default_base_branch": "main",
            },
        )
        task = _request_json(
            client,
            "POST",
            "/tasks",
            expected_status=201,
            json_body={
                "project_id": project["id"],
                "title": "Add file locator panel and code context pack",
                "input_summary": (
                    "Locate repositories.py, codebase_locator_service.py, "
                    "context_builder_service.py and FileLocatorPanel.tsx."
                ),
                "acceptance_criteria": [
                    "Can produce candidate files by task keywords",
                    "Can build a bounded CodeContextPack",
                ],
            },
        )

        keyword_search = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "task_id": task["id"],
                "limit": 10,
            },
        )
        candidate_paths = {
            candidate["relative_path"] for candidate in keyword_search["candidates"]
        }
        _assert(
            "runtime/orchestrator/app/services/codebase_locator_service.py"
            in candidate_paths,
            "Task-based keyword search should locate the backend locator service.",
        )
        _assert(
            "runtime/orchestrator/app/services/context_builder_service.py"
            in candidate_paths,
            "Task-based keyword search should locate the context builder service.",
        )
        _assert(
            "apps/web/src/features/repositories/components/FileLocatorPanel.tsx"
            in candidate_paths,
            "Task-based keyword search should locate the frontend panel.",
        )
        _assert(
            not any(
                path.startswith("node_modules/")
                or path.startswith("dist/")
                or path.startswith(".venv/")
                for path in candidate_paths
            ),
            "Noise directories must stay excluded from Day05 candidate results.",
        )

        path_prefix_search = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "path_prefixes": [
                    "apps/web/src/features/repositories/components",
                ],
                "limit": 5,
            },
        )
        _assert(
            path_prefix_search["candidates"][0]["relative_path"]
            == "apps/web/src/features/repositories/components/FileLocatorPanel.tsx",
            "Path-prefix search should prioritize the requested frontend component path.",
        )

        file_type_search = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "module_names": ["services"],
                "file_types": ["py"],
                "limit": 10,
            },
        )
        _assert(
            all(candidate["file_type"] == "py" for candidate in file_type_search["candidates"]),
            "File-type filters should keep only requested source-file types.",
        )
        _assert(
            any(
                candidate["relative_path"]
                == "runtime/orchestrator/app/services/codebase_locator_service.py"
                for candidate in file_type_search["candidates"]
            ),
            "Module-name + file-type search should still locate the backend service file.",
        )

        planning_search = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/file-locator/search",
            expected_status=200,
            json_body={
                "task_query": "Need the tsx panel for candidate viewer",
                "file_types": ["tsx"],
                "limit": 5,
            },
        )
        _assert(
            planning_search["candidates"][0]["relative_path"]
            == "apps/web/src/features/repositories/components/FileLocatorPanel.tsx",
            "Planning-query search should support non-task Day05 entry signals.",
        )

        context_pack = _request_json(
            client,
            "POST",
            f"/repositories/projects/{project['id']}/context-pack",
            expected_status=200,
            json_body={
                "task_id": task["id"],
                "selected_paths": [
                    "runtime/orchestrator/app/services/codebase_locator_service.py",
                    "apps/web/src/features/repositories/components/FileLocatorPanel.tsx",
                    "runtime/orchestrator/app/api/routes/repositories.py",
                ],
                "max_total_bytes": 620,
                "max_bytes_per_file": 300,
            },
        )
        _assert(
            context_pack["included_file_count"] >= 2,
            "CodeContextPack should include at least the requested high-priority files within budget.",
        )
        _assert(
            context_pack["total_included_bytes"] <= context_pack["max_total_bytes"],
            "CodeContextPack must respect the configured total byte budget.",
        )
        _assert(
            context_pack["truncated"] is True,
            "Small budgets should surface a truncated Day05 CodeContextPack.",
        )
        _assert(
            any(
                entry["relative_path"]
                == "runtime/orchestrator/app/services/codebase_locator_service.py"
                for entry in context_pack["entries"]
            ),
            "Selected files should appear in the generated CodeContextPack entries.",
        )

    print("V4 Day05 code locator smoke passed.")


if __name__ == "__main__":
    main()
