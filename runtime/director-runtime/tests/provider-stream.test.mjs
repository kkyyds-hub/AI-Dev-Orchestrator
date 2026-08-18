import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const runtimeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const runtimeModule = path.join(runtimeRoot, "dist", "director-runtime.js");

const SECRET_API_KEY = "b2-secret-api-key-node-fake-never-real";
const MODEL_ID = "director-test-model-b2";
const PROMPT_A = "b2-node-provider-prompt-unique-a";
const PROMPT_B = "b2-node-provider-prompt-unique-b";

function request(requestId, overrides = {}) {
	return {
		schema_version: "p26-big-director-runtime/v1",
		request_id: requestId,
		project_id: "project-b2-v1",
		session_id: "session-b2-v1",
		message_id: `message-${requestId}`,
		current_user_message: {
			content: PROMPT_A,
			occurred_at: "2026-08-18T00:00:00Z",
			actor_claim: "user",
		},
		authoritative_facts: {},
		active_discussion_workspace: null,
		relevant_discussion_events: [],
		active_formalization: { proposal: null, plan_version: null },
		governance_boundaries: {
			authoritative_write: false,
			director_may_modify_code: false,
			formalization_requires_explicit_request: true,
			confirmation_is_separate: true,
			execution_boundary: "no_task_run_agent_session_before_execution",
		},
		available_skills: [],
		available_tools: [],
		permission_context: {},
		runtime_config: {
			model_id: MODEL_ID,
			provider_profile_id: "openai",
			timeout_ms: 20000,
			max_tool_rounds: 0,
		},
		...overrides,
	};
}

async function runRuntime(input, environment = {}) {
	return await new Promise((resolve, reject) => {
		const child = spawn(process.execPath, [runtimeModule], {
			env: { ...process.env, ...environment },
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";
		child.stdout.setEncoding("utf8");
		child.stderr.setEncoding("utf8");
		child.stdout.on("data", (chunk) => { stdout += chunk; });
		child.stderr.on("data", (chunk) => { stderr += chunk; });
		child.once("error", reject);
		child.once("close", (code) => resolve({ code, stdout, stderr }));
		child.stdin.end(input);
	});
}

function sseChunk(model, delta, finishReason) {
	return `data: ${JSON.stringify({
		id: "chatcmpl-b2-local-stub",
		object: "chat.completion.chunk",
		created: 1,
		model,
		choices: [{ index: 0, delta, finish_reason: finishReason }],
	})}\n\n`;
}

/**
 * Loopback OpenAI-compatible stub bound to 127.0.0.1 only. It records bounded
 * request metadata (never the raw Authorization value) and serves the exact
 * endpoint the pinned Pi AI openai-completions adapter calls.
 */
async function startStub(mode, responseText) {
	const state = { requests: [], mode, responseText };
	const server = http.createServer((req, res) => {
		let body = "";
		req.on("data", (chunk) => { body += chunk; });
		req.on("end", () => {
			let payload = null;
			try {
				payload = body ? JSON.parse(body) : {};
			} catch {
				payload = null;
			}
			state.requests.push({
				path: req.url,
				model: payload && typeof payload.model === "string" ? payload.model : null,
				authorization_present: Boolean(req.headers.authorization),
				body,
				stream: payload ? payload.stream : null,
				tools_present: payload ? "tools" in payload : null,
			});
			if (state.mode === "unauthorized") {
				res.writeHead(401, { "Content-Type": "application/json" });
				res.end(JSON.stringify({ error: { message: "unauthorized" } }));
				return;
			}
			if (state.mode === "server_error") {
				res.writeHead(500, { "Content-Type": "application/json" });
				res.end(JSON.stringify({ error: { message: "server_error" } }));
				return;
			}
			if (state.mode === "malformed_no_finish_reason") {
				res.writeHead(200, { "Content-Type": "text/event-stream" });
				res.write(sseChunk(payload?.model ?? "unknown", { role: "assistant", content: "partial" }, null));
				res.end();
				return;
			}
			if (state.mode === "malformed_invalid_json") {
				res.writeHead(200, { "Content-Type": "text/event-stream" });
				res.write("data: {not-valid-json\n\n");
				res.end();
				return;
			}
			res.writeHead(200, { "Content-Type": "text/event-stream" });
			res.write(sseChunk(payload?.model ?? "unknown", { role: "assistant", content: state.responseText }, null));
			res.write(sseChunk(payload?.model ?? "unknown", {}, "stop"));
			res.write("data: [DONE]\n\n");
			res.end();
		});
	});
	await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
	return {
		state,
		baseUrl: `http://127.0.0.1:${server.address().port}/v1`,
		async close() {
			await new Promise((resolve) => server.close(resolve));
		},
	};
}

function providerEnvironment(baseUrl, overrides = {}) {
	return {
		DIRECTOR_RUNTIME_PROVIDER_MODE: "openai_compatible",
		DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID: "openai",
		DIRECTOR_RUNTIME_PROVIDER_BASE_URL: baseUrl,
		DIRECTOR_RUNTIME_PROVIDER_API_KEY: SECRET_API_KEY,
		...overrides,
	};
}

function assertFailedClosed(execution, { exactStderr = true } = {}) {
	assert.notEqual(execution.code, 0);
	assert.equal(execution.stdout, "");
	if (exactStderr) {
		assert.equal(execution.stderr, "director_runtime_failed\n");
	} else {
		assert.equal(execution.stderr.endsWith("director_runtime_failed\n"), true);
	}
	assert.equal(execution.stderr.includes(SECRET_API_KEY), false);
}

test("provider bridge fails closed before any provider request is made", async () => {
	const stub = await startStub("ok", "provider-stub-response-A");
	try {
		const mismatch = await runRuntime(`${JSON.stringify(request("b2-profile-mismatch", {
			runtime_config: {
				model_id: MODEL_ID,
				provider_profile_id: "other-provider-profile",
				timeout_ms: 20000,
				max_tool_rounds: 0,
			},
		}))}\n`, providerEnvironment(stub.baseUrl));
		assertFailedClosed(mismatch);
		assert.equal(stub.state.requests.length, 0);

		const missingKey = await runRuntime(`${JSON.stringify(request("b2-missing-key"))}\n`, providerEnvironment(stub.baseUrl, {
			DIRECTOR_RUNTIME_PROVIDER_API_KEY: "",
		}));
		assertFailedClosed(missingKey);
		assert.equal(stub.state.requests.length, 0);

		const missingBaseUrl = await runRuntime(`${JSON.stringify(request("b2-missing-base-url"))}\n`, {
			DIRECTOR_RUNTIME_PROVIDER_MODE: "openai_compatible",
			DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID: "openai",
			DIRECTOR_RUNTIME_PROVIDER_API_KEY: SECRET_API_KEY,
		});
		assertFailedClosed(missingBaseUrl);
		assert.equal(stub.state.requests.length, 0);
	} finally {
		await stub.close();
	}
});

test("synthetic default path is unchanged when provider mode is not injected", async () => {
	const stub = await startStub("ok", "provider-stub-response-A");
	try {
		const execution = await runRuntime(`${JSON.stringify(request("b2-synthetic-default", {
			runtime_config: {
				model_id: "synthetic-director-model",
				provider_profile_id: "synthetic-local",
				timeout_ms: 5000,
				max_tool_rounds: 0,
			},
		}))}\n`);
		assert.equal(execution.code, 0);
		assert.equal(execution.stderr, "");
		const lines = execution.stdout.trimEnd().split("\n");
		assert.equal(lines.length, 1);
		const result = JSON.parse(lines[0]);
		assert.equal(result.response_text, "synthetic director runtime response");
		assert.equal(stub.state.requests.length, 0);
	} finally {
		await stub.close();
	}
});

test("provider responses A and B flow through the Pi Agent loop with bounded tools", async () => {
	const stub = await startStub("ok", "provider-stub-response-A");
	try {
		const authorizedToolsRequest = request("b2-provider-a", {
			current_user_message: {
				content: PROMPT_A,
				occurred_at: "2026-08-18T00:00:00Z",
				actor_claim: "user",
			},
			available_tools: [{
				tool_id: "allowed-but-unregistered",
				allowed: true,
				authorization_id: "authorization-b2-node",
				idempotency_key: "idempotency-b2-node",
			}],
		});
		const executionA = await runRuntime(`${JSON.stringify(authorizedToolsRequest)}\n`, providerEnvironment(stub.baseUrl));
		assert.equal(executionA.code, 0);
		assert.equal(executionA.stderr, "");
		const resultA = JSON.parse(executionA.stdout.trimEnd());

		assert.equal(resultA.response_text, "provider-stub-response-A");
		assert.equal(resultA.error, null);
		assert.deepEqual(resultA.tool_activity, []);
		assert.equal(resultA.runtime_metadata.model_id, MODEL_ID);
		assert.equal(resultA.runtime_metadata.provider_profile_id, "openai");
		assert.equal(executionA.stdout.includes(SECRET_API_KEY), false);

		assert.equal(stub.state.requests.length, 1);
		const providerRequestA = stub.state.requests[0];
		assert.equal(providerRequestA.path, "/v1/chat/completions");
		assert.equal(providerRequestA.model, MODEL_ID);
		assert.equal(providerRequestA.authorization_present, true);
		assert.equal(providerRequestA.stream, true);
		assert.equal(providerRequestA.tools_present, false);
		assert.equal(providerRequestA.body.includes(PROMPT_A), true);

		stub.state.responseText = "provider-stub-response-B";
		const requestB = request("b2-provider-b", {
			current_user_message: {
				content: PROMPT_B,
				occurred_at: "2026-08-18T00:00:00Z",
				actor_claim: "user",
			},
		});
		const executionB = await runRuntime(`${JSON.stringify(requestB)}\n`, providerEnvironment(stub.baseUrl));
		assert.equal(executionB.code, 0);
		const resultB = JSON.parse(executionB.stdout.trimEnd());
		assert.equal(resultB.response_text, "provider-stub-response-B");
		assert.equal(stub.state.requests.length, 2);
		assert.equal(stub.state.requests[1].model, MODEL_ID);
		assert.equal(stub.state.requests[1].body.includes(PROMPT_B), true);
		assert.equal(stub.state.requests[1].authorization_present, true);
	} finally {
		await stub.close();
	}
});

test("frozen request contract rejects secret-bearing fields", async () => {
	const { validateDirectorRuntimeRequest } = await import(path.join(runtimeRoot, "dist", "protocol.js"));

	const validRequest = validateDirectorRuntimeRequest(request("b2-contract-baseline"));
	assert.equal(Object.keys(validRequest.runtime_config).join(","), "model_id,provider_profile_id,timeout_ms,max_tool_rounds");

	assert.throws(() => validateDirectorRuntimeRequest(request("b2-contract-api-key", {
		runtime_config: {
			model_id: MODEL_ID,
			provider_profile_id: "openai",
			timeout_ms: 20000,
			max_tool_rounds: 0,
			api_key: "must-be-rejected",
		},
	})));
	assert.throws(() => validateDirectorRuntimeRequest(request("b2-contract-credential", {
		permission_context: { credential: "must-be-rejected" },
	})));
	assert.throws(() => validateDirectorRuntimeRequest(request("b2-contract-secret-fact", {
		authoritative_facts: { provider_secret: "must-be-rejected" },
	})));
});

test("provider error responses never admit a candidate and keep frozen retry policy", async () => {
	for (const [mode, expectedRequests, exactStderr] of [
		["unauthorized", 1, true],
		["server_error", 1, true],
		["malformed_no_finish_reason", 1, true],
		// The pinned Pi AI adapter echoes one bounded parse diagnostic for an
		// invalid SSE data chunk before the runtime fails closed; stderr must
		// still carry no secret.
		["malformed_invalid_json", 1, false],
	]) {
		const stub = await startStub(mode, "provider-stub-response-A");
		try {
			const execution = await runRuntime(`${JSON.stringify(request(`b2-provider-${mode}`))}\n`, providerEnvironment(stub.baseUrl));
			assertFailedClosed(execution, { exactStderr });
			assert.equal(stub.state.requests.length, expectedRequests, `request count for ${mode}`);
		} finally {
			await stub.close();
		}
	}
});

test("provider bridge source stays inside the B2 boundary", async () => {
	const source = await readFile(path.join(runtimeRoot, "src", "provider-stream.ts"), "utf8");
	for (const forbidden of [
		"fetch(",
		"axios",
		"MCP",
		"child_process",
		"fs.writeFile",
		"git commit",
		"git push",
		"repository",
		"generate-models",
		"hydrate-model-data",
	]) {
		assert.equal(source.includes(forbidden), false, forbidden);
	}
	for (const envKey of [
		"DIRECTOR_RUNTIME_PROVIDER_MODE",
		"DIRECTOR_RUNTIME_PROVIDER_BASE_URL",
		"DIRECTOR_RUNTIME_PROVIDER_API_KEY",
		"DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID",
	]) {
		assert.equal(source.includes(envKey), true, envKey);
	}
	assert.equal(source.includes("request.runtime_config.model_id"), true);
});
