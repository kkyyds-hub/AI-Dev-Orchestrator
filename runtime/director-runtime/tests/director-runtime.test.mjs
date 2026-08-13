import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const runtimeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const runtimeModule = path.join(runtimeRoot, "dist", "director-runtime.js");
const protocolModule = path.join(runtimeRoot, "dist", "protocol.js");

function request(requestId, overrides = {}) {
	return {
		schema_version: "p26-big-director-runtime/v1",
		request_id: requestId,
		project_id: "project-b1-v1",
		session_id: "session-b1-v1",
		message_id: `message-${requestId}`,
		current_user_message: {
			content: "Run the deterministic Pi Director loop.",
			occurred_at: "2026-08-13T00:00:00Z",
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
			model_id: "synthetic-director-model",
			provider_profile_id: "synthetic-local",
			timeout_ms: 1000,
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

function assertSuccessfulResult(execution, sourceRequest, responseText) {
	assert.equal(execution.code, 0);
	assert.equal(execution.stderr, "");
	const lines = execution.stdout.trimEnd().split("\n");
	assert.equal(lines.length, 1);
	const result = JSON.parse(lines[0]);
	assert.equal(result.schema_version, sourceRequest.schema_version);
	assert.equal(result.request_id, sourceRequest.request_id);
	assert.equal(result.response_text, responseText);
	assert.deepEqual(result.turn_semantics, {
		conversation_mode: "general_discussion",
		formal_action_requested: false,
		hypothetical_action: false,
		confidence: null,
	});
	assert.equal(result.discussion_delta_candidate, null);
	assert.deepEqual(result.formalization, { proposal_candidate: null, readiness: "not_ready" });
	assert.deepEqual(result.tool_activity, []);
	assert.deepEqual(result.source_references, [
		{ message_id: sourceRequest.message_id, kind: "current_user_message" },
	]);
	assert.equal(result.runtime_metadata.model_id, sourceRequest.runtime_config.model_id);
	assert.equal(result.runtime_metadata.provider_profile_id, sourceRequest.runtime_config.provider_profile_id);
	assert.equal(result.error, null);
}

test("real Pi Agent prompt maps injected assistant responses into the frozen result without tools", async () => {
	const { createSyntheticStreamFn, executeDirectorRuntimeRequest } = await import(runtimeModule);
	const { validateDirectorRuntimeRequest } = await import(protocolModule);
	const sourceRequest = request("node-pi-loop", {
		available_tools: [{
			tool_id: "allowed-but-unregistered",
			allowed: true,
			authorization_id: "authorization-node",
			idempotency_key: "idempotency-node",
		}],
	});
	const validated = validateDirectorRuntimeRequest(sourceRequest);
	let streamCalls = 0;
	let observedTools;
	const streamFn = (...args) => {
		streamCalls += 1;
		observedTools = args[1].tools;
		return createSyntheticStreamFn("response A from Pi")(...args);
	};
	const resultA = await executeDirectorRuntimeRequest(validated, streamFn);
	const resultB = await executeDirectorRuntimeRequest(
		validated,
		createSyntheticStreamFn("response B from Pi"),
	);

	assert.equal(streamCalls, 1);
	assert.deepEqual(observedTools, []);
	assert.equal(resultA.response_text, "response A from Pi");
	assert.equal(resultB.response_text, "response B from Pi");
	assert.deepEqual(resultA.tool_activity, []);
	assert.equal(resultA.source_references[0].message_id, sourceRequest.message_id);
	assert.equal(resultA.source_references[0].kind, "current_user_message");
});

test("JSONL process emits exactly one result and isolates repeated requests", async () => {
	for (const requestId of ["process-one", "process-two", "process-three"]) {
		const sourceRequest = request(requestId);
		const execution = await runRuntime(`${JSON.stringify(sourceRequest)}\n`, {
			OPENAI_API_KEY: "unused-fake-key",
			ANTHROPIC_API_KEY: "unused-fake-key",
		});
		assertSuccessfulResult(execution, sourceRequest, "synthetic director runtime response");
	}
});

test("malformed JSONL and synthetic stream failure do not emit a candidate", async () => {
	for (const input of ["{invalid json\n", `${JSON.stringify(request("line-one"))}\n${JSON.stringify(request("line-two"))}\n`]) {
		const execution = await runRuntime(input);
		assert.notEqual(execution.code, 0);
		assert.equal(execution.stdout, "");
	}

	const invalidSchema = request("invalid-schema", { schema_version: "p26-big-director-runtime/v2" });
	const invalidGovernance = request("invalid-governance", {
		governance_boundaries: {
			authoritative_write: true,
			director_may_modify_code: false,
			formalization_requires_explicit_request: true,
			confirmation_is_separate: true,
			execution_boundary: "no_task_run_agent_session_before_execution",
		},
	});
	for (const sourceRequest of [invalidSchema, invalidGovernance]) {
		const execution = await runRuntime(`${JSON.stringify(sourceRequest)}\n`);
		assert.notEqual(execution.code, 0);
		assert.equal(execution.stdout, "");
	}

	const streamFailure = await runRuntime(`${JSON.stringify(request("stream-failure"))}\n`, {
		DIRECTOR_RUNTIME_SYNTHETIC_MODE: "throw",
	});
	assert.notEqual(streamFailure.code, 0);
	assert.equal(streamFailure.stdout, "");
});

test("runtime source keeps provider, network, persistence, and Git writes outside B1", async () => {
	const source = await readFile(path.join(runtimeRoot, "src", "director-runtime.ts"), "utf8");
	for (const forbidden of [
		"fetch(",
		"axios",
		"MCP",
		"child_process",
		"fs.writeFile",
		"git commit",
		"git push",
		"repository",
	]) {
		assert.equal(source.includes(forbidden), false, forbidden);
	}
});
