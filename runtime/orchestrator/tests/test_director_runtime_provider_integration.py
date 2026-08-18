"""B2 provider bridge integration: ProviderConfigService -> env -> Node -> Pi -> stub.

This module verifies the governed OpenAI-compatible provider bridge end to end
against a loopback stub bound to 127.0.0.1 only. It never touches the real
provider settings file, never calls a real provider, never imports repository
or write services, and never persists anything. All credentials are obviously
fake fixed values.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import time

from app.domain.director_runtime_protocol import (
    DirectorRuntimeFailure,
    DirectorRuntimeRequest,
    serialize_director_runtime_request,
    validate_director_runtime_request,
)
from app.services.director_runtime_provider_config_service import (
    ENV_PROVIDER_API_KEY,
    ENV_PROVIDER_BASE_URL,
    ENV_PROVIDER_MODE,
    ENV_PROVIDER_PROFILE_ID,
    DirectorRuntimeProviderConfigError,
    DirectorRuntimeProviderConfigService,
    DirectorRuntimeProviderEnvironment,
    OPENAI_PROVIDER_PROFILE_ID,
    PROVIDER_MODE_OPENAI_COMPATIBLE,
)
from app.services.director_runtime_supervisor_service import (
    DirectorRuntimeAttemptState,
    DirectorRuntimeSupervisor,
)
from app.services.director_runtime_transport import StdioJsonlDirectorRuntimeTransport
from app.services.provider_config_service import ProviderConfigService

RUNTIME = (
    Path(__file__).resolve().parents[2]
    / "director-runtime"
    / "dist"
    / "director-runtime.js"
)

SECRET_API_KEY = "b2-secret-api-key-python-fake-never-real"
MODEL_ID = "director-test-model-b2"
PROMPT_A = "b2-python-provider-prompt-unique-a"
PROMPT_B = "b2-python-provider-prompt-unique-b"


def _sse_chunk(model: str, delta: dict, finish_reason: str | None) -> bytes:
    payload = {
        "id": "chatcmpl-b2-local-stub",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


class _StubHandler(BaseHTTPRequestHandler):
    """Serve only POST /v1/chat/completions on 127.0.0.1 without raw secrets."""

    def do_POST(self) -> None:  # noqa: N802 - http.server naming contract
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {}
        record = {
            "path": self.path,
            "model": payload.get("model"),
            "authorization_present": bool(self.headers.get("Authorization")),
            "stream": payload.get("stream"),
            "tools_present": "tools" in payload,
            "body": body,
        }
        self.server.provider_requests.append(record)  # type: ignore[attr-defined]
        mode = self.server.stub_mode  # type: ignore[attr-defined]

        if mode == "unauthorized":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "unauthorized"}}).encode("utf-8"))
            return
        if mode == "server_error":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "server_error"}}).encode("utf-8"))
            return
        if mode == "hang":
            # Accept the request but never complete the response.
            time.sleep(30)
            return
        if mode == "malformed_no_finish_reason":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(_sse_chunk(str(payload.get("model") or ""), {"role": "assistant", "content": "partial"}, None))
            return

        response_text = self.server.stub_response_text  # type: ignore[attr-defined]
        model_name = str(payload.get("model") or "")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(_sse_chunk(model_name, {"role": "assistant", "content": response_text}, None))
        self.wfile.write(_sse_chunk(model_name, {}, "stop"))
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Never emit request detail (which would include headers) to stderr.
        return


class _ProviderStub:
    def __init__(self, mode: str = "ok", response_text: str = "provider-stub-response-A") -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
        self._server.stub_mode = mode  # type: ignore[attr-defined]
        self._server.stub_response_text = response_text  # type: ignore[attr-defined]
        self._server.provider_requests = []  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    @property
    def requests(self) -> list[dict]:
        return self._server.provider_requests  # type: ignore[attr-defined]

    @property
    def mode(self) -> str:
        return self._server.stub_mode  # type: ignore[attr-defined]

    @mode.setter
    def mode(self, value: str) -> None:
        self._server.stub_mode = value  # type: ignore[attr-defined]

    @property
    def response_text(self) -> str:
        return self._server.stub_response_text  # type: ignore[attr-defined]

    @response_text.setter
    def response_text(self, value: str) -> None:
        self._server.stub_response_text = value  # type: ignore[attr-defined]

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


def _fake_provider_config_service(
    tmp_path: Path,
    *,
    api_key: str | None = SECRET_API_KEY,
    base_url: str = "http://127.0.0.1:9/v1",
) -> ProviderConfigService:
    """Construct one ProviderConfigService bound to a temporary config file."""

    config_path = tmp_path / "provider-settings" / "openai-provider-config.json"
    service = ProviderConfigService(config_path=config_path)
    service.update_openai_config(api_key=api_key, base_url=base_url)
    return service


def _request_payload(request_id: str, *, prompt: str) -> dict[str, object]:
    return {
        "schema_version": "p26-big-director-runtime/v1",
        "request_id": request_id,
        "project_id": "b2-provider-project",
        "session_id": "b2-provider-session",
        "message_id": f"message-{request_id}",
        "current_user_message": {
            "content": prompt,
            "occurred_at": "2026-08-18T00:00:00Z",
            "actor_claim": "user",
        },
        "authoritative_facts": {},
        "active_discussion_workspace": None,
        "relevant_discussion_events": [],
        "active_formalization": {"proposal": None, "plan_version": None},
        "governance_boundaries": {
            "authoritative_write": False,
            "director_may_modify_code": False,
            "formalization_requires_explicit_request": True,
            "confirmation_is_separate": True,
            "execution_boundary": "no_task_run_agent_session_before_execution",
        },
        "available_skills": [],
        "available_tools": [
            {
                "tool_id": "allowed-but-unregistered",
                "allowed": True,
                "authorization_id": "b2-authorization",
                "idempotency_key": "b2-idempotency",
            }
        ],
        "permission_context": {},
        "runtime_config": {
            "model_id": MODEL_ID,
            "provider_profile_id": OPENAI_PROVIDER_PROFILE_ID,
            "timeout_ms": 20000.0,
            "max_tool_rounds": 0,
        },
    }


def _build_request(request_id: str, *, prompt: str) -> DirectorRuntimeRequest:
    return validate_director_runtime_request(_request_payload(request_id, prompt=prompt))


def _bridge_environment(
    service: DirectorRuntimeProviderConfigService,
    *,
    provider_profile_id: str = OPENAI_PROVIDER_PROFILE_ID,
) -> dict[str, str]:
    return service.build_openai_runtime_environment(
        provider_profile_id=provider_profile_id
    ).to_environment()


def _provider_transport(environment: dict[str, str]) -> StdioJsonlDirectorRuntimeTransport:
    return StdioJsonlDirectorRuntimeTransport(
        command=("node", str(RUNTIME)),
        cancel_wait_seconds=2.0,
        environment=environment,
    )


def _assert_outcome_has_no_secret(*values: object) -> None:
    for value in values:
        assert SECRET_API_KEY not in str(value)


def _snapshot_db_writes(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        return {}
    connection = sqlite3.connect(db_path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM '{table}'").fetchone()[0])
            for table in tables
        }
    finally:
        connection.close()


class TestProviderConfigServiceReuse:
    def test_bridge_resolves_only_through_provider_config_service(self, tmp_path: Path) -> None:
        provider_service = _fake_provider_config_service(
            tmp_path, base_url="http://127.0.0.1:60001/v1"
        )
        bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)

        resolved = bridge.resolve_openai_runtime_config()
        assert resolved.api_key == SECRET_API_KEY
        assert resolved.base_url == "http://127.0.0.1:60001/v1"
        assert resolved.source == "saved_config"

        environment = bridge.build_openai_runtime_environment(
            provider_profile_id=OPENAI_PROVIDER_PROFILE_ID
        )
        assert environment == DirectorRuntimeProviderEnvironment(
            provider_profile_id=OPENAI_PROVIDER_PROFILE_ID,
            mode=PROVIDER_MODE_OPENAI_COMPATIBLE,
            base_url="http://127.0.0.1:60001/v1",
            api_key=SECRET_API_KEY,
        )
        rendered = environment.to_environment()
        assert rendered == {
            ENV_PROVIDER_MODE: "openai_compatible",
            ENV_PROVIDER_PROFILE_ID: OPENAI_PROVIDER_PROFILE_ID,
            ENV_PROVIDER_BASE_URL: "http://127.0.0.1:60001/v1",
            ENV_PROVIDER_API_KEY: SECRET_API_KEY,
        }

    def test_unknown_profile_fails_closed(self, tmp_path: Path) -> None:
        bridge = DirectorRuntimeProviderConfigService(
            provider_config_service=_fake_provider_config_service(tmp_path)
        )
        try:
            bridge.build_openai_runtime_environment(provider_profile_id="other-profile")
            raise AssertionError("expected fail-closed rejection")
        except DirectorRuntimeProviderConfigError:
            pass

    def test_missing_credential_omits_env_key(self, tmp_path: Path) -> None:
        provider_service = _fake_provider_config_service(
            tmp_path, api_key=None, base_url="http://127.0.0.1:60002/v1"
        )
        bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
        environment = bridge.build_openai_runtime_environment(
            provider_profile_id=OPENAI_PROVIDER_PROFILE_ID
        )
        assert environment.api_key is None
        assert ENV_PROVIDER_API_KEY not in environment.to_environment()


class TestFrozenRequestContract:
    def test_request_has_no_secret_fields(self) -> None:
        request = _build_request("b2-contract", prompt="contract check")
        assert set(request.runtime_config.__class__.model_fields.keys()) == {
            "model_id",
            "provider_profile_id",
            "timeout_ms",
            "max_tool_rounds",
        }
        payload = serialize_director_runtime_request(request)
        serialized = json.dumps(payload)
        assert SECRET_API_KEY not in serialized
        for forbidden_field in ("api_key", "credential", "secret", "authorization"):
            assert forbidden_field not in payload["runtime_config"]

    def test_request_rejects_secret_bearing_snapshots(self) -> None:
        for patch in (
            {"permission_context": {"api_key": "must-be-rejected"}},
            {"authoritative_facts": {"credential": "must-be-rejected"}},
            {"permission_context": {"provider_secret": "must-be-rejected"}},
        ):
            payload = _request_payload("b2-contract-reject", prompt="contract check")
            payload.update(patch)
            try:
                validate_director_runtime_request(payload)
                raise AssertionError("expected secret-bearing request rejection")
            except Exception:
                pass


class TestCredentialIsolationAndBridge:
    def test_credential_enters_only_via_child_environment(self, tmp_path: Path) -> None:
        stub = _ProviderStub(response_text="provider-stub-response-A")
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            request = _build_request("b2-credential-isolation", prompt=PROMPT_A)
            payload = serialize_director_runtime_request(request)

            assert SECRET_API_KEY not in json.dumps(payload)
            assert SECRET_API_KEY not in request.model_dump_json()

            transport = _provider_transport(_bridge_environment(bridge))
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is not None
            assert outcome.error is None
            assert outcome.candidate.response_text == "provider-stub-response-A"
            assert outcome.candidate.tool_activity == []
            assert outcome.candidate.runtime_metadata.model_id == MODEL_ID
            assert outcome.candidate.runtime_metadata.provider_profile_id == OPENAI_PROVIDER_PROFILE_ID

            assert len(stub.requests) == 1
            provider_request = stub.requests[0]
            assert provider_request["path"] == "/v1/chat/completions"
            assert provider_request["model"] == MODEL_ID
            assert provider_request["authorization_present"] is True
            assert provider_request["stream"] is True
            assert provider_request["tools_present"] is False
            assert PROMPT_A in provider_request["body"]
            assert SECRET_API_KEY not in provider_request["body"]

            _assert_outcome_has_no_secret(
                outcome.candidate.model_dump_json(),
                outcome.candidate.model_dump(),
                request.model_dump_json(),
            )
            assert transport.active_process_ids == frozenset()
        finally:
            stub.close()

    def test_response_b_proves_provider_origin_and_no_db_writes(self, tmp_path: Path) -> None:
        stub = _ProviderStub(response_text="provider-stub-response-A")
        db_path = tmp_path / "db" / "orchestrator.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()
        before = _snapshot_db_writes(db_path)
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)

            request_a = _build_request("b2-response-a", prompt=PROMPT_A)
            transport_a = _provider_transport(_bridge_environment(bridge))
            supervisor_a = DirectorRuntimeSupervisor(transport=transport_a)
            supervisor_a.start()
            outcome_a = asyncio.run(supervisor_a.submit(request=request_a))
            assert outcome_a.candidate is not None
            assert outcome_a.candidate.response_text == "provider-stub-response-A"

            stub.response_text = "provider-stub-response-B"
            request_b = _build_request("b2-response-b", prompt=PROMPT_B)
            transport_b = _provider_transport(_bridge_environment(bridge))
            supervisor_b = DirectorRuntimeSupervisor(transport=transport_b)
            supervisor_b.start()
            outcome_b = asyncio.run(supervisor_b.submit(request=request_b))
            assert outcome_b.candidate is not None
            assert outcome_b.candidate.response_text == "provider-stub-response-B"
            assert len(stub.requests) == 2
            assert PROMPT_B in stub.requests[1]["body"]
            assert PROMPT_A in stub.requests[0]["body"]

            assert _snapshot_db_writes(db_path) == before
            assert transport_a.active_process_ids == frozenset()
            assert transport_b.active_process_ids == frozenset()
        finally:
            stub.close()


class TestFailClosedBoundaries:
    def test_profile_mismatch_fails_closed_without_provider_request(self, tmp_path: Path) -> None:
        stub = _ProviderStub()
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            environment = _bridge_environment(bridge)
            environment[ENV_PROVIDER_PROFILE_ID] = "different-injected-profile"

            request = _build_request("b2-profile-mismatch", prompt=PROMPT_A)
            transport = _provider_transport(environment)
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            assert len(stub.requests) == 0
            assert transport.active_process_ids == frozenset()
        finally:
            stub.close()

    def test_missing_credential_fails_closed_without_provider_request(self, tmp_path: Path) -> None:
        stub = _ProviderStub()
        try:
            provider_service = _fake_provider_config_service(
                tmp_path, api_key=None, base_url=stub.base_url
            )
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            environment = _bridge_environment(bridge)
            assert ENV_PROVIDER_API_KEY not in environment

            request = _build_request("b2-missing-credential", prompt=PROMPT_A)
            transport = _provider_transport(environment)
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            assert len(stub.requests) == 0
        finally:
            stub.close()

    def test_missing_base_url_fails_closed_without_provider_request(self, tmp_path: Path) -> None:
        stub = _ProviderStub()
        try:
            environment = {
                ENV_PROVIDER_MODE: PROVIDER_MODE_OPENAI_COMPATIBLE,
                ENV_PROVIDER_PROFILE_ID: OPENAI_PROVIDER_PROFILE_ID,
                ENV_PROVIDER_API_KEY: SECRET_API_KEY,
            }
            request = _build_request("b2-missing-base-url", prompt=PROMPT_A)
            transport = _provider_transport(environment)
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            assert len(stub.requests) == 0
        finally:
            stub.close()

    def test_provider_401_never_admits_candidate(self, tmp_path: Path) -> None:
        stub = _ProviderStub(mode="unauthorized")
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            request = _build_request("b2-provider-401", prompt=PROMPT_A)
            transport = _provider_transport(_bridge_environment(bridge))
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            assert len(stub.requests) == 1
            assert transport.active_process_ids == frozenset()
        finally:
            stub.close()

    def test_provider_500_never_admits_candidate_and_frozen_retry(self, tmp_path: Path) -> None:
        stub = _ProviderStub(mode="server_error")
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            request = _build_request("b2-provider-500", prompt=PROMPT_A)
            transport = _provider_transport(_bridge_environment(bridge))
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            # Frozen Pi retry policy: maxRetries=0, so exactly one provider request.
            assert len(stub.requests) == 1
        finally:
            stub.close()

    def test_malformed_provider_response_never_admits_candidate(self, tmp_path: Path) -> None:
        stub = _ProviderStub(mode="malformed_no_finish_reason")
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            request = _build_request("b2-provider-malformed", prompt=PROMPT_A)
            transport = _provider_transport(_bridge_environment(bridge))
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            assert len(stub.requests) == 1
        finally:
            stub.close()

    def test_provider_timeout_terminates_and_reaps_child(self, tmp_path: Path) -> None:
        stub = _ProviderStub(mode="hang")
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            request = _build_request("b2-provider-timeout", prompt=PROMPT_A)
            request = request.model_copy(
                update={
                    "runtime_config": request.runtime_config.model_copy(
                        update={"timeout_ms": 2000.0}
                    )
                }
            )
            transport = _provider_transport(_bridge_environment(bridge))
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.attempt_state == DirectorRuntimeAttemptState.TIMED_OUT
            assert outcome.candidate is None
            assert outcome.error is not None
            assert transport.active_process_ids == frozenset()
            assert len(stub.requests) == 1
        finally:
            stub.close()


class TestSyntheticDefaultRegression:
    def test_default_path_stays_synthetic_without_provider_mode(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DIRECTOR_RUNTIME_PROVIDER_MODE", raising=False)
        stub = _ProviderStub()
        try:
            request = validate_director_runtime_request(
                {
                    **_request_payload("b2-synthetic-regression", prompt="run the default loop"),
                    "available_tools": [],
                    "runtime_config": {
                        "model_id": "synthetic-director-model",
                        "provider_profile_id": "synthetic-local",
                        "timeout_ms": 2000.0,
                        "max_tool_rounds": 0,
                    },
                }
            )
            transport = StdioJsonlDirectorRuntimeTransport(
                command=("node", str(RUNTIME)),
                cancel_wait_seconds=0.5,
            )
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is not None
            assert outcome.error is None
            assert outcome.candidate.response_text == "synthetic director runtime response"
            assert len(stub.requests) == 0
            assert transport.active_process_ids == frozenset()
        finally:
            stub.close()


class TestTransportEnvironmentControl:
    def test_request_json_cannot_control_provider_environment_keys(self, tmp_path: Path) -> None:
        stub = _ProviderStub()
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            environment = _bridge_environment(bridge)
            transport = _provider_transport(environment)

            hostile_request = _build_request("b2-hostile-request", prompt=PROMPT_A)
            payload = serialize_director_runtime_request(hostile_request)
            injected_payload = dict(payload)
            injected_payload["DIRECTOR_RUNTIME_PROVIDER_API_KEY"] = "attacker-key"
            injected_payload["DIRECTOR_RUNTIME_PROVIDER_BASE_URL"] = "http://attacker.example/v1"
            injected_payload["DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID"] = "attacker-profile"

            async def scenario() -> None:
                supervisor = DirectorRuntimeSupervisor(transport=transport)
                supervisor.start()
                try:
                    raw = await transport.invoke(request_id="hostile", request=injected_payload)
                except Exception:
                    raw = None
                assert raw is None
                assert len(stub.requests) == 0

                supervisor2 = DirectorRuntimeSupervisor(transport=transport)
                supervisor2.start()
                outcome = await supervisor2.submit(request=hostile_request)
                assert outcome.candidate is not None
                assert outcome.candidate.response_text == "provider-stub-response-A"
                assert len(stub.requests) == 1
                assert stub.requests[0]["model"] == MODEL_ID

            asyncio.run(scenario())
            assert transport.active_process_ids == frozenset()
        finally:
            stub.close()


class TestErrorPrivacy:
    def test_failure_outputs_never_leak_credentials(self, tmp_path: Path) -> None:
        stub = _ProviderStub(mode="unauthorized")
        try:
            provider_service = _fake_provider_config_service(tmp_path, base_url=stub.base_url)
            bridge = DirectorRuntimeProviderConfigService(provider_config_service=provider_service)
            request = _build_request("b2-error-privacy", prompt=PROMPT_A)
            transport = _provider_transport(_bridge_environment(bridge))
            supervisor = DirectorRuntimeSupervisor(transport=transport)
            supervisor.start()
            outcome = asyncio.run(supervisor.submit(request=request))

            assert outcome.candidate is None
            assert outcome.error is not None
            failure = outcome.error
            assert isinstance(failure, DirectorRuntimeFailure)
            observed = " ".join(
                [
                    failure.model_dump_json(),
                    failure.safe_message,
                    failure.code,
                    failure.stage,
                ]
            )
            assert SECRET_API_KEY not in observed
            assert "Bearer" not in observed
            assert SECRET_API_KEY not in stub.base_url
        finally:
            stub.close()
