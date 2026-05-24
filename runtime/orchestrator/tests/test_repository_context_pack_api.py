"""API coverage for project repository CodeContextPack generation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.db import get_db_session
from app.core.db_tables import ORMBase
from app.domain.project import Project
from app.domain.repository_workspace import RepositoryWorkspace
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)


@pytest.fixture()
def sqlite_session_factory(tmp_path):
    db_path = tmp_path / "orchestrator-test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    ORMBase.metadata.create_all(bind=engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def client(sqlite_session_factory):
    app = FastAPI()
    app.include_router(api_router)

    def override_get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_project_with_optional_workspace(
    sqlite_session_factory,
    *,
    repository_root_path: Path | None = None,
    allowed_workspace_root: Path | None = None,
) -> str:
    session = sqlite_session_factory()
    try:
        project = Project(
            name="Context Pack API Project",
            summary="Project used by context-pack API tests.",
        )
        created_project = ProjectRepository(session).create(project)

        if repository_root_path is not None:
            RepositoryWorkspaceRepository(session).upsert(
                RepositoryWorkspace(
                    project_id=created_project.id,
                    root_path=str(repository_root_path.resolve()),
                    display_name="context-pack-fixture",
                    default_base_branch="main",
                    allowed_workspace_root=str(
                        (allowed_workspace_root or repository_root_path).resolve()
                    ),
                )
            )

        return str(created_project.id)
    finally:
        session.close()


def test_build_project_context_pack_success(
    client,
    sqlite_session_factory,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    readme_file = repo_root / "README.md"
    readme_file.parent.mkdir(parents=True)
    readme_file.write_text(
        "# Context Pack Fixture\n\n"
        "This README validates multi-file context-pack selection.\n",
        encoding="utf-8",
    )
    source_file = repo_root / "src" / "service.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "def build_context_pack():\n"
        "    return 'context pack ready'\n",
        encoding="utf-8",
    )
    project_id = _create_project_with_optional_workspace(
        sqlite_session_factory,
        repository_root_path=repo_root,
        allowed_workspace_root=tmp_path,
    )

    response = client.post(
        f"/repositories/projects/{project_id}/context-pack",
        json={
            "selected_paths": ["README.md", "src/service.py"],
            "selection_reasons_by_path": {
                "README.md": ["explicit README selection"],
                "src/service.py": ["explicit test selection"]
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["repository_root_path"] == str(repo_root.resolve())
    assert data["selected_paths"] == ["README.md", "src/service.py"]
    assert data["included_file_count"] == 2
    assert [entry["relative_path"] for entry in data["entries"]] == [
        "README.md",
        "src/service.py",
    ]
    assert "Context Pack Fixture" in data["entries"][0]["excerpt"]
    assert "build_context_pack" in data["entries"][1]["excerpt"]
    assert data["entries"][0]["match_reasons"] == ["explicit README selection"]
    assert data["entries"][1]["match_reasons"] == ["explicit test selection"]


def test_build_project_context_pack_marks_truncated_when_total_budget_is_exhausted(
    client,
    sqlite_session_factory,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    first_file = repo_root / "README.md"
    first_file.parent.mkdir(parents=True)
    first_file.write_text("A" * 600, encoding="utf-8")
    second_file = repo_root / "src" / "service.py"
    second_file.parent.mkdir(parents=True)
    second_file.write_text("def later():\n    return 'omitted'\n", encoding="utf-8")
    project_id = _create_project_with_optional_workspace(
        sqlite_session_factory,
        repository_root_path=repo_root,
        allowed_workspace_root=tmp_path,
    )

    response = client.post(
        f"/repositories/projects/{project_id}/context-pack",
        json={
            "selected_paths": ["README.md", "src/service.py"],
            "max_total_bytes": 512,
            "max_bytes_per_file": 512,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["truncated"] is True
    assert data["included_file_count"] == 1
    assert data["total_included_bytes"] <= 512
    assert data["omitted_paths"] == ["src/service.py"]
    assert [entry["relative_path"] for entry in data["entries"]] == ["README.md"]
    assert data["entries"][0]["truncated"] is True


def test_build_project_context_pack_rejects_path_escape_with_422(
    client,
    sqlite_session_factory,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
    project_id = _create_project_with_optional_workspace(
        sqlite_session_factory,
        repository_root_path=repo_root,
        allowed_workspace_root=tmp_path,
    )

    response = client.post(
        f"/repositories/projects/{project_id}/context-pack",
        json={"selected_paths": ["../outside.txt"]},
    )

    assert response.status_code == 422
    assert "escapes the repository root" in response.json()["detail"]


def test_build_project_context_pack_rejects_absolute_path_escape_with_422(
    client,
    sqlite_session_factory,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")
    project_id = _create_project_with_optional_workspace(
        sqlite_session_factory,
        repository_root_path=repo_root,
        allowed_workspace_root=tmp_path,
    )

    response = client.post(
        f"/repositories/projects/{project_id}/context-pack",
        json={"selected_paths": [str(outside_file.resolve())]},
    )

    assert response.status_code == 422
    assert "escapes the repository root" in response.json()["detail"]


@pytest.mark.parametrize(
    "selected_path",
    [
        ".git/config",
        "node_modules/ignored.js",
        "__pycache__/ignored.py",
        ".venv/ignored.py",
        "dist/ignored.js",
        "build/ignored.js",
    ],
)
def test_build_project_context_pack_rejects_default_ignored_directory_files_with_422(
    client,
    sqlite_session_factory,
    tmp_path,
    selected_path,
):
    repo_root = tmp_path / "repo"
    ignored_file = repo_root / selected_path
    ignored_file.parent.mkdir(parents=True, exist_ok=True)
    ignored_file.write_text("ignored but present", encoding="utf-8")
    project_id = _create_project_with_optional_workspace(
        sqlite_session_factory,
        repository_root_path=repo_root,
        allowed_workspace_root=tmp_path,
    )

    response = client.post(
        f"/repositories/projects/{project_id}/context-pack",
        json={"selected_paths": [selected_path]},
    )

    assert response.status_code == 422
    assert "ignored repository directory" in response.json()["detail"]


def test_build_project_context_pack_without_bound_repository_returns_404(
    client,
    sqlite_session_factory,
):
    project_id = _create_project_with_optional_workspace(sqlite_session_factory)

    response = client.post(
        f"/repositories/projects/{project_id}/context-pack",
        json={"selected_paths": ["src/service.py"]},
    )

    assert response.status_code == 404
    assert "Repository workspace not found" in response.json()["detail"]
