"""Contract tests for P21-C-H-B2-B native readonly reviewer transport."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessSupervisor,
)
from app.external_executors.readonly_reviewer_native_transport import (
    NativeReadonlyReviewerCaptureTransport,
)
from app.external_executors.readonly_reviewer_transport import (
    FakeReadonlyReviewerTransport,
    ReadonlyReviewerTransportRequest,
)
from app.services.project_director_sandbox_candidate_diff_readonly_reviewer_adapter_service import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


WRITE_FLAGS = [
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
]

PROMPT = "Review this readonly diff.\nDo not write files."
SCOPE = ["src/a.py"]


def _prompt_sha256(prompt: str = PROMPT) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _prompt_bytes(prompt: str = PROMPT) -> int:
    return len(prompt.encode("utf-8"))


def _valid_raw_output() -> str:
    return json.dumps(
        {
            "review_status": "reviewed",
            "verdict": "no_blocking_findings",
            "risk_level": "low",
            "summary": "No blocking issues.",
            "findings": [],
            "recommended_next_step": "Proceed.",
        },
        ensure_ascii=False,
    )


def _request(*, executor: str = "codex", prompt: str = PROMPT):
    return ReadonlyReviewerTransportRequest(
        requested_reviewer_executor=executor,
        review_prompt_text=prompt,
        review_prompt_sha256=_prompt_sha256(prompt),
        review_prompt_bytes=_prompt_bytes(prompt),
        review_scope_paths=list(SCOPE),
        review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
    )


class FakeNativeProcess:
    def __init__(
        self,
        *,
        stdout_bytes: bytes = b"",
        stderr_bytes: bytes = b"",
        returncode: int = 0,
        timeout_on_communicate: bool = False,
        timeout_on_wait_after_terminate: bool = False,
    ) -> None:
        self.stdout_bytes = stdout_bytes
        self.stderr_bytes = stderr_bytes
        self.returncode = returncode
        self.timeout_on_communicate = timeout_on_communicate
        self.timeout_on_wait_after_terminate = timeout_on_wait_after_terminate
        self.communicate_input: bytes | None = None
        self.communicate_timeout: float | None = None
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def communicate(self, *, input=None, timeout=None):
        self.communicate_input = input
        self.communicate_timeout = timeout
        if self.timeout_on_communicate:
            raise subprocess.TimeoutExpired(cmd="fake-reviewer", timeout=timeout)
        return self.stdout_bytes, self.stderr_bytes

    def wait(self, timeout=None):
        self.wait_calls += 1
        if (
            self.terminated
            and not self.killed
            and self.timeout_on_wait_after_terminate
        ):
            raise subprocess.TimeoutExpired(cmd="fake-reviewer", timeout=timeout)
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class RecordingPopenFactory:
    def __init__(self, process: FakeNativeProcess | None = None) -> None:
        self.process = process or FakeNativeProcess(
            stdout_bytes=_valid_raw_output().encode("utf-8")
        )
        self.calls: list[dict] = []

    def __call__(self, *argv, **kwargs):
        self.calls.append({"argv": argv, "kwargs": kwargs})
        return self.process


class RaisingPopenFactory:
    def __call__(self, *argv, **kwargs):
        raise RuntimeError("secret launch failure details must not leak")


class SpySupervisor(RealExecutorProcessSupervisor):
    def __init__(self) -> None:
        super().__init__()
        self.register_calls = 0
        self.cleanup_calls = 0

    def register(self, *args, **kwargs):
        self.register_calls += 1
        return super().register(*args, **kwargs)

    def cleanup(self, *args, **kwargs):
        self.cleanup_calls += 1
        return super().cleanup(*args, **kwargs)


def _transport(tmp_path: Path, *, process=None, supervisor=None, timeout=1.0):
    popen_factory = RecordingPopenFactory(process)
    transport = NativeReadonlyReviewerCaptureTransport(
        workspace_path=str(tmp_path),
        timeout_seconds=timeout,
        process_supervisor=supervisor or SpySupervisor(),
        popen_factory=popen_factory,
    )
    return transport, popen_factory


def _call_adapter_with_transport(transport, *, executor="codex", prompt=PROMPT, svc=None):
    svc = svc or ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService()
    return svc.validate_review_output_through_transport(
        requested_reviewer_executor=executor,
        review_prompt_text=prompt,
        expected_review_prompt_sha256=_prompt_sha256(prompt),
        expected_review_prompt_bytes=_prompt_bytes(prompt),
        review_scope_paths=list(SCOPE),
        transport=transport,
    )


def test_constructor_rejects_relative_workspace_path() -> None:
    with pytest.raises(ValueError, match="workspace_path must be absolute"):
        NativeReadonlyReviewerCaptureTransport(
            workspace_path="relative/path",
            timeout_seconds=1.0,
            process_supervisor=SpySupervisor(),
            popen_factory=RecordingPopenFactory(),
        )


def test_constructor_rejects_non_positive_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        NativeReadonlyReviewerCaptureTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=0,
            process_supervisor=SpySupervisor(),
            popen_factory=RecordingPopenFactory(),
        )


def test_fake_transport_execution_metadata_all_false() -> None:
    fake = FakeReadonlyReviewerTransport(raw_output_text=_valid_raw_output())
    result = fake.execute(_request())
    assert result.execution_mode == "fake_transport"
    assert result.real_reviewer_started is False
    assert result.real_reviewer_executed is False
    assert result.native_process_started is False
    assert result.provider_called is False
    assert result.codex_started is False
    assert result.claude_code_started is False


def test_successful_native_process_start_and_capture_contract(tmp_path: Path) -> None:
    stdout = "\n```json\n{\"ok\":true}\n```\nDone.\n"
    process = FakeNativeProcess(
        stdout_bytes=stdout.encode("utf-8"),
        stderr_bytes=b"stderr must not leak",
        returncode=0,
    )
    supervisor = SpySupervisor()
    transport, popen_factory = _transport(
        tmp_path, process=process, supervisor=supervisor
    )

    result = transport.execute(_request())

    assert result.transport_status == "completed"
    assert result.raw_output_text == stdout
    assert result.execution_mode == "native_capture_transport"
    assert result.real_reviewer_started is True
    assert result.real_reviewer_executed is True
    assert result.native_process_started is True
    assert result.provider_called is False
    assert result.codex_started is True
    assert result.claude_code_started is False
    assert process.communicate_input == PROMPT.encode("utf-8")
    assert process.communicate_timeout == 1.0

    call = popen_factory.calls[0]
    assert call["argv"][0] == ["codex"]
    assert PROMPT not in call["argv"][0]
    assert call["kwargs"]["shell"] is False
    assert call["kwargs"]["cwd"] == str(tmp_path)
    assert call["kwargs"]["stdin"] == subprocess.PIPE
    assert call["kwargs"]["stdout"] == subprocess.PIPE
    assert call["kwargs"]["stderr"] == subprocess.PIPE
    assert supervisor.register_calls == 1
    assert supervisor.cleanup_calls == 1
    assert supervisor.snapshot().total_records == 0
    assert tmp_path.exists()

    dumped = asdict(result)
    assert "process_handle_id" not in dumped
    assert "pid" not in dumped
    assert "argv" not in dumped
    assert "stderr" not in dumped
    assert "stderr must not leak" not in repr(result)


def test_claude_code_success_sets_claude_flags(tmp_path: Path) -> None:
    transport, _ = _transport(tmp_path)
    result = transport.execute(_request(executor="claude-code"))

    assert result.transport_status == "completed"
    assert result.execution_mode == "native_capture_transport"
    assert result.real_reviewer_started is True
    assert result.real_reviewer_executed is True
    assert result.native_process_started is True
    assert result.provider_called is False
    assert result.codex_started is False
    assert result.claude_code_started is True


def test_non_zero_exit_failed_without_stderr_leak(tmp_path: Path) -> None:
    process = FakeNativeProcess(
        stdout_bytes=b'{"ignored":true}',
        stderr_bytes=b"raw stderr secret",
        returncode=7,
    )
    transport, _ = _transport(tmp_path, process=process)

    result = transport.execute(_request())

    assert result.transport_status == "failed"
    assert result.transport_error_code == "reviewer_native_exit_nonzero"
    assert result.raw_output_text == ""
    assert result.real_reviewer_started is True
    assert result.real_reviewer_executed is False
    assert "raw stderr secret" not in repr(result)


def test_launch_failure_failed_without_exception_leak(tmp_path: Path) -> None:
    transport = NativeReadonlyReviewerCaptureTransport(
        workspace_path=str(tmp_path),
        timeout_seconds=1.0,
        process_supervisor=SpySupervisor(),
        popen_factory=RaisingPopenFactory(),
    )

    result = transport.execute(_request())

    assert result.transport_status == "failed"
    assert result.transport_error_code == "reviewer_native_launch_failed"
    assert result.real_reviewer_started is False
    assert result.real_reviewer_executed is False
    assert "secret launch failure" not in repr(result)


def test_timeout_terminates_then_kills_and_cleans_up(tmp_path: Path) -> None:
    process = FakeNativeProcess(
        timeout_on_communicate=True,
        timeout_on_wait_after_terminate=True,
    )
    supervisor = SpySupervisor()
    transport, _ = _transport(tmp_path, process=process, supervisor=supervisor)

    result = transport.execute(_request())

    assert result.transport_status == "timeout"
    assert result.transport_error_code == "reviewer_native_timeout"
    assert result.raw_output_text == ""
    assert process.terminated is True
    assert process.killed is True
    assert supervisor.register_calls == 1
    assert supervisor.cleanup_calls == 1
    assert supervisor.snapshot().total_records == 0
    assert result.real_reviewer_started is True
    assert result.real_reviewer_executed is False


def test_timeout_can_terminate_without_kill(tmp_path: Path) -> None:
    process = FakeNativeProcess(timeout_on_communicate=True)
    transport, _ = _transport(tmp_path, process=process)

    result = transport.execute(_request())

    assert result.transport_status == "timeout"
    assert process.terminated is True
    assert process.killed is False


def test_invalid_utf8_stdout_failed(tmp_path: Path) -> None:
    process = FakeNativeProcess(stdout_bytes=b"\xff\xfe", returncode=0)
    transport, _ = _transport(tmp_path, process=process)

    result = transport.execute(_request())

    assert result.transport_status == "failed"
    assert result.transport_error_code == "reviewer_stdout_invalid_utf8"
    assert result.raw_output_text == ""
    assert result.real_reviewer_started is True
    assert result.real_reviewer_executed is False


def test_native_completed_raw_output_enters_hb1_verbatim(tmp_path: Path) -> None:
    raw = _valid_raw_output()
    process = FakeNativeProcess(stdout_bytes=raw.encode("utf-8"), returncode=0)
    transport, _ = _transport(tmp_path, process=process)
    captured = {}

    class SpyValidationService:
        def validate_raw_review_output(self, **kwargs):
            captured.update(kwargs)
            from app.services.project_director_sandbox_candidate_diff_review_output_validation_service import (
                ProjectDirectorSandboxCandidateDiffReviewOutputValidationService,
            )

            return (
                ProjectDirectorSandboxCandidateDiffReviewOutputValidationService()
                .validate_raw_review_output(**kwargs)
            )

    result = _call_adapter_with_transport(
        transport,
        svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=SpyValidationService()
        ),
    )

    assert result.adapter_status == "validated_output"
    assert result.execution_mode == "native_capture_transport"
    assert captured["raw_output_text"] == raw
    assert result.real_reviewer_started is True
    assert result.real_reviewer_executed is True
    assert result.native_process_started is True
    for flag in WRITE_FLAGS:
        assert getattr(result, flag) is False


def test_native_failed_does_not_call_hb1(tmp_path: Path) -> None:
    process = FakeNativeProcess(returncode=1)
    transport, _ = _transport(tmp_path, process=process)

    class SpyValidationService:
        call_count = 0

        def validate_raw_review_output(self, **kwargs):
            self.call_count += 1
            raise AssertionError("H-B1 must not be called")

    spy = SpyValidationService()
    result = _call_adapter_with_transport(
        transport,
        svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=spy
        ),
    )

    assert result.adapter_status == "blocked"
    assert result.execution_mode == "native_capture_transport"
    assert result.transport_status == "failed"
    assert spy.call_count == 0


def test_native_timeout_does_not_call_hb1(tmp_path: Path) -> None:
    process = FakeNativeProcess(timeout_on_communicate=True)
    transport, _ = _transport(tmp_path, process=process)

    class SpyValidationService:
        call_count = 0

        def validate_raw_review_output(self, **kwargs):
            self.call_count += 1
            raise AssertionError("H-B1 must not be called")

    spy = SpyValidationService()
    result = _call_adapter_with_transport(
        transport,
        svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=spy
        ),
    )

    assert result.adapter_status == "blocked"
    assert result.execution_mode == "native_capture_transport"
    assert result.transport_status == "timeout"
    assert spy.call_count == 0
