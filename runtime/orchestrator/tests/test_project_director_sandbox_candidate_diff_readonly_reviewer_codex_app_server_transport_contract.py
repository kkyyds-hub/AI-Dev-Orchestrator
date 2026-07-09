"""Contract tests for P21-C-H-B2-C1 Codex app-server readonly reviewer transport."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from app.external_executors.actual_process_supervisor import RealExecutorProcessSupervisor
from app.external_executors.readonly_reviewer_codex_app_server_transport import (
    CodexAppServerReadonlyReviewerTransport,
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


PROMPT = "Reply with exactly OK."
SCOPE = ["src/example.py"]
WRITE_FLAGS = [
    "main_project_file_written", "sandbox_file_written", "manifest_file_written",
    "diff_file_written", "patch_applied", "git_write_performed",
    "worktree_created", "worker_started", "task_created", "run_created",
]


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


# ── Fake app-server script builder ─────────────────────────────────


def _fake_app_server_script(
    *,
    protocol_stages: list[dict[str, Any]] | None = None,
    agent_messages: list[dict[str, Any]] | None = None,
    turn_completed_status: str = "completed",
    initialize_error: bool = False,
    thread_start_error: bool = False,
    turn_start_error: bool = False,
    thread_ephemeral: bool = False,
    thread_id: str = "fake-thread-id-001",
    eof_before_initialize: bool = False,
    eof_before_turn_completed: bool = False,
    invalid_utf8: bool = False,
    invalid_json: bool = False,
    non_dict_json: bool = False,
    oversized_line: bool = False,
    stdout_delays: list[float] | None = None,
    never_read_stdin: bool = False,
) -> str:
    """Generate a Python script that acts as a fake app-server."""
    lines = ["import json, sys, time, os\n"]

    if never_read_stdin:
        lines.append("# Never read stdin\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    if invalid_utf8:
        lines.append("sys.stdout.buffer.write(b'\\xff\\xfe\\n')\n")
        lines.append("sys.stdout.buffer.flush()\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    if invalid_json:
        lines.append("sys.stdout.write('not json\\n')\n")
        lines.append("sys.stdout.flush()\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    if non_dict_json:
        lines.append("sys.stdout.write('[1,2,3]\\n')\n")
        lines.append("sys.stdout.flush()\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    if oversized_line:
        lines.append(f"sys.stdout.write('\"' + 'x' * {1024 * 1024 + 10} + '\"\\n')\n")
        lines.append("sys.stdout.flush()\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    if eof_before_initialize:
        # Use real FD close for reliable EOF detection
        lines.append("sys.stdout.flush()\n")
        lines.append("os.close(1)\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    # Normal interactive protocol
    delays_json = json.dumps(stdout_delays or [])
    lines.append(textwrap.dedent(f"""\
delay_idx = 0
delays = {delays_json}

def send(obj):
    if delays:
        global delay_idx
        if delay_idx < len(delays):
            time.sleep(delays[delay_idx])
            delay_idx += 1
    sys.stdout.write(json.dumps(obj) + '\\n')
    sys.stdout.flush()

def recv():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)
"""))

    # Initialize
    if initialize_error:
        lines.append("req = recv()\n")
        lines.append('send({"id": req["id"], "error": {"code": -1, "message": "init failed"}})\n')
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    lines.append("req = recv()  # initialize\n")
    lines.append(f'send({{"id": req["id"], "result": {{"userAgent": "fake/1.0"}}}})\n')

    # initialized (no response needed)
    lines.append("recv()  # initialized\n")

    # thread/start
    if thread_start_error:
        lines.append("req = recv()\n")
        lines.append('send({"id": req["id"], "error": {"code": -2, "message": "thread failed"}})\n')
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    lines.append("req = recv()  # thread/start\n")
    ephemeral_str = "True" if thread_ephemeral else "False"
    lines.append(
        f"send({{'id': req[\"id\"], 'result': {{'thread': {{'id': '{thread_id}', 'ephemeral': {ephemeral_str}}}, 'modelProvider': 'codex'}}}})\n"
    )

    if eof_before_turn_completed:
        # turn/start response then real FD EOF
        lines.append("req = recv()  # turn/start\n")
        lines.append('send({"id": req["id"], "result": {"status": "started"}})\n')
        lines.append("sys.stdout.flush()\n")
        lines.append("os.close(1)\n")
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    # turn/start
    if turn_start_error:
        lines.append("req = recv()\n")
        lines.append('send({"id": req["id"], "error": {"code": -3, "message": "turn failed"}})\n')
        lines.append("time.sleep(30)\n")
        return "".join(lines)

    lines.append("req = recv()  # turn/start\n")
    lines.append('send({"id": req["id"], "result": {"status": "started"}})\n')

    # Agent messages - add default final_answer if none provided and turn will complete
    if not agent_messages and turn_completed_status == "completed":
        agent_messages = [
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "default ok"}}},
        ]
    if agent_messages:
        for msg in agent_messages:
            lines.append(f"send({json.dumps(msg)})\n")

    # turn/completed
    lines.append(f'send({{"method": "turn/completed", "params": {{"status": "{turn_completed_status}"}}}})\n')

    # Thread cleanup (only if not ephemeral)
    if not thread_ephemeral:
        lines.append("req = recv()  # thread/delete\n")
        lines.append('send({"id": req["id"], "result": {"success": True}})\n')

    # Wait for shutdown
    lines.append("time.sleep(30)\n")
    return "".join(lines)


def _write_script(tmp_path: Path, name: str, content: str) -> Path:
    script = tmp_path / name
    script.write_text(content)
    return script


def _popen_factory_for_script(script_path: Path):
    """Create a popen_factory that launches a Python script instead of codex."""
    def factory(argv, **kwargs):
        return subprocess.Popen(
            [sys.executable, "-u", str(script_path)],
            **{k: v for k, v in kwargs.items() if k != "close_fds"},
        )
    return factory


def _transport(tmp_path: Path, script_content: str, *,
               timeout=10.0, max_output_bytes=100_000,
               supervisor=None) -> tuple[CodexAppServerReadonlyReviewerTransport, Any, SpySupervisor]:
    script = _write_script(tmp_path, "fake_server.py", script_content)
    sup = supervisor or SpySupervisor()
    transport = CodexAppServerReadonlyReviewerTransport(
        workspace_path=str(tmp_path),
        timeout_seconds=timeout,
        max_output_bytes=max_output_bytes,
        process_supervisor=sup,
        popen_factory=_popen_factory_for_script(script),
    )
    return transport, script, sup


def _call_adapter(transport, *, prompt=PROMPT, svc=None):
    svc = svc or ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService()
    return svc.validate_review_output_through_transport(
        requested_reviewer_executor="codex",
        review_prompt_text=prompt,
        expected_review_prompt_sha256=_prompt_sha256(prompt),
        expected_review_prompt_bytes=_prompt_bytes(prompt),
        review_scope_paths=list(SCOPE),
        review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
        transport=transport,
    )


class SpySupervisor(RealExecutorProcessSupervisor):
    def __init__(self) -> None:
        super().__init__()
        self.register_calls = 0
        self.cleanup_calls = 0
        self.terminate_calls = 0
        self.kill_calls = 0

    def register(self, *args, **kwargs):
        self.register_calls += 1
        return super().register(*args, **kwargs)

    def cleanup(self, *args, **kwargs):
        self.cleanup_calls += 1
        return super().cleanup(*args, **kwargs)

    def terminate(self, *args, **kwargs):
        self.terminate_calls += 1
        return super().terminate(*args, **kwargs)

    def kill(self, *args, **kwargs):
        self.kill_calls += 1
        return super().kill(*args, **kwargs)


# ══════════════════════════════════════════════════════════════════════
# A. Real interactive small-line happy path
# ══════════════════════════════════════════════════════════════════════


class TestHappyPath:
    def test_small_jsonl_interactive(self, tmp_path) -> None:
        final_answer = '{"review_status":"reviewed","verdict":"no_blocking_findings","risk_level":"low","summary":"OK","findings":[],"recommended_next_step":"Proceed."}'
        script = _fake_app_server_script(
            agent_messages=[
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "commentary", "text": "thinking..."}}},
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "unphased", "text": "intermediate"}}},
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": final_answer}}},
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "unphased", "text": "ignored"}}},
            ],
        )
        transport, _, sup = _transport(tmp_path, script)
        result = transport.execute(_request())

        assert result.transport_status == "completed"
        assert result.transport_error_code is None
        assert result.raw_output_text == final_answer
        assert result.real_reviewer_started is True
        assert result.real_reviewer_executed is True
        assert result.native_process_started is True
        assert result.provider_called is False
        assert result.codex_started is True
        assert result.claude_code_started is False
        assert sup.snapshot().total_records == 0


# ══════════════════════════════════════════════════════════════════════
# B. Outbound protocol exactness
# ══════════════════════════════════════════════════════════════════════


class TestOutboundProtocol:
    def test_exact_message_order_and_content(self, tmp_path) -> None:
        """Verify the exact messages sent to the app-server."""
        captured_file = tmp_path / "captured.json"
        script_content = textwrap.dedent(f"""\
            import json, sys, pathlib
            def recv():
                line = sys.stdin.readline()
                if not line:
                    return None
                return json.loads(line)
            def send(obj):
                sys.stdout.write(json.dumps(obj) + '\\n')
                sys.stdout.flush()

            req = recv()  # initialize
            captured_init = req
            send({{"id": req["id"], "result": {{"userAgent": "fake"}}}})
            recv()  # initialized

            req = recv()  # thread/start
            captured_thread = req
            send({{"id": req["id"], "result": {{"thread": {{"id": "t-1", "ephemeral": False}}, "modelProvider": "codex"}}}})

            req = recv()  # turn/start
            captured_turn = req
            send({{"id": req["id"], "result": {{"status": "started"}}}})
            send({{"method": "item/completed", "params": {{"item": {{"type": "agentMessage", "phase": "final_answer", "text": "OK"}}}}}})
            send({{"method": "turn/completed", "params": {{"status": "completed"}}}})

            # Write captured before thread/delete (file write is more reliable here)
            pathlib.Path("{captured_file}").write_text(json.dumps({{
                "init": captured_init,
                "thread": captured_thread,
                "turn": captured_turn,
            }}))

            req = recv()  # thread/delete
            captured_delete = req
            send({{"id": req["id"], "result": {{"success": True}}}})
            import time; time.sleep(30)
        """)
        script = _write_script(tmp_path, "fake_server.py", script_content)
        sup = SpySupervisor()
        transport = CodexAppServerReadonlyReviewerTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=15.0,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=_popen_factory_for_script(script),
        )
        result = transport.execute(_request(prompt="Test prompt."))
        assert result.transport_status == "completed"

        # Give child process time to flush file write
        time.sleep(0.5)

        # Read captured messages
        assert captured_file.exists(), f"Captured file not written: {captured_file}"
        captured = json.loads(captured_file.read_text())

        # Initialize
        init = captured["init"]
        assert init["id"] == 1
        assert init["method"] == "initialize"
        assert init["params"]["clientInfo"]["name"] == "ai_dev_orchestrator_readonly_reviewer"

        # Thread/start
        thread = captured["thread"]
        assert thread["id"] == 2
        assert thread["params"]["approvalPolicy"] == "never"
        assert thread["params"]["cwd"] == str(tmp_path)
        assert "model" not in thread["params"]

        # Turn/start
        turn = captured["turn"]
        assert turn["id"] == 3
        assert turn["params"]["approvalPolicy"] == "never"
        assert turn["params"]["sandboxPolicy"]["type"] == "readOnly"
        assert turn["params"]["input"][0]["text"] == "Test prompt."
        assert "model" not in turn["params"]

        # Thread/delete is still sent (verified by transport completing successfully)
        # but captured data only includes init/thread/turn (file written before delete)


# ══════════════════════════════════════════════════════════════════════
# C. Ephemeral thread
# ══════════════════════════════════════════════════════════════════════


class TestEphemeralThread:
    def test_ephemeral_no_delete(self, tmp_path) -> None:
        """When thread is ephemeral, thread/delete must not be sent."""
        captured_file = tmp_path / "captured.json"
        script_content = textwrap.dedent(f"""\
            import json, sys, pathlib
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            def send(obj):
                sys.stdout.write(json.dumps(obj) + '\\n')
                sys.stdout.flush()

            req = recv()
            send({{"id": req["id"], "result": {{"userAgent": "fake"}}}})
            recv()
            req = recv()
            send({{"id": req["id"], "result": {{"thread": {{"id": "t-eph", "ephemeral": True}}, "modelProvider": "codex"}}}})
            req = recv()
            send({{"id": req["id"], "result": {{"status": "started"}}}})
            send({{"method": "item/completed", "params": {{"item": {{"type": "agentMessage", "phase": "final_answer", "text": "OK"}}}}}})
            send({{"method": "turn/completed", "params": {{"status": "completed"}}}})
            # No thread/delete expected
            import time; time.sleep(2)
            pathlib.Path('{captured_file}').write_text('no_more_messages')
            time.sleep(30)
        """)
        script = _write_script(tmp_path, "fake_server.py", script_content)
        sup = SpySupervisor()
        transport = CodexAppServerReadonlyReviewerTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=10.0,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=_popen_factory_for_script(script),
        )
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        # If ephemeral, no thread/delete was sent, so the script would have written the file
        # indicating no more messages were expected
        time.sleep(1)
        if captured_file.exists():
            assert captured_file.read_text() == "no_more_messages"


# ══════════════════════════════════════════════════════════════════════
# D. Authoritative output selection
# ══════════════════════════════════════════════════════════════════════


class TestOutputSelection:
    def _run_with_messages(self, tmp_path, messages, turn_status="completed"):
        script = _fake_app_server_script(
            agent_messages=messages,
            turn_completed_status=turn_status,
        )
        transport, _, _ = _transport(tmp_path, script)
        return transport.execute(_request())

    def test_final_answer_priority(self, tmp_path) -> None:
        r = self._run_with_messages(tmp_path, [
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "commentary", "text": "commentary"}}},
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "unphased", "text": "unphased-1"}}},
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "THE ANSWER"}}},
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "unphased", "text": "unphased-2"}}},
        ])
        assert r.raw_output_text == "THE ANSWER"

    def test_unphased_fallback(self, tmp_path) -> None:
        # Implementation treats items without phase field as "unphased"
        r = self._run_with_messages(tmp_path, [
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": "unphased-1"}}},
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "commentary", "text": "commentary"}}},
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": "LAST_UNPHASED"}}},
        ])
        assert r.raw_output_text == "LAST_UNPHASED"

    def test_only_commentary_missing(self, tmp_path) -> None:
        """Only commentary messages → output_missing (no final_answer or unphased)."""
        script_content = textwrap.dedent("""\
            import json, sys, time
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            def send(obj):
                sys.stdout.write(json.dumps(obj) + '\\n')
                sys.stdout.flush()

            req = recv()
            send({"id": req["id"], "result": {"userAgent": "fake"}})
            recv()
            req = recv()
            send({"id": req["id"], "result": {"thread": {"id": "t-1", "ephemeral": True}, "modelProvider": "codex"}})
            req = recv()
            send({"id": req["id"], "result": {"status": "started"}})
            send({"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "commentary", "text": "thinking"}}})
            send({"method": "turn/completed", "params": {"status": "completed"}})
            time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_output_missing"

    def test_raw_output_no_strip(self, tmp_path) -> None:
        raw = "  \n```json\n{\"ok\":true}\n```\n  "
        r = self._run_with_messages(tmp_path, [
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": raw}}},
        ])
        assert r.raw_output_text == raw


# ══════════════════════════════════════════════════════════════════════
# E. JSONL framing
# ══════════════════════════════════════════════════════════════════════


class TestJSONLFraming:
    def test_fragmented_jsonl(self, tmp_path) -> None:
        """One JSONL split across multiple OS writes."""
        script_content = textwrap.dedent("""\
            import json, sys, time
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            def send(obj):
                data = json.dumps(obj) + '\\n'
                # Write in small chunks
                for i in range(0, len(data), 10):
                    sys.stdout.write(data[i:i+10])
                    sys.stdout.flush()
            req = recv()
            send({"id": req["id"], "result": {"userAgent": "fake"}})
            recv()
            req = recv()
            send({"id": req["id"], "result": {"thread": {"id": "t-1", "ephemeral": True}, "modelProvider": "codex"}})
            req = recv()
            send({"id": req["id"], "result": {"status": "started"}})
            send({"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "fragmented ok"}}})
            send({"method": "turn/completed", "params": {"status": "completed"}})
            time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.raw_output_text == "fragmented ok"

    def test_multi_line_single_chunk(self, tmp_path) -> None:
        """Multiple JSONL lines in one OS write."""
        script_content = textwrap.dedent("""\
            import json, sys, time
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            req = recv()
            # Send multiple lines in one write
            lines = [
                json.dumps({"id": req["id"], "result": {"userAgent": "fake"}}),
                json.dumps({"id": 999, "result": "noise"}),
            ]
            sys.stdout.write('\\n'.join(lines) + '\\n')
            sys.stdout.flush()
            recv()
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"thread": {"id": "t-1", "ephemeral": True}, "modelProvider": "codex"}}) + '\\n')
            sys.stdout.flush()
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"status": "started"}}) + '\\n')
            sys.stdout.flush()
            sys.stdout.write(json.dumps({"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "multi ok"}}}) + '\\n')
            sys.stdout.write(json.dumps({"method": "turn/completed", "params": {"status": "completed"}}) + '\\n')
            sys.stdout.flush()
            time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.raw_output_text == "multi ok"

    def test_incomplete_json_eof(self, tmp_path) -> None:
        """Last line incomplete JSON without newline → protocol failed."""
        script_content = textwrap.dedent("""\
            import json, sys, os
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"userAgent": "fake"}}) + '\\n')
            sys.stdout.flush()
            recv()
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"thread": {"id": "t-1", "ephemeral": True}, "modelProvider": "codex"}}) + '\\n')
            sys.stdout.flush()
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"status": "started"}}) + '\\n')
            sys.stdout.flush()
            # Write incomplete JSON without newline then real FD EOF
            sys.stdout.write('{"method": "turn/completed", "params": {"status": "completed"')
            sys.stdout.flush()
            os.close(1)
            import time; time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content, timeout=5.0)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_protocol_failed"


# ══════════════════════════════════════════════════════════════════════
# F. Small-line reader regression
# ══════════════════════════════════════════════════════════════════════


class TestSmallLineRegression:
    def test_small_line_does_not_block(self, tmp_path) -> None:
        """Small JSONL response must not block reader waiting for 8192 bytes."""
        script_content = textwrap.dedent("""\
            import json, sys, time
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            req = recv()
            # Send a very small response
            sys.stdout.write('{"id":1,"result":{"userAgent":"tiny"}}\\n')
            sys.stdout.flush()
            # Wait for next request
            recv()
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"thread": {"id": "t-1", "ephemeral": True}, "modelProvider": "codex"}}) + '\\n')
            sys.stdout.flush()
            req = recv()
            sys.stdout.write(json.dumps({"id": req["id"], "result": {"status": "started"}}) + '\\n')
            sys.stdout.flush()
            sys.stdout.write(json.dumps({"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "small ok"}}}) + '\\n')
            sys.stdout.write(json.dumps({"method": "turn/completed", "params": {"status": "completed"}}) + '\\n')
            sys.stdout.flush()
            time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content, timeout=5.0)

        # Run in thread with watchdog
        result_holder: dict[str, Any] = {}

        def run():
            result_holder["result"] = transport.execute(_request())

        t = threading.Thread(target=run)
        t.start()
        t.join(timeout=8.0)
        assert not t.is_alive(), "Test deadlocked on small line read"
        assert "result" in result_holder
        assert result_holder["result"].transport_status == "completed"


# ══════════════════════════════════════════════════════════════════════
# G. EOF fast failure
# ══════════════════════════════════════════════════════════════════════


class TestEOFFastFailure:
    def test_eof_before_initialize(self, tmp_path) -> None:
        """EOF before any response → failed with protocol_failed."""
        script = _fake_app_server_script(eof_before_initialize=True)
        transport, _, _ = _transport(tmp_path, script, timeout=5.0)
        start = time.monotonic()
        result = transport.execute(_request())
        elapsed = time.monotonic() - start
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_protocol_failed"
        assert elapsed < 2.0, f"Should fail fast, took {elapsed:.1f}s"

    def test_eof_before_turn_completed(self, tmp_path) -> None:
        script = _fake_app_server_script(eof_before_turn_completed=True)
        transport, _, _ = _transport(tmp_path, script, timeout=5.0)
        start = time.monotonic()
        result = transport.execute(_request())
        elapsed = time.monotonic() - start
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_protocol_failed"
        assert elapsed < 2.0, f"Should fail fast, took {elapsed:.1f}s"


# ══════════════════════════════════════════════════════════════════════
# H. Protocol failures
# ══════════════════════════════════════════════════════════════════════


class TestProtocolFailures:
    def test_invalid_utf8(self, tmp_path) -> None:
        script = _fake_app_server_script(invalid_utf8=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdout_invalid_utf8"

    def test_invalid_json(self, tmp_path) -> None:
        script = _fake_app_server_script(invalid_json=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_protocol_failed"

    def test_non_dict_json(self, tmp_path) -> None:
        script = _fake_app_server_script(non_dict_json=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_protocol_failed"

    def test_oversized_line(self, tmp_path) -> None:
        script = _fake_app_server_script(oversized_line=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_protocol_too_large"


# ══════════════════════════════════════════════════════════════════════
# I. Request/response failures
# ══════════════════════════════════════════════════════════════════════


class TestRequestResponseFailures:
    def test_initialize_error(self, tmp_path) -> None:
        script = _fake_app_server_script(initialize_error=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_initialize_failed"

    def test_thread_start_error(self, tmp_path) -> None:
        script = _fake_app_server_script(thread_start_error=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_thread_start_failed"

    def test_turn_start_error(self, tmp_path) -> None:
        script = _fake_app_server_script(turn_start_error=True)
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        # Turn start error may be overridden by thread cleanup failure
        assert result.transport_error_code in (
            "reviewer_codex_app_server_turn_failed",
            "reviewer_codex_app_server_thread_cleanup_failed",
        )


# ══════════════════════════════════════════════════════════════════════
# J. Turn terminal states
# ══════════════════════════════════════════════════════════════════════


class TestTurnTerminalStates:
    def test_turn_failed(self, tmp_path) -> None:
        script = _fake_app_server_script(turn_completed_status="failed")
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_turn_failed"
        assert result.real_reviewer_started is True
        assert result.real_reviewer_executed is False

    def test_turn_error(self, tmp_path) -> None:
        script = _fake_app_server_script(turn_completed_status="error")
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_turn_failed"

    def test_turn_interrupted(self, tmp_path) -> None:
        script = _fake_app_server_script(turn_completed_status="interrupted")
        transport, _, _ = _transport(tmp_path, script)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_turn_interrupted"
        assert result.real_reviewer_started is True
        assert result.real_reviewer_executed is False


# ══════════════════════════════════════════════════════════════════════
# K. Output byte bound
# ══════════════════════════════════════════════════════════════════════


class TestOutputByteBound:
    def test_output_too_large(self, tmp_path) -> None:
        big_text = "x" * 101
        script = _fake_app_server_script(
            agent_messages=[
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": big_text}}},
            ],
        )
        transport, _, _ = _transport(tmp_path, script, max_output_bytes=100)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdout_too_large"
        assert result.raw_output_text == ""
        assert result.real_reviewer_executed is False

    def test_exact_limit_ok(self, tmp_path) -> None:
        text = "a" * 100
        script = _fake_app_server_script(
            agent_messages=[
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": text}}},
            ],
        )
        transport, _, _ = _transport(tmp_path, script, max_output_bytes=100)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert len(result.raw_output_text.encode("utf-8")) == 100


# ══════════════════════════════════════════════════════════════════════
# L. Thread cleanup contract
# ══════════════════════════════════════════════════════════════════════


class TestThreadCleanup:
    def test_non_ephemeral_delete_success(self, tmp_path) -> None:
        """Non-ephemeral thread triggers thread/delete and succeeds."""
        script_content = textwrap.dedent("""\
            import json, sys, time
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            def send(obj):
                sys.stdout.write(json.dumps(obj) + '\\n')
                sys.stdout.flush()

            req = recv()
            send({"id": req["id"], "result": {"userAgent": "fake"}})
            recv()
            req = recv()
            thread_id = "t-del-test"
            send({"id": req["id"], "result": {"thread": {"id": thread_id, "ephemeral": False}, "modelProvider": "codex"}})
            req = recv()
            send({"id": req["id"], "result": {"status": "started"}})
            send({"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "ok"}}})
            send({"method": "turn/completed", "params": {"status": "completed"}})
            req = recv()
            assert req["method"] == "thread/delete"
            assert req["params"]["threadId"] == thread_id
            send({"id": req["id"], "result": {"success": True}})
            time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content, timeout=15.0)
        result = transport.execute(_request())
        assert result.transport_status == "completed"
        assert result.transport_error_code is None

    def test_cleanup_failure(self, tmp_path) -> None:
        """Thread/delete returns error → cleanup failed."""
        script_content = textwrap.dedent("""\
            import json, sys, time
            def recv():
                line = sys.stdin.readline()
                return json.loads(line) if line else None
            def send(obj):
                sys.stdout.write(json.dumps(obj) + '\\n')
                sys.stdout.flush()

            req = recv()
            send({"id": req["id"], "result": {"userAgent": "fake"}})
            recv()
            req = recv()
            send({"id": req["id"], "result": {"thread": {"id": "t-1", "ephemeral": False}, "modelProvider": "codex"}})
            req = recv()
            send({"id": req["id"], "result": {"status": "started"}})
            send({"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "ok"}}})
            send({"method": "turn/completed", "params": {"status": "completed"}})
            # thread/delete returns error
            req = recv()
            send({"id": req["id"], "error": {"code": -1, "message": "delete failed"}})
            time.sleep(30)
        """)
        transport, _, _ = _transport(tmp_path, script_content)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_codex_app_server_thread_cleanup_failed"


# ══════════════════════════════════════════════════════════════════════
# M. Single total deadline
# ══════════════════════════════════════════════════════════════════════


class TestTotalDeadline:
    def test_cumulative_delay_exceeds_timeout(self, tmp_path) -> None:
        """Each stage delay < timeout, but cumulative > timeout.
        Delays are on stdout writes from child, so parent waits for responses.
        Must prove deadline is single total, not per-stage reset."""
        script = _fake_app_server_script(
            stdout_delays=[1.0, 1.0, 1.0, 1.0, 1.0],
        )
        transport, _, _ = _transport(tmp_path, script, timeout=3.0)
        start = time.monotonic()
        result = transport.execute(_request())
        elapsed = time.monotonic() - start
        assert result.transport_status == "timeout"
        assert result.transport_error_code == "reviewer_native_timeout"
        assert elapsed < 10.0


# ══════════════════════════════════════════════════════════════════════
# N. Writer failure
# ══════════════════════════════════════════════════════════════════════


class TestWriterFailure:
    def test_stdin_write_failure(self, tmp_path) -> None:
        """Broken stdin → deterministic reviewer_stdin_write_failed.
        Uses a fake stdin pipe that raises BrokenPipeError on write."""
        script_content = textwrap.dedent("""\
            import sys, time
            # Close stdin to trigger BrokenPipeError on parent write
            sys.stdin.close()
            time.sleep(30)
        """)
        transport, _, sup = _transport(tmp_path, script_content, timeout=5.0)

        # Replace popen_factory to inject a fake stdin that raises BrokenPipeError
        class FakeStdin:
            closed = False
            def write(self, data):
                raise BrokenPipeError("broken pipe")
            def flush(self):
                pass
            def close(self):
                self.closed = True

        original_factory = transport._popen_factory

        def patched_factory(argv, **kwargs):
            proc = original_factory(argv, **kwargs)
            proc.stdin = FakeStdin()
            return proc

        transport._popen_factory = patched_factory
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdin_write_failed"
        assert sup.snapshot().total_records == 0


# ══════════════════════════════════════════════════════════════════════
# O. Writer backpressure timeout
# ══════════════════════════════════════════════════════════════════════


class TestWriterBackpressure:
    def test_backpressure_timeout(self, tmp_path) -> None:
        """Child never reads stdin → writer blocks → timeout.
        Must also verify all threads are dead after."""
        import threading as _threading
        captured_threads: list[_threading.Thread] = []
        original_init = _threading.Thread.__init__

        def capturing_init(self, *args, **kw):
            original_init(self, *args, **kw)
            captured_threads.append(self)

        monkeypatch_ctx = pytest.MonkeyPatch()
        monkeypatch_ctx.setattr(_threading.Thread, "__init__", capturing_init)
        try:
            script = _fake_app_server_script(never_read_stdin=True)
            transport, _, sup = _transport(tmp_path, script, timeout=2.0)
            prompt = "X" * (1024 * 1024)  # 1 MiB prompt

            result_holder: dict[str, Any] = {}

            def run():
                result_holder["result"] = transport.execute(_request(prompt=prompt))

            t = threading.Thread(target=run)
            t.start()
            t.join(timeout=10.0)
            assert not t.is_alive(), "Test deadlocked"
            assert "result" in result_holder
            result = result_holder["result"]
            assert result.transport_status == "timeout"
            assert result.transport_error_code == "reviewer_native_timeout"
            # Join captured threads
            for ct in captured_threads:
                ct.join(timeout=2.0)
            assert all(not ct.is_alive() for ct in captured_threads), "Threads still alive after backpressure timeout"
            assert sup.snapshot().total_records == 0
        finally:
            monkeypatch_ctx.undo()


# ══════════════════════════════════════════════════════════════════════
# P. Reader/writer thread cleanup
# ══════════════════════════════════════════════════════════════════════


class _ProcessProxy:
    """Lightweight proxy over a real Popen that counts direct terminate/kill calls."""

    def __init__(self, proc: subprocess.Popen) -> None:
        object.__setattr__(self, "_proc", proc)
        object.__setattr__(self, "direct_terminate_calls", 0)
        object.__setattr__(self, "direct_kill_calls", 0)

    def terminate(self) -> None:
        object.__setattr__(self, "direct_terminate_calls", self.direct_terminate_calls + 1)
        self._proc.terminate()

    def kill(self) -> None:
        object.__setattr__(self, "direct_kill_calls", self.direct_kill_calls + 1)
        self._proc.kill()

    def wait(self, timeout=None):
        return self._proc.wait(timeout=timeout)

    def poll(self):
        return self._proc.poll()

    @property
    def stdin(self):
        return self._proc.stdin

    @stdin.setter
    def stdin(self, value):
        self._proc.stdin = value

    @property
    def stdout(self):
        return self._proc.stdout

    @property
    def stderr(self):
        return self._proc.stderr

    @property
    def pid(self):
        return self._proc.pid

    @property
    def returncode(self):
        return self._proc.returncode

    def __getattr__(self, name):
        return getattr(self._proc, name)


class TestThreadCleanupLifecycle:
    def _execute_with_thread_capture(self, tmp_path, script_content, *, timeout=10.0,
                                     popen_factory=None, supervisor=None, **kwargs):
        """Execute transport while capturing all threading.Thread objects."""
        import threading as _threading
        captured_threads: list[_threading.Thread] = []
        original_init = _threading.Thread.__init__

        def capturing_init(self, *args, **kw):
            original_init(self, *args, **kw)
            captured_threads.append(self)

        monkeypatch_ctx = pytest.MonkeyPatch()
        monkeypatch_ctx.setattr(_threading.Thread, "__init__", capturing_init)
        try:
            script = _write_script(tmp_path, "fake_server.py", script_content)
            sup = supervisor or SpySupervisor()
            factory = popen_factory or _popen_factory_for_script(script)
            transport = CodexAppServerReadonlyReviewerTransport(
                workspace_path=str(tmp_path),
                timeout_seconds=timeout,
                max_output_bytes=100_000,
                process_supervisor=sup,
                popen_factory=factory,
            )
            result = transport.execute(_request())
            # Give threads time to finish
            for t in captured_threads:
                t.join(timeout=2.0)
            return result, captured_threads, sup
        finally:
            monkeypatch_ctx.undo()

    def test_success_threads_not_alive(self, tmp_path) -> None:
        script = _fake_app_server_script(thread_ephemeral=True)
        result, threads, sup = self._execute_with_thread_capture(tmp_path, script)
        assert result.transport_status == "completed"
        assert all(not t.is_alive() for t in threads), "Threads still alive after success"
        assert sup.snapshot().total_records == 0

    def test_timeout_threads_not_alive(self, tmp_path) -> None:
        script = _fake_app_server_script(never_read_stdin=True)
        result, threads, sup = self._execute_with_thread_capture(tmp_path, script, timeout=1.0)
        assert result.transport_status == "timeout"
        assert all(not t.is_alive() for t in threads), "Threads still alive after timeout"
        assert sup.snapshot().total_records == 0

    def test_writer_failure_threads_not_alive(self, tmp_path) -> None:
        script = _fake_app_server_script(never_read_stdin=True)

        class FakeStdin:
            closed = False
            def write(self, data):
                raise BrokenPipeError("broken pipe")
            def flush(self):
                pass
            def close(self):
                self.closed = True

        original_factory = _popen_factory_for_script(
            _write_script(tmp_path, "fake_server_writer.py", script),
        )

        def broken_stdin_factory(argv, **kwargs):
            proc = original_factory(argv, **kwargs)
            proc.stdin = FakeStdin()
            return proc

        result, threads, sup = self._execute_with_thread_capture(
            tmp_path, script, timeout=5.0, popen_factory=broken_stdin_factory,
        )
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_stdin_write_failed"
        assert all(not t.is_alive() for t in threads), "Threads still alive after writer failure"
        assert sup.snapshot().total_records == 0

    def test_protocol_failure_threads_not_alive(self, tmp_path) -> None:
        script = _fake_app_server_script(invalid_json=True)
        result, threads, sup = self._execute_with_thread_capture(tmp_path, script)
        assert result.transport_status == "failed"
        assert all(not t.is_alive() for t in threads), "Threads still alive after protocol failure"


# ══════════════════════════════════════════════════════════════════════
# Q. Process supervisor cleanup
# ══════════════════════════════════════════════════════════════════════


class TestSupervisorCleanup:
    def test_register_failure(self, tmp_path) -> None:
        class FailingSupervisor(SpySupervisor):
            def register(self, *args, **kwargs):
                self.register_calls += 1
                raise RuntimeError("register failed")

        script = _fake_app_server_script()
        sup = FailingSupervisor()
        transport, _, _ = _transport(tmp_path, script, supervisor=sup)
        result = transport.execute(_request())
        assert result.transport_status == "failed"
        assert result.transport_error_code == "reviewer_native_failed"

    def test_supervisor_terminate_fallback(self, tmp_path) -> None:
        """When supervisor.terminate fails, direct process.terminate is called."""
        class TerminateFailingSupervisor(SpySupervisor):
            def terminate(self, *args, **kwargs):
                self.terminate_calls += 1
                raise RuntimeError("terminate failed")

        script = _fake_app_server_script(never_read_stdin=True)
        sup = TerminateFailingSupervisor()
        proxy_holder: list[_ProcessProxy] = []

        def proxy_factory(argv, **kwargs):
            proc = subprocess.Popen(
                [sys.executable, "-u", str(_write_script(tmp_path, "f.py", script))],
                **{k: v for k, v in kwargs.items() if k != "close_fds"},
            )
            proxy = _ProcessProxy(proc)
            proxy_holder.append(proxy)
            return proxy

        transport = CodexAppServerReadonlyReviewerTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=1.0,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=proxy_factory,
        )
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert result.transport_error_code == "reviewer_native_timeout"
        assert sup.terminate_calls >= 1, "Supervisor terminate must be attempted"
        assert proxy_holder, "Proxy must have been created"
        assert proxy_holder[0].direct_terminate_calls >= 1, "Direct terminate must be called on fallback"
        assert sup.snapshot().total_records == 0

    def test_supervisor_terminate_returns_failure_fallback(self, tmp_path) -> None:
        """When supervisor.terminate returns action_success=False, direct terminate is called."""
        class TerminateReturnsFailureSupervisor(SpySupervisor):
            def terminate(self, *args, **kwargs):
                self.terminate_calls += 1
                from app.external_executors.actual_process_supervisor import (
                    RealExecutorProcessActionResult,
                    RealExecutorProcessStatus,
                )
                return RealExecutorProcessActionResult(
                    process_handle_id=args[0] if args else "unknown",
                    status=RealExecutorProcessStatus.TERMINATED,
                    action_success=False,
                )

        script = _fake_app_server_script(never_read_stdin=True)
        sup = TerminateReturnsFailureSupervisor()
        proxy_holder: list[_ProcessProxy] = []

        def proxy_factory(argv, **kwargs):
            proc = subprocess.Popen(
                [sys.executable, "-u", str(_write_script(tmp_path, "f.py", script))],
                **{k: v for k, v in kwargs.items() if k != "close_fds"},
            )
            proxy = _ProcessProxy(proc)
            proxy_holder.append(proxy)
            return proxy

        transport = CodexAppServerReadonlyReviewerTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=1.0,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=proxy_factory,
        )
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert result.transport_error_code == "reviewer_native_timeout"
        assert sup.terminate_calls >= 1
        assert proxy_holder
        assert proxy_holder[0].direct_terminate_calls >= 1, "Direct terminate must be called on fallback"
        assert sup.snapshot().total_records == 0

    def test_supervisor_kill_fallback(self, tmp_path) -> None:
        """When terminate fails and wait times out, direct kill is called.
        Uses a real child process that ignores SIGTERM."""
        script_content = textwrap.dedent("""\
            import signal, time
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(60)
        """)
        script = _write_script(tmp_path, "unkillable.py", script_content)

        class KillFailingSupervisor(SpySupervisor):
            def terminate(self, *args, **kwargs):
                self.terminate_calls += 1
                raise RuntimeError("terminate failed")
            def kill(self, *args, **kwargs):
                self.kill_calls += 1
                raise RuntimeError("kill failed")

        sup = KillFailingSupervisor()
        proxy_holder: list[_ProcessProxy] = []

        def proxy_factory(argv, **kwargs):
            proc = subprocess.Popen(
                [sys.executable, "-u", str(script)],
                **{k: v for k, v in kwargs.items() if k != "close_fds"},
            )
            proxy = _ProcessProxy(proc)
            proxy_holder.append(proxy)
            return proxy

        transport = CodexAppServerReadonlyReviewerTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=2.0,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=proxy_factory,
            terminate_wait_seconds=0.5,
        )
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert result.transport_error_code == "reviewer_native_timeout"
        assert sup.terminate_calls >= 1
        assert sup.kill_calls >= 1, "Kill must be attempted when terminate fails and wait times out"
        assert proxy_holder
        assert proxy_holder[0].direct_kill_calls >= 1, "Direct kill must be called on fallback"
        assert sup.snapshot().total_records == 0
        assert proxy_holder[0].poll() is not None, "Child process must have exited"

    def test_supervisor_kill_returns_failure_fallback(self, tmp_path) -> None:
        """When supervisor.kill returns action_success=False, direct process.kill() is called.
        Uses a real SIGTERM-immune child so wait actually times out."""
        script_content = textwrap.dedent("""\
            import signal, time
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(60)
        """)
        script = _write_script(tmp_path, "unkillable2.py", script_content)

        class KillReturnsFailureSupervisor(SpySupervisor):
            def terminate(self, *args, **kwargs):
                self.terminate_calls += 1
                raise RuntimeError("terminate failed")
            def kill(self, *args, **kwargs):
                self.kill_calls += 1
                from app.external_executors.actual_process_supervisor import (
                    RealExecutorProcessActionResult,
                    RealExecutorProcessStatus,
                )
                return RealExecutorProcessActionResult(
                    process_handle_id=args[0] if args else "unknown",
                    status=RealExecutorProcessStatus.TERMINATED,
                    action_success=False,
                )

        sup = KillReturnsFailureSupervisor()
        proxy_holder: list[_ProcessProxy] = []

        def proxy_factory(argv, **kwargs):
            proc = subprocess.Popen(
                [sys.executable, "-u", str(script)],
                **{k: v for k, v in kwargs.items() if k != "close_fds"},
            )
            proxy = _ProcessProxy(proc)
            proxy_holder.append(proxy)
            return proxy

        transport = CodexAppServerReadonlyReviewerTransport(
            workspace_path=str(tmp_path),
            timeout_seconds=2.0,
            max_output_bytes=100_000,
            process_supervisor=sup,
            popen_factory=proxy_factory,
            terminate_wait_seconds=0.5,
        )
        result = transport.execute(_request())
        assert result.transport_status == "timeout"
        assert result.transport_error_code == "reviewer_native_timeout"
        assert sup.terminate_calls >= 1
        assert sup.kill_calls >= 1, "Kill must be attempted when supervisor.kill returns failure"
        assert proxy_holder
        assert proxy_holder[0].direct_kill_calls >= 1, "Direct kill must be called when supervisor.kill returns failure"
        assert sup.snapshot().total_records == 0
        assert proxy_holder[0].poll() is not None, "Child process must have exited"


# ══════════════════════════════════════════════════════════════════════
# R. Constructor / executor boundary
# ══════════════════════════════════════════════════════════════════════


class TestConstructorBoundary:
    def test_rejects_relative_workspace(self) -> None:
        with pytest.raises(ValueError, match="workspace_path must be absolute"):
            CodexAppServerReadonlyReviewerTransport(
                workspace_path="relative", timeout_seconds=1.0,
                max_output_bytes=1000, process_supervisor=SpySupervisor(),
                popen_factory=lambda **kw: None,
            )

    def test_rejects_zero_timeout(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            CodexAppServerReadonlyReviewerTransport(
                workspace_path=str(tmp_path), timeout_seconds=0,
                max_output_bytes=1000, process_supervisor=SpySupervisor(),
                popen_factory=lambda **kw: None,
            )

    def test_rejects_zero_max_output(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="max_output_bytes must be positive"):
            CodexAppServerReadonlyReviewerTransport(
                workspace_path=str(tmp_path), timeout_seconds=1.0,
                max_output_bytes=0, process_supervisor=SpySupervisor(),
                popen_factory=lambda **kw: None,
            )

    def test_rejects_claude_code_executor(self, tmp_path) -> None:
        script = _fake_app_server_script()
        transport, _, _ = _transport(tmp_path, script)
        with pytest.raises(ValueError, match="not supported"):
            transport.execute(_request(executor="claude-code"))


# ══════════════════════════════════════════════════════════════════════
# S. Adapter → H-B1 integration
# ══════════════════════════════════════════════════════════════════════


class TestAdapterHB1Integration:
    def test_valid_output_through_adapter(self, tmp_path) -> None:
        raw = _valid_raw_output()
        script = _fake_app_server_script(
            agent_messages=[
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": raw}}},
            ],
        )
        transport, _, _ = _transport(tmp_path, script)
        result = _call_adapter(transport)

        assert result.adapter_status == "validated_output"
        assert result.transport_status == "completed"
        assert result.output_validation_status == "validated"
        assert result.strict_json_valid is True
        assert result.schema_valid is True
        assert result.semantics_valid is True
        assert result.evidence_scope_valid is True
        assert result.real_reviewer_started is True
        assert result.real_reviewer_executed is True
        assert result.codex_started is True
        assert result.claude_code_started is False
        assert result.provider_called is False
        for flag in WRITE_FLAGS:
            assert getattr(result, flag) is False, f"{flag} should be False"


# ══════════════════════════════════════════════════════════════════════
# T. Invalid H-B1 output
# ══════════════════════════════════════════════════════════════════════


class TestInvalidHB1Output:
    def test_markdown_fenced_json_blocked(self, tmp_path) -> None:
        fenced = f"```json\n{_valid_raw_output()}\n```"
        script = _fake_app_server_script(
            agent_messages=[
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": fenced}}},
            ],
        )
        transport, _, _ = _transport(tmp_path, script)
        result = _call_adapter(transport)
        assert result.adapter_status == "blocked"
        assert result.transport_status == "completed"
        assert result.output_validation_status == "blocked"
        assert "review_output_validation_blocked" in result.blocked_reasons

    def test_non_json_output_blocked(self, tmp_path) -> None:
        script = _fake_app_server_script(
            agent_messages=[
                {"method": "item/completed", "params": {"item": {"type": "agentMessage", "phase": "final_answer", "text": "not json at all"}}},
            ],
        )
        transport, _, _ = _transport(tmp_path, script)
        result = _call_adapter(transport)
        assert result.adapter_status == "blocked"
        assert result.transport_status == "completed"
        assert result.output_validation_status == "blocked"
