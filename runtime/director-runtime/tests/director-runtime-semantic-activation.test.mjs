import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const executable = path.join(root, "dist/director-runtime.js");
const [runtime, context, protocol, bridge] = await Promise.all([
	import(executable),
	import(path.join(root, "dist/director-context.js")),
	import(path.join(root, "dist/protocol.js")),
	import(path.join(root, "dist/director-provider-semantic-summarizer.js")),
]);

const secret = "LOCAL_API_KEY_NEVER_LOG_THIS";
const oldHistory = "START_HISTORY_SECRET " + "historical-A".repeat(550) + " END_HISTORY_SECRET";

function history(content, index = 1) {
	return { message_id: `history-${index}`, role: "assistant", content, sequence_no: index, occurred_at: "2026-09-15T00:00:00Z", source: "ai" };
}

function request(overrides = {}) {
	return protocol.validateDirectorRuntimeRequest({
		schema_version: "p26-big-director-runtime/v1", request_id: "request-A", project_id: "project-A", session_id: "session-A", message_id: "current-A",
		current_user_message: { content: "CURRENT_USER_A", occurred_at: "2026-09-16T00:00:00Z", actor_claim: "user" },
		recent_raw_messages: { items: [history(oldHistory)], has_more_before: false },
		authoritative_facts: { fact: "FRESH_FACT" }, active_discussion_workspace: { preferred: "FRESH_WORKSPACE" }, relevant_discussion_events: [],
		active_formalization: { proposal: { value: "FRESH_PROPOSAL" }, plan_version: { value: "FRESH_VERSION" } },
		governance_boundaries: { authoritative_write: false, director_may_modify_code: false, formalization_requires_explicit_request: true, confirmation_is_separate: true, execution_boundary: "no_task_run_agent_session_before_execution" },
		available_skills: [], available_tools: [], permission_context: {}, runtime_config: { model_id: "synthetic-test", provider_profile_id: "profile-A", timeout_ms: 20_000, max_tool_rounds: 0 },
		...overrides,
	});
}

async function runProcess(input, environment = {}) {
	return await new Promise((resolve, reject) => {
		const child = spawn(process.execPath, [executable], {
			env: { ...process.env, DIRECTOR_RUNTIME_PROVIDER_MODE: "", DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE: "", DIRECTOR_RUNTIME_SYNTHETIC_MODE: "", ...environment },
			stdio: ["pipe", "pipe", "pipe"],
		});
		let stdout = "", stderr = "";
		child.stdout.setEncoding("utf8"); child.stderr.setEncoding("utf8");
		child.stdout.on("data", chunk => { stdout += chunk; });
		child.stderr.on("data", chunk => { stderr += chunk; });
		child.once("error", reject);
		child.once("close", code => resolve({ code, stdout, stderr }));
		child.stdin.end(`${JSON.stringify(input)}\n`);
	});
}

function chunk(model, delta, finishReason) {
	return `data: ${JSON.stringify({ id: "local-only", object: "chat.completion.chunk", created: 1, model, choices: [{ index: 0, delta, finish_reason: finishReason }] })}\n\n`;
}

async function stub(responses = [{ text: "SEMANTIC_HISTORY", finish: "stop" }, { text: "FINAL_ANSWER", finish: "stop" }]) {
	const requests = [];
	const server = http.createServer((incoming, outgoing) => {
		let body = "";
		incoming.on("data", part => { body += part; });
		incoming.on("end", () => {
			const message = JSON.parse(body);
			requests.push({ body, message, path: incoming.url, authorized: incoming.headers.authorization === `Bearer ${secret}` });
			const response = responses[Math.min(requests.length - 1, responses.length - 1)];
			if (response.error) {
				outgoing.writeHead(500, { "content-type": "application/json" });
				outgoing.end(JSON.stringify({ error: { message: "local provider failure" } }));
				return;
			}
			outgoing.writeHead(200, { "content-type": "text/event-stream" });
			outgoing.write(chunk(message.model, { role: "assistant", content: response.text }, null));
			outgoing.write(chunk(message.model, {}, response.finish));
			outgoing.end("data: [DONE]\n\n");
		});
	});
	await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
	return {
		requests,
		baseUrl: `http://127.0.0.1:${server.address().port}/v1`,
		close: () => new Promise(resolve => server.close(resolve)),
	};
}

function env(server, semanticMode = "enabled") {
	return {
		DIRECTOR_RUNTIME_PROVIDER_MODE: "openai_compatible",
		DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID: "profile-A",
		DIRECTOR_RUNTIME_PROVIDER_BASE_URL: server.baseUrl,
		DIRECTOR_RUNTIME_PROVIDER_API_KEY: secret,
		DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE: semanticMode,
	};
}

function resultOf(execution) {
	assert.equal(execution.code, 0, execution.stderr);
	assert.equal(execution.stderr, "");
	assert.equal(execution.stdout.trimEnd().split("\n").length, 1);
	assert.ok(!execution.stdout.includes(secret));
	return JSON.parse(execution.stdout);
}

function messageText(message) {
	return typeof message.content === "string" ? message.content : message.content.map(entry => entry.text).join("");
}

function assertSafe(execution) {
	for (const output of [execution.stdout, execution.stderr]) {
		assert.equal(output.includes(secret), false);
		assert.equal(output.includes("END_HISTORY_SECRET"), false);
	}
}

test("default and non-exact opt-in preserve one C3-A call and unchanged result", async () => {
	for (const mode of [undefined, "disabled", "ENABLED", "enabled "]) {
		const server = await stub([{ text: "FINAL_ANSWER", finish: "stop" }]);
		try {
			const input = request();
			const configuration = env(server, mode ?? "");
			const execution = await runProcess(input, configuration);
			const result = resultOf(execution);
			assert.equal(result.response_text, "FINAL_ANSWER");
			assert.deepEqual(result.tool_activity, []);
			assert.deepEqual(result.source_references, [{ message_id: input.message_id, kind: "current_user_message" }]);
			assert.equal(result.schema_version, "p26-big-director-runtime/v1");
			assert.equal(server.requests.length, 1);
			assert.equal(messageText(server.requests[0].message.messages.at(-1)), input.current_user_message.content);
			assert.equal(messageText(server.requests[0].message.messages[0]), context.createDirectorModelContext(input).systemPrompt);
			assertSafe(execution);
		} finally { await server.close(); }
	}
});

test("synthetic process ignores semantic opt-in without Provider mode", async () => {
	const input = request();
	const execution = await runProcess(input, { DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE: "enabled" });
	const result = resultOf(execution);
	assert.equal(result.response_text, "synthetic director runtime response");
	assert.equal(result.schema_version, "p26-big-director-runtime/v1");
	assert.deepEqual(result.tool_activity, []);
});

test("Provider profile mismatch and missing credential remain fail-closed before any calls", async () => {
	const server = await stub();
	try {
		for (const configuration of [
			{ ...env(server), DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID: "wrong-profile" },
			{ ...env(server), DIRECTOR_RUNTIME_PROVIDER_API_KEY: "" },
		]) {
			const execution = await runProcess(request(), configuration);
			assert.notEqual(execution.code, 0);
			assert.equal(execution.stdout, "");
			assert.equal(execution.stderr, "director_runtime_failed\n");
			assert.equal(server.requests.length, 0);
			assertSafe(execution);
		}
	} finally { await server.close(); }
});

test("short timeout, absent history, small corpus, incomplete provenance and oversized source skip summary", async () => {
	const cases = [
		request({ runtime_config: { model_id: "synthetic-test", provider_profile_id: "profile-A", timeout_ms: 4_999, max_tool_rounds: 0 } }),
		request({ recent_raw_messages: { items: [], has_more_before: false } }),
		request({ recent_raw_messages: { items: [history("short")], has_more_before: false } }),
		request({ relevant_discussion_events: [{ content: "missing event provenance" }] }),
		request({ recent_raw_messages: { items: [history("O".repeat(9_000), 1), history("P".repeat(9_000), 2), history("Q".repeat(9_000), 3)], has_more_before: false } }),
	];
	for (const input of cases) {
		const server = await stub([{ text: "FINAL_ANSWER", finish: "stop" }]);
		try {
			const execution = await runProcess(input, env(server));
			const result = resultOf(execution);
			assert.equal(result.response_text, "FINAL_ANSWER");
			assert.equal(server.requests.length, 1);
			assert.equal(messageText(server.requests[0].message.messages[0]), context.createDirectorModelContext(input).systemPrompt);
			assertSafe(execution);
		} finally { await server.close(); }
	}
});

test("eligible history invokes summary then final Agent once with isolated and governed contexts", async () => {
	const server = await stub();
	try {
		const input = request();
		const before = structuredClone(input);
		const execution = await runProcess(input, env(server));
		const result = resultOf(execution);
		assert.equal(result.response_text, "FINAL_ANSWER");
		assert.equal(server.requests.length, 2);
		const [summaryRequest, finalRequest] = server.requests;
		for (const providerRequest of server.requests) {
			assert.equal(providerRequest.authorized, true);
			assert.equal(providerRequest.path, "/v1/chat/completions");
			assert.equal(providerRequest.message.model, input.runtime_config.model_id);
			assert.equal(Object.hasOwn(providerRequest.message, "tools"), false);
		}
		assert.match(summaryRequest.body, /UNTRUSTED_COMPACTABLE_HISTORICAL_WORKING_MEMORY/);
		assert.match(summaryRequest.body, /END_HISTORY_SECRET/);
		for (const forbidden of ["CURRENT_USER_A", "FRESH_FACT", "FRESH_WORKSPACE", "FRESH_PROPOSAL", "FRESH_VERSION"]) assert.equal(summaryRequest.body.includes(forbidden), false);
		assert.equal(summaryRequest.message.messages.length, 2);
		assert.equal(finalRequest.message.messages.length, 2);
		assert.equal(messageText(finalRequest.message.messages[1]), "CURRENT_USER_A");
		for (const pinned of ["FRESH_FACT", "FRESH_WORKSPACE", "FRESH_PROPOSAL", "FRESH_VERSION", "NON_AUTHORITATIVE_SEMANTIC_WORKING_MEMORY_SUMMARY"]) assert.ok(finalRequest.body.includes(pinned), pinned);
		assert.equal(finalRequest.body.includes("END_HISTORY_SECRET"), false);
		assert.equal(Object.hasOwn(result, "semantic_summary"), false);
		assert.deepEqual(result.tool_activity, []);
		assert.deepEqual(result.source_references, [{ message_id: input.message_id, kind: "current_user_message" }]);
		assert.deepEqual(input, before);
		assertSafe(execution);
	} finally { await server.close(); }
});

test("length-truncated or failed summary falls back to C1 and still calls final Agent once", async () => {
	for (const first of [{ text: "plausible partial", finish: "length" }, { error: true }]) {
		const server = await stub([first, { text: "FINAL_ANSWER", finish: "stop" }]);
		try {
			const input = request();
			const execution = await runProcess(input, env(server));
			const result = resultOf(execution);
			assert.equal(result.response_text, "FINAL_ANSWER");
			assert.equal(server.requests.length, 2);
			assert.equal(messageText(server.requests[1].message.messages[0]), context.createDirectorModelContext(input).systemPrompt);
			assert.equal(server.requests[1].body.includes("NON_AUTHORITATIVE_SEMANTIC_WORKING_MEMORY_SUMMARY"), false);
			assertSafe(execution);
		} finally { await server.close(); }
	}
});

test("final Agent failure remains a safe failure after semantic success", async () => {
	const server = await stub([{ text: "SEMANTIC_HISTORY", finish: "stop" }, { error: true }]);
	try {
		const execution = await runProcess(request(), env(server));
		assert.equal(server.requests.length, 2);
		assert.notEqual(execution.code, 0);
		assert.equal(execution.stdout, "");
		assert.equal(execution.stderr, "director_runtime_failed\n");
		assertSafe(execution);
	} finally { await server.close(); }
});

test("injected bridge timeout falls back, reserves final attempt, and never retries", async () => {
	const previousMode = process.env.DIRECTOR_RUNTIME_PROVIDER_MODE;
	const previousSemanticMode = process.env.DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE;
	process.env.DIRECTOR_RUNTIME_PROVIDER_MODE = "openai_compatible";
	process.env.DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE = "enabled";
	try {
		const input = request({ runtime_config: { model_id: "synthetic-test", provider_profile_id: "profile-A", timeout_ms: 5_000, max_tool_rounds: 0 } });
		const before = structuredClone(input);
		let summaryCalls = 0;
		let agentCalls = 0;
		let summarySignal;
		const summarizer = bridge.createDirectorProviderSemanticSummarizer({
			id: "summary", name: "summary", api: "synthetic", provider: "synthetic", baseUrl: "synthetic://test", reasoning: false,
			input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 12_000, maxTokens: 2048,
		}, (_model, _context, options) => {
			summaryCalls++;
			summarySignal = options.signal;
			return new Promise(() => {});
		}, { timeoutMs: 20 });
		const result = await runtime.executeDirectorRuntimeRequest(input, (...args) => {
			agentCalls++;
			assert.equal(args[1].systemPrompt, context.createDirectorModelContext(input).systemPrompt);
			return runtime.createSyntheticStreamFn("FINAL_ANSWER")(...args);
		}, undefined, { semanticSummarizer: summarizer });
		assert.equal(result.response_text, "FINAL_ANSWER");
		assert.equal(summaryCalls, 1);
		assert.equal(agentCalls, 1);
		assert.equal(summarySignal.aborted, true);
		assert.deepEqual(input, before);
	} finally {
		if (previousMode === undefined) delete process.env.DIRECTOR_RUNTIME_PROVIDER_MODE;
		else process.env.DIRECTOR_RUNTIME_PROVIDER_MODE = previousMode;
		if (previousSemanticMode === undefined) delete process.env.DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE;
		else process.env.DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE = previousSemanticMode;
	}
});

test("same-request stub runs are stable and concurrent projects do not bleed", async () => {
	const server = await stub();
	try {
		const first = request();
		const second = request({ request_id: "request-B", project_id: "project-B", session_id: "session-B", message_id: "current-B", current_user_message: { content: "CURRENT_USER_B", occurred_at: "2026-09-16T00:00:00Z", actor_claim: "user" }, recent_raw_messages: { items: [history("B_HISTORY".repeat(1000))], has_more_before: false }, active_discussion_workspace: { preferred: "FRESH_B" } });
		const [executionA, executionB] = await Promise.all([runProcess(first, env(server)), runProcess(second, env(server))]);
		const resultA = resultOf(executionA), resultB = resultOf(executionB);
		assert.equal(resultA.response_text, "FINAL_ANSWER");
		assert.equal(resultB.response_text, "FINAL_ANSWER");
		assert.equal(server.requests.length, 4);
		const finalA = server.requests.find(entry => entry.body.includes("CURRENT_USER_A"));
		const finalB = server.requests.find(entry => entry.body.includes("CURRENT_USER_B"));
		assert.ok(finalA.body.includes("FRESH_WORKSPACE"));
		assert.ok(!finalA.body.includes("FRESH_B"));
		assert.ok(finalB.body.includes("FRESH_B"));
		assert.ok(!finalB.body.includes("FRESH_WORKSPACE"));
		assertSafe(executionA); assertSafe(executionB);
		const repeated = resultOf(await runProcess(first, env(server)));
		assert.deepEqual({ ...resultA, runtime_metadata: { ...resultA.runtime_metadata, duration_ms: 0 } }, { ...repeated, runtime_metadata: { ...repeated.runtime_metadata, duration_ms: 0 } });
	} finally { await server.close(); }
});
