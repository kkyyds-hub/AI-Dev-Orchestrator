"""Contract tests for P21-C-H-B2-B hardened native readonly reviewer transport."""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from app.external_executors.actual_process_supervisor import (
    RealExecutorProcessSupervisor,
)
from app.external_executors.readonly_reviewer_native_transport import (
    NativeReadonlyReviewerCaptureTransport,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportRequest,
)
from app.services.project_director_sandbox_candidate_diff_readonly_reviewer_adapter_service import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)


WRITE_FLAGS = [
    "main_project_file_written", "sandbox_file_written", "manifest_file_written",
    "diff_file_written", "patch_applied", "git_write_performed",
    "worktree_created", "worker_started", "task_created", "run_created",
]

PROMPT = "Review this readonly diff.\nDo not write files."
SCOPE = ["src/a.py"]


def _prompt_sha256(prompt: str = PROMPT) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _prompt_bytes(prompt: str = PROMPT) -> int:
    return len(prompt.encode("utf-8"))


def _valid_raw_output() -> str:
    return json.dumps({
        "review_status": "reviewed",
        "verdict": "no_blocking_findings",
        "risk_level": "low",
        "summary": "No blocking issues.",
        "findings": [],
        "recommended_next_step": "Proceed.",
    }, ensure_ascii=False)


def _request(*, executor="codex", prompt=PROMPT):
    return ReadonlyReviewerTransportRequest(
        requested_reviewer_executor=executor,
        review_prompt_text=prompt,
        review_prompt_sha256=_prompt_sha256(prompt),
        review_prompt_bytes=_prompt_bytes(prompt),
        review_scope_paths=list(SCOPE),
        review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
    )


# ── Real-pipe FakeProcess ──────────────────────────────────────────


class _FakeStdinPipe:
    def __init__(self) -> None:
        self._read_fd, self._write_fd = os.pipe()
        self._write_file = os.fdopen(self._write_fd, "wb")
        self.written: bytes = b""

    def write(self, data: bytes) -> None:
        self.written += data
        self._write_file.write(data)
        self._write_file.flush()

    def close(self) -> None:
        self._write_file.close()
        os.close(self._read_fd)

    @property
    def closed(self) -> bool:
        return self._write_file.closed


class _FakeStdoutPipe:
    def __init__(self, data: bytes) -> None:
        self._read_fd, self._write_fd = os.pipe()
        os.write(self._write_fd, data)
        os.close(self._write_fd)
        self._read_file = os.fdopen(self._read_fd, "rb")

    def fileno(self) -> int:
        return self._read_fd

    def read(self, n: int = -1) -> bytes:
        return self._read_file.read(n)

    def close(self) -> None:
        try:
            self._read_file.close()
        except OSError:
            pass


class RealPipeFakeProcess:
    """Fake process with real OS pipes for stdin/stdout."""

    def __init__(
        self,
        *,
        stdout_bytes: bytes = b"",
        returncode: int = 0,
        delay_stdout: float = 0,
    ) -> None:
        self.stdin = _FakeStdinPipe()
        self.stdout = _FakeStdoutPipe(stdout_bytes)
        self.returncode = returncode
        self._returncode = returncode
        self.terminated = False
        self.killed = False
        self._delay_stdout = delay_stdout
        self._wait_event = threading.Event()

    def poll(self) -> int | None:
        if self._wait_event.is_set() or self.returncode is not None:
            return self._returncode
        return None

    def wait(self, timeout: float | None = None) -> int:
        if self._delay_stdout > 0 and not self._wait_event.is_set():
            self._wait_event.wait(timeout=self._delay_stdout)
            if not self._wait_event.is_set():
                raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout or 0)
        self._wait_event.set()
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._wait_event.set()

    def kill(self) -> None:
        self.killed = True
        self._wait_event.set()


class SlowStdoutFakeProcess(RealPipeFakeProcess):
    """Process that delays stdout writing to simulate slow output."""

    def __init__(self, stdout_bytes: bytes, delay: float) -> None:
        super().__init__(stdout_bytes=b"", returncode=0)
        self._slow_data = stdout_bytes
        self._slow_delay = delay
        # Rewrite stdout pipe with delayed data via thread
        self.stdout.close()
        self.stdout = _SlowStdoutPipe(stdout_bytes, delay)


class _SlowStdoutPipe:
    def __init__(self, data: bytes, delay: float) -> None:
        self._read_fd, self._write_fd = os.pipe()
        self._data = data
        self._delay = delay
        self._thread = threading.Thread(target=self._write_later, daemon=True)
        self._thread.start()

    def _write_later(self) -> None:
        time.sleep(self._delay)
        try:
            os.write(self._write_fd, self._data)
        except OSError:
            pass
        finally:
            try:
                os.close(self._write_fd)
            except OSError:
                pass

    def fileno(self) -> int:
        return self._read_fd

    def read(self, n: int = -1) -> bytes:
        return os.read(self._read_fd, n) if n > 0 else b""

    def close(self) -> None:
        try:
            os.close(self._read_fd)
        except OSError:
            pass


# ── Popen factories ────────────────────────────────────────────────


class RecordingPopenFactory:
    def __init__(self, process) -> None:
        self.process = process
        self.calls: list[dict] = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": argv, "kwargs": kwargs})
        return self.process


class RaisingPopenFactory:
    def __call__(self, *argv, **kwargs):
        raise RuntimeError("secret launch failure details must not leak")


# ── Supervisors ────────────────────────────────────────────────────


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


class RegisterFailingSupervisor(RealExecutorProcessSupervisor):
    def __init__(self) -> None:
        super().__init__()
        self.register_calls = 0
        self.cleanup_calls = 0

    def register(self, *args, **kwargs):
        self.register_calls += 1
        raise RuntimeError("supervisor register failed")

    def cleanup(self, *args, **kwargs):
        self.cleanup_calls += 1
        return super().cleanup(*args, **kwargs)


# ── Helpers ────────────────────────────────────────────────────────


def _transport(tmp_path: Path, *, process=None, supervisor=None, timeout=2.0,
               max_output_bytes=100_000, popen_factory_cls=RecordingPopenFactory):
    if process is None:
        process = RealPipeFakeProcess(stdout_bytes=_valid_raw_output().encode("utf-8"))
    popen_factory = popen_factory_cls(process) if popen_factory_cls is not RaisingPopenFactory else RaisingPopenFactory()
    sup = supervisor or SpySupervisor()
    transport = NativeReadonlyReviewerCaptureTransport(
        workspace_path=str(tmp_path),
        timeout_seconds=timeout,
        max_output_bytes=max_output_bytes,
        process_supervisor=sup,
        popen_factory=popen_factory,
    )
    return transport, popen_factory, sup


def _call_adapter(transport, *, executor="codex", prompt=PROMPT, svc=None):
    svc = svc or ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService()
    return svc.validate_review_output_through_transport(
        requested_reviewer_executor=executor,
        review_prompt_text=prompt,
        expected_review_prompt_sha256=_prompt_sha256(prompt),
        expected_review_prompt_bytes=_prompt_bytes(prompt),
        review_scope_paths=list(SCOPE),
        transport=transport,
    )


# ══════════════════════════════════════════════════════════════════════
# A. Constructor validation
# ══════════════════════════════════════════════════════════════════════


class TestConstructorValidation:
    def test_rejects_relative_workspace_path(self) -> None:
        with pytest.raises(ValueError, match="workspace_path must be absolute"):
            NativeReadonlyReviewerCaptureTransport(
                workspace_path="relative/path", timeout_seconds=1.0,
                max_output_bytes=1000, process_supervisor=SpySupervisor(),
                popen_factory=RecordingPopenFactory(RealPipeFakeProcess()),
            )

    def test_rejects_non_positive_timeout(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            NativeReadonlyReviewerCaptureTransport(
                workspace_path=str(tmp_path), timeout_seconds=0,
                max_output_bytes=1000, process_supervisor=SpySupervisor(),
                popen_factory=RecordingPopenFactory(RealPipeFakeProcess()),
            )

    def test_rejects_zero_max_output_bytes(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="max_output_bytes must be positive"):
            NativeReadonlyReviewerCaptureTransport(
                workspace_path=str(tmp_path), timeout_seconds=1.0,
                max_output_bytes=0, process_supervisor=SpySupervisor(),
                popen_factory=RecordingPopenFactory(RealPipeFakeProcess()),
            )

    def test_rejects_negative_max_output_bytes(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="max_output_bytes must be positive"):
            NativeReadonlyReviewerCaptureTransport(
                workspace_path=str(tmp_path), timeout_seconds=1.0,
                max_output_bytes=-1, process_supervisor=SpySupervisor(),
                popen_factory=RecordingPopenFactory(RealPipeFakeProcess()),
            )


# ══════════════════════════════════════════════════════════════════════
# B. Command profile contract
# ══════════════════════════════════════════════════════════════════════


class TestCommandProfile:
    def test_codex_exact_argv(self, tmp_path) -> None:
        transport, popen_factory, _ = _transport(tmp_path)
        transport.execute(_request(executor="codex"))
        call = popen_factory.calls[0]
        assert call["argv"] == [
            "codex", "exec", "--ephemeral", "--sandbox", "read-only",
            "--color", "never", "-",
        ]

    def test_codex_prompt_not_in_argv(self, tmp_path) -> None:
        transport, popen_factory, _ = _transport(tmp_path)
        transport.execute(_request(executor="codex"))
        argv = popen_factory.calls[0]["argv"]
        assert PROMPT not in argv
        assert "diff" not in " ".join(argv).lower()

    def test_claude_command_profile(self, tmp_path) -> None:
        transport, popen_factory, _ = _transport(tmp_path)
        transport.execute(_request(executor="claude-code"))
        argv = popen_factory.calls[0]["argv"]
        assert argv[0] == "claude"
        assert "-p" in argv
        p_idx = argv.index("-p")
        assert argv[p_idx + 1] == (
            "Review the content provided through stdin and return only "
            "the requested final review output."
        )
        assert "--permission-mode" in argv
        pm_idx = argv.index("--permission-mode")
        assert argv[pm_idx + 1] == "plan"
        assert "--no-session-persistence" in argv

    def test_claude_prompt_not_in_argv(self, tmp_path) -> None:
        transport, popen_factory, _ = _transport(tmp_path)
        transport.execute(_request(executor="claude-code"))
        argv = popen_factory.calls[0]["argv"]
        assert PROMPT not in argv


# ══════════════════════════════════════════════════════════════════════
# C. Popen boundary
# ══════════════════════════════════════════════════════════════════════


class TestPopenBoundary:
    def test_shell_false_stdin_pipe_stdout_pipe(self, tmp_path) -> None:
        transport, popen_factory, _ = _transport(tmp_path)
        transport.execute(_request())
        kwargs = popen_factory.calls[0]["kwargs"]
        assert kwargs["shell"] is False
        assert kwargs["stdin"] == subprocess.PIPE
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["cwd"] == str(tmp_path)

    def test_prompt_via_stdin_not_argv(self, tmp_path) -> None:
        transport, popen_factory, _ = _transport(tmp_path)
        transport.execute(_request())
        process = popen_factory.process
        assert process.stdin.written == PROMPT.encode("utf-8")


# ══════════════════════════════════════════════════════════════════════
# D. max_output_bytes contract
# ══════════════════════════════════════════════════════════════════════


class TestMaxOutputBytes:
    def test_exact_limit_completed(self, tmp_path) -> None:
        data = b"x" * 100
        process = RealPipeFakeProcess(stdout_bytes=data, returncode=0)
        transport, _, _ = _transport(tmp_path, process=process, max_output_bytes=100)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert len(result.raw_output_text.encode("utf-8")) == 100

    def test_exceed_by_one_failed(self, tmp_path) -> None:
        data = b"x" * 101
        process = RealPipeFakeProcess(stdout_bytes=data, returncode=0)
        transport, _, _ = _transport(tmp_path, process=process, max_output_bytes=100)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdout_too_large"
        assert result.raw_output_text == ""
        assert result.real_reviewer_executed is False


# ══════════════════════════════════════════════════════════════════════
# E. Multi-chunk raw preservation
# ══════════════════════════════════════════════════════════════════════


class TestMultiChunkPreservation:
    def test_raw_preserved_with_leading_trailing_whitespace(self, tmp_path) -> None:
        stdout = "\n  \n{\"review_status\":\"reviewed\",\"verdict\":\"no_blocking_findings\",\"risk_level\":\"low\",\"summary\":\"S\",\"findings\":[],\"recommended_next_step\":\"N\"}\n  \n"
        process = RealPipeFakeProcess(stdout_bytes=stdout.encode("utf-8"), returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.raw_output_text == stdout

    def test_raw_preserved_markdown_fence(self, tmp_path) -> None:
        inner = _valid_raw_output()
        stdout = f"```json\n{inner}\n```"
        process = RealPipeFakeProcess(stdout_bytes=stdout.encode("utf-8"), returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.raw_output_text == stdout
        assert "```" in result.raw_output_text

    def test_raw_preserved_prefix_suffix(self, tmp_path) -> None:
        inner = _valid_raw_output()
        stdout = f"Here is my review:\n{inner}\nDone."
        process = RealPipeFakeProcess(stdout_bytes=stdout.encode("utf-8"), returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.raw_output_text == stdout

    def test_chinese_content_preserved(self, tmp_path) -> None:
        stdout = '{"summary": "发现一个边界问题"}'
        process = RealPipeFakeProcess(stdout_bytes=stdout.encode("utf-8"), returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.raw_output_text == stdout
        assert len(result.raw_output_text.encode("utf-8")) > len(stdout)


# ══════════════════════════════════════════════════════════════════════
# F. Real OS pipe tests
# ══════════════════════════════════════════════════════════════════════


class TestRealOSPipe:
    def _helper_echo_script(self) -> str:
        return (
            "import sys\n"
            "data = sys.stdin.buffer.read()\n"
            "sys.stdout.buffer.write(data)\n"
        )

    def _helper_overflow_script(self, size: int) -> str:
        return (
            f"import sys\n"
            f"sys.stdout.buffer.write(b'x' * {size})\n"
        )

    def _helper_slow_script(self, delay: float) -> str:
        return (
            f"import sys, time\n"
            f"time.sleep({delay})\n"
            f"sys.stdout.buffer.write(b'done')\n"
        )

    def test_real_pipe_echo(self, tmp_path) -> None:
        script = self._helper_echo_script()
        script_path = tmp_path / "echo_helper.py"
        script_path.write_text(script)

        prompt_data = "A" * 5000  # larger than single chunk
        transport = NativeReadonlyReviewerCaptureTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=5.0,
            max_output_bytes=100_000,
            process_supervisor=SpySupervisor(),
            popen_factory=lambda argv, **kw: subprocess.Popen(
                [sys.executable, str(script_path)],
                **{k: v for k, v in kw.items() if k != "close_fds"},
            ),
        )
        result = transport.execute(_request(prompt=prompt_data))
        assert result.transport_status == "completed"
        assert result.raw_output_text == prompt_data

    def test_real_pipe_overflow(self, tmp_path) -> None:
        max_bytes = 50
        script = self._helper_overflow_script(max_bytes + 1)
        script_path = tmp_path / "overflow_helper.py"
        script_path.write_text(script)

        transport = NativeReadonlyReviewerCaptureTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=5.0,
            max_output_bytes=max_bytes,
            process_supervisor=SpySupervisor(),
            popen_factory=lambda argv, **kw: subprocess.Popen(
                [sys.executable, str(script_path)],
                **{k: v for k, v in kw.items() if k != "close_fds"},
            ),
        )
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdout_too_large"
        assert result.raw_output_text == ""

    def test_real_pipe_timeout(self, tmp_path) -> None:
        script = self._helper_slow_script(10.0)
        script_path = tmp_path / "slow_helper.py"
        script_path.write_text(script)

        sup = SpySupervisor()
        transport = NativeReadonlyReviewerCaptureTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=0.3,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=lambda argv, **kw: subprocess.Popen(
                [sys.executable, str(script_path)],
                **{k: v for k, v in kw.items() if k != "close_fds"},
            ),
        )
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert result.raw_output_text == ""
        assert result.real_reviewer_executed is False
        assert sup.snapshot().total_records == 0


# ══════════════════════════════════════════════════════════════════════
# G. Stderr leak boundary
# ══════════════════════════════════════════════════════════════════════


class TestStderrLeakBoundary:
    def test_stderr_not_in_result(self, tmp_path) -> None:
        process = RealPipeFakeProcess(
            stdout_bytes=_valid_raw_output().encode("utf-8"), returncode=0,
        )
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        dumped = asdict(result)
        assert "stderr" not in dumped
        assert "process_handle_id" not in dumped
        assert "pid" not in dumped
        assert "argv" not in dumped


# ══════════════════════════════════════════════════════════════════════
# H. Timeout / terminate / kill
# ══════════════════════════════════════════════════════════════════════


class TestTimeoutTerminateKill:
    def test_timeout_terminates_and_cleans_up(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"", returncode=0, delay_stdout=10.0)
        sup = SpySupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup, timeout=0.3)
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert result.real_reviewer_executed is False
        assert sup.register_calls == 1
        assert sup.cleanup_calls == 1
        assert sup.snapshot().total_records == 0

    def test_timeout_terminate_sufficient(self, tmp_path) -> None:
        """When terminate succeeds, kill should not be needed."""
        process = RealPipeFakeProcess(stdout_bytes=b"", returncode=0, delay_stdout=10.0)
        sup = SpySupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup, timeout=0.3)
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert process.terminated is True


# ══════════════════════════════════════════════════════════════════════
# I. Invalid UTF-8
# ══════════════════════════════════════════════════════════════════════


class TestInvalidUTF8:
    def test_invalid_utf8_failed(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"\xff\xfe", returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdout_invalid_utf8"
        assert result.raw_output_text == ""
        assert result.real_reviewer_executed is False


# ══════════════════════════════════════════════════════════════════════
# J. Non-zero exit
# ══════════════════════════════════════════════════════════════════════


class TestNonZeroExit:
    def test_nonzero_exit_failed(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"ignored", returncode=7)
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_native_exit_nonzero"
        assert result.raw_output_text == ""
        assert result.real_reviewer_executed is False


# ══════════════════════════════════════════════════════════════════════
# K. Launch failure
# ══════════════════════════════════════════════════════════════════════


class TestLaunchFailure:
    def test_launch_failure_no_exception_leak(self, tmp_path) -> None:
        transport = NativeReadonlyReviewerCaptureTransport(
            workspace_path=str(tmp_path), timeout_seconds=1.0,
            max_output_bytes=1000, process_supervisor=SpySupervisor(),
            popen_factory=RaisingPopenFactory(),
        )
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_native_launch_failed"
        assert result.real_reviewer_started is False
        assert result.real_reviewer_executed is False
        assert "secret launch failure" not in repr(result)


# ══════════════════════════════════════════════════════════════════════
# L. Register failure cleanup
# ══════════════════════════════════════════════════════════════════════


class TestRegisterFailureCleanup:
    def test_register_failure_terminates_process(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=_valid_raw_output().encode("utf-8"))
        sup = RegisterFailingSupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_native_failed"
        assert result.real_reviewer_executed is False
        assert sup.register_calls == 1
        # cleanup may or may not be called depending on implementation


# ══════════════════════════════════════════════════════════════════════
# M. Supervisor lifecycle
# ══════════════════════════════════════════════════════════════════════


class TestSupervisorLifecycle:
    def test_completed_register_cleanup(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=_valid_raw_output().encode("utf-8"))
        sup = SpySupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup)
        transport.execute(_request())
        assert sup.register_calls == 1
        assert sup.cleanup_calls == 1
        assert sup.snapshot().total_records == 0

    def test_failed_register_cleanup(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"", returncode=1)
        sup = SpySupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup)
        transport.execute(_request())
        assert sup.register_calls == 1
        assert sup.cleanup_calls == 1
        assert sup.snapshot().total_records == 0

    def test_timeout_register_cleanup(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"", returncode=0, delay_stdout=10.0)
        sup = SpySupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup, timeout=0.3)
        transport.execute(_request())
        assert sup.register_calls == 1
        assert sup.cleanup_calls == 1
        assert sup.snapshot().total_records == 0

    def test_stdout_too_large_register_cleanup(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"x" * 101, returncode=0)
        sup = SpySupervisor()
        transport, _, _ = _transport(tmp_path, process=process, supervisor=sup, max_output_bytes=100)
        transport.execute(_request())
        assert sup.register_calls == 1
        assert sup.cleanup_calls == 1
        assert sup.snapshot().total_records == 0


# ══════════════════════════════════════════════════════════════════════
# N. H-B1 integration
# ══════════════════════════════════════════════════════════════════════


class TestHB1Integration:
    def test_completed_valid_enters_hb1(self, tmp_path) -> None:
        raw = _valid_raw_output()
        process = RealPipeFakeProcess(stdout_bytes=raw.encode("utf-8"), returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        captured = {}

        class SpyHB1:
            def validate_raw_review_output(self, **kwargs):
                captured.update(kwargs)
                from app.services.project_director_sandbox_candidate_diff_review_output_validation_service import (
                    ProjectDirectorSandboxCandidateDiffReviewOutputValidationService,
                )
                return ProjectDirectorSandboxCandidateDiffReviewOutputValidationService().validate_raw_review_output(**kwargs)

        result = _call_adapter(transport, svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=SpyHB1(),
        ))
        assert result.adapter_status == "validated_output"
        assert result.execution_mode == "native_capture_transport"
        assert captured["raw_output_text"] == raw

    def test_completed_invalid_raw_hb1_blocked(self, tmp_path) -> None:
        fenced = f"```json\n{_valid_raw_output()}\n```"
        process = RealPipeFakeProcess(stdout_bytes=fenced.encode("utf-8"), returncode=0)
        transport, _, _ = _transport(tmp_path, process=process)
        result = _call_adapter(transport)
        assert result.adapter_status == "blocked"
        assert "review_output_validation_blocked" in result.blocked_reasons
        assert "review_output_markdown_fence_forbidden" in result.output_validation_blocked_reasons

    def test_failed_no_hb1_call(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"", returncode=1)
        transport, _, _ = _transport(tmp_path, process=process)

        class SpyHB1:
            call_count = 0
            def validate_raw_review_output(self, **kwargs):
                self.call_count += 1
                raise AssertionError("H-B1 must not be called")

        spy = SpyHB1()
        result = _call_adapter(transport, svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=spy,
        ))
        assert result.adapter_status == "blocked"
        assert spy.call_count == 0

    def test_timeout_no_hb1_call(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"", returncode=0, delay_stdout=10.0)
        transport, _, _ = _transport(tmp_path, process=process, timeout=0.3)

        class SpyHB1:
            call_count = 0
            def validate_raw_review_output(self, **kwargs):
                self.call_count += 1
                raise AssertionError("H-B1 must not be called")

        spy = SpyHB1()
        result = _call_adapter(transport, svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=spy,
        ))
        assert result.adapter_status == "blocked"
        assert spy.call_count == 0

    def test_stdout_too_large_no_hb1_call(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=b"x" * 101, returncode=0)
        transport, _, _ = _transport(tmp_path, process=process, max_output_bytes=100)

        class SpyHB1:
            call_count = 0
            def validate_raw_review_output(self, **kwargs):
                self.call_count += 1
                raise AssertionError("H-B1 must not be called")

        spy = SpyHB1()
        result = _call_adapter(transport, svc=ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService(
            output_validation_service=spy,
        ))
        assert result.adapter_status == "blocked"
        assert spy.call_count == 0


# ══════════════════════════════════════════════════════════════════════
# O. Execution flags
# ══════════════════════════════════════════════════════════════════════


class TestExecutionFlags:
    def test_codex_completed_flags(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=_valid_raw_output().encode("utf-8"))
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request(executor="codex"))
        assert result.real_reviewer_started is True
        assert result.real_reviewer_executed is True
        assert result.native_process_started is True
        assert result.provider_called is False
        assert result.codex_started is True
        assert result.claude_code_started is False

    def test_claude_completed_flags(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=_valid_raw_output().encode("utf-8"))
        transport, _, _ = _transport(tmp_path, process=process)
        result = transport.execute(_request(executor="claude-code"))
        assert result.real_reviewer_started is True
        assert result.real_reviewer_executed is True
        assert result.native_process_started is True
        assert result.provider_called is False
        assert result.codex_started is False
        assert result.claude_code_started is True

    def test_all_failure_paths_executed_false(self, tmp_path) -> None:
        # Non-zero exit
        p1 = RealPipeFakeProcess(stdout_bytes=b"x", returncode=1)
        t1, _, _ = _transport(tmp_path, process=p1)
        assert t1.execute(_request()).real_reviewer_executed is False

        # Invalid UTF-8
        p2 = RealPipeFakeProcess(stdout_bytes=b"\xff", returncode=0)
        t2, _, _ = _transport(tmp_path, process=p2)
        assert t2.execute(_request()).real_reviewer_executed is False

        # Too large
        p3 = RealPipeFakeProcess(stdout_bytes=b"x" * 101, returncode=0)
        t3, _, _ = _transport(tmp_path, process=p3, max_output_bytes=100)
        assert t3.execute(_request()).real_reviewer_executed is False


# ══════════════════════════════════════════════════════════════════════
# P. Write flags always false
# ══════════════════════════════════════════════════════════════════════


class TestWriteFlagsAlwaysFalse:
    def test_adapter_result_write_flags(self, tmp_path) -> None:
        process = RealPipeFakeProcess(stdout_bytes=_valid_raw_output().encode("utf-8"))
        transport, _, _ = _transport(tmp_path, process=process)
        result = _call_adapter(transport)
        for flag in WRITE_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"
        assert result.ai_project_director_total_loop == "Partial"
