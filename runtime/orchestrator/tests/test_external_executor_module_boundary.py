from __future__ import annotations

from pathlib import Path

from app.external_executors.boundary import (
    ALLOWED_EXTERNAL_EXECUTOR_MODULE_KINDS,
    BOUNDARY_RULES,
    EXTERNAL_EXECUTOR_MODULE_BOUNDARY,
    FORBIDDEN_LEGACY_INTEGRATION_TARGETS,
)


EXTERNAL_EXECUTOR_DIR = Path("app/external_executors")
BOUNDARY_FILE = EXTERNAL_EXECUTOR_DIR / "boundary.py"
ACTUAL_CONTRACT_FILE = EXTERNAL_EXECUTOR_DIR / "actual_contract.py"
ACTUAL_PREFLIGHT_FILE = EXTERNAL_EXECUTOR_DIR / "actual_preflight.py"
ACTUAL_PREVIEW_FILE = EXTERNAL_EXECUTOR_DIR / "actual_preview.py"
ACTUAL_DISABLED_ADAPTER_FILE = EXTERNAL_EXECUTOR_DIR / "actual_disabled_adapter.py"


def _read(path: str) -> str:
    return Path(path).read_text()


def test_external_executor_boundary_package_exists() -> None:
    assert EXTERNAL_EXECUTOR_DIR.is_dir()
    assert (EXTERNAL_EXECUTOR_DIR / "__init__.py").is_file()
    assert BOUNDARY_FILE.is_file()
    assert ACTUAL_CONTRACT_FILE.is_file()
    assert ACTUAL_PREFLIGHT_FILE.is_file()
    assert ACTUAL_PREVIEW_FILE.is_file()
    assert ACTUAL_DISABLED_ADAPTER_FILE.is_file()


def test_boundary_declares_module_kind_split_and_legacy_targets() -> None:
    assert ALLOWED_EXTERNAL_EXECUTOR_MODULE_KINDS == ("fake", "preview", "actual")
    assert FORBIDDEN_LEGACY_INTEGRATION_TARGETS == (
        "task_worker.py",
        "executor_service.py",
        "routes/runtime.py",
        "controlled_runtime_service.py",
    )
    assert "fake" in EXTERNAL_EXECUTOR_MODULE_BOUNDARY
    assert "preview" in EXTERNAL_EXECUTOR_MODULE_BOUNDARY
    assert "actual" in EXTERNAL_EXECUTOR_MODULE_BOUNDARY
    assert any(
        "fake" in rule and "preview" in rule and "actual" in rule and "separate" in rule
        for rule in BOUNDARY_RULES
    )


def test_boundary_states_orchestration_and_no_real_launch_limits() -> None:
    boundary_text = "\n".join((EXTERNAL_EXECUTOR_MODULE_BOUNDARY, *BOUNDARY_RULES))

    assert "external_executors" in boundary_text
    assert "task_worker.py" in boundary_text
    assert "executor_service.py" in boundary_text
    assert "route files" in boundary_text
    assert "ControlledRuntimeService" in boundary_text
    assert "repository" in boundary_text
    assert "RealExecutorAdapter" in boundary_text
    assert "subprocess" in boundary_text
    assert "real executor launch" in boundary_text


def test_boundary_does_not_import_forbidden_layers_or_process_modules() -> None:
    source = BOUNDARY_FILE.read_text()

    forbidden_snippets = {
        "app.api",
        "app.workers",
        "app.services.executor_service",
        "import subprocess",
        "from subprocess",
        "import os",
        "from os",
        "import pty",
        "from pty",
        "import shlex",
        "from shlex",
        "import pathlib",
        "from pathlib",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_boundary_does_not_contain_execution_traces_or_sensitive_fields() -> None:
    source = BOUNDARY_FILE.read_text()

    forbidden_snippets = {
        "os.popen",
        "shell=True",
        "Popen",
        "run(",
        "call(",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
        "password",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_task_worker_has_no_actual_executor_integration_trace() -> None:
    source = _read("app/workers/task_worker.py")

    forbidden_snippets = {
        "RealExecutorAdapter",
        "external_executors",
        "Codex CLI",
        "Claude Code",
        "DeepSeek CLI",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_executor_service_has_no_actual_executor_integration_trace() -> None:
    source = _read("app/services/executor_service.py")

    forbidden_snippets = {
        "RealExecutorAdapter",
        "external_executors",
        "Codex CLI",
        "Claude Code",
        "DeepSeek CLI",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_runtime_route_has_no_actual_executor_integration_trace() -> None:
    source = _read("app/api/routes/runtime.py")

    forbidden_snippets = {
        "RealExecutorAdapter",
        "external_executors",
        "subprocess",
        "Popen",
        "shell=True",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_controlled_runtime_service_stays_free_of_process_launch_helpers() -> None:
    source = _read("app/services/controlled_runtime_service.py")

    forbidden_snippets = {
        "import subprocess",
        "from subprocess",
        "os.popen",
        "import pty",
        "from pty",
        "tmux",
        "shell=True",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_boundary_does_not_create_route_migration_or_web_entrypoints() -> None:
    assert not Path("app/api/routes/external_executor.py").exists()
    assert not Path("app/api/routes/external_executors.py").exists()
    assert not any(Path("migrations").glob("*external_executor*"))
    assert not Path("../../apps/web/external_executors").exists()


def test_actual_contract_exists_without_legacy_integration_targets() -> None:
    source = ACTUAL_CONTRACT_FILE.read_text()

    assert "RealExecutorAdapterProtocol" in source
    assert "class RealExecutorAdapter(" not in source
    assert "def launch(self, context:" in source
    assert "def poll(self, session_id:" in source
    assert "def cancel(self, session_id:" in source
    assert "def kill(self, session_id:" in source
    assert "def cleanup(self, session_id:" in source

    forbidden_snippets = {
        "app.api",
        "app.workers",
        "app.services",
        "app.repositories",
        "import subprocess",
        "from subprocess",
        "os.popen",
        "import pty",
        "from pty",
        "import shlex",
        "from shlex",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_actual_preflight_exists_without_legacy_integration_targets() -> None:
    source = ACTUAL_PREFLIGHT_FILE.read_text()

    assert "RealExecutorPreflightService" in source
    assert "RealExecutorPreflightInput" in source
    assert "RealExecutorPreflightResult" in source
    assert "class RealExecutorAdapter(" not in source
    assert "def evaluate(" in source
    assert "def evaluate_launch(" in source

    forbidden_snippets = {
        "app.api",
        "app.workers",
        "app.services",
        "app.repositories",
        "import subprocess",
        "from subprocess",
        "os.popen",
        "import os",
        "from os",
        "import pty",
        "from pty",
        "import shlex",
        "from shlex",
        "Popen",
        "shell=True",
        "tmux",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_actual_preview_exists_without_legacy_integration_targets() -> None:
    source = ACTUAL_PREVIEW_FILE.read_text()

    assert "RealExecutorLaunchPlanPreviewBuilder" in source
    assert "RealExecutorLaunchPlanPreviewInput" in source
    assert "RealExecutorLaunchPlanPreview" in source
    assert "class RealExecutorAdapter(" not in source
    assert "def build(" in source
    assert "executable=False" in source

    forbidden_snippets = {
        "app.api",
        "app.workers",
        "app.services",
        "app.repositories",
        "import subprocess",
        "from subprocess",
        "os.popen",
        "import os",
        "from os",
        "import pty",
        "from pty",
        "import shlex",
        "from shlex",
        "Popen",
        "shell=True",
        "tmux",
        "raw_command",
        "env_vars",
        "process_handle",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_actual_disabled_adapter_exists_without_legacy_integration_targets() -> None:
    source = ACTUAL_DISABLED_ADAPTER_FILE.read_text()

    assert "DisabledRealExecutorAdapter" in source
    assert "DisabledRealExecutorAdapterConfig" in source
    assert "DisabledRealExecutorAdapterAuditEvent" in source
    assert "class RealExecutorAdapter(" not in source
    assert "def launch(self, context:" in source
    assert "def poll(self, session_id:" in source
    assert "def cancel(self, session_id:" in source
    assert "def kill(self, session_id:" in source
    assert "def cleanup(self, session_id:" in source
    assert "RealExecutorOperationStatus.BLOCKED" in source

    forbidden_snippets = {
        "app.api",
        "app.workers",
        "app.services",
        "app.repositories",
        "import subprocess",
        "from subprocess",
        "os.popen",
        "import os",
        "from os",
        "import pty",
        "from pty",
        "import shlex",
        "from shlex",
        "Popen",
        "shell=True",
        "tmux",
        "raw_command",
        "env_vars",
        "process_handle",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source
