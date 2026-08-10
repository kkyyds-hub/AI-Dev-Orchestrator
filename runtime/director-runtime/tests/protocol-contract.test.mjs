import assert from "node:assert/strict";
import test from "node:test";

import {
	DirectorRuntimeContractError,
	validateDirectorRuntimeRequest,
	validateDirectorTurnResult,
	validateResultForRequest,
} from "../dist/protocol.js";

const validTimestamps = [
	"2026-08-10T01:00:00+08:00",
	"2026-08-09T17:00:00Z",
	"2026-08-09T17:00:00.1Z",
	"2026-08-09T17:00:00.123Z",
	"2026-08-09T17:00:00.123456+08:00",
	"2026-08-09T12:00:00-05:00",
];
const invalidTimestamps = [
	"2026-08-10T01:00:00",
	"2026/08/10 01:00:00 +08:00",
	"August 10, 2026 01:00:00 +08:00",
	"2026-08-10 01:00:00+08:00",
	"2026-08-10T01:00:00+0800",
	"2026-08-10T01:00:00z",
	"2026-02-30T01:00:00+08:00",
	"2026-13-01T01:00:00+08:00",
	"2026-08-10T24:01:00+08:00",
	"2026-08-10T01:60:00+08:00",
	"2026-08-10T01:00:60+08:00",
	"not-a-date",
];

function requestPayload(occurredAt = validTimestamps[0]) {
	return {
		schema_version: "p26-big-director-runtime/v1",
		request_id: "request-1",
		project_id: "project-1",
		session_id: "session-1",
		message_id: "message-1",
		current_user_message: { content: "hello", occurred_at: occurredAt, actor_claim: "user" },
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
		runtime_config: { model_id: "model-1", provider_profile_id: "profile-1", timeout_ms: 1000, max_tool_rounds: 0 },
	};
}

function resultPayload(requestId = "request-1") {
	return {
		schema_version: "p26-big-director-runtime/v1",
		request_id: requestId,
		response_text: "safe response",
		turn_semantics: { conversation_mode: "general_discussion", formal_action_requested: false, hypothetical_action: false, confidence: 0.8 },
		discussion_lifecycle: { observed_status: null, suggested_next_status: null },
		discussion_delta_candidate: null,
		formalization: { proposal_candidate: null, readiness: "not_ready" },
		tool_activity: [],
		source_references: [],
		runtime_metadata: { runtime_state: "ready", model_id: "model-1", provider_profile_id: "profile-1", usage: {}, duration_ms: 1, attempt: 0 },
		error: null,
	};
}

function rejects(fn) {
	assert.throws(fn, DirectorRuntimeContractError);
}

test("request accepts the canonical v1 timestamp grammar", () => {
	for (const timestamp of validTimestamps) {
		assert.equal(validateDirectorRuntimeRequest(requestPayload(timestamp)).current_user_message.occurred_at, timestamp);
	}
});

test("request rejects noncanonical timestamps", () => {
	for (const timestamp of invalidTimestamps) rejects(() => validateDirectorRuntimeRequest(requestPayload(timestamp)));
});

test("request rejects closed-envelope keys, invalid identity, and governance bypasses", () => {
	const cases = [
		(value) => { value.schema_version = "p26-big-director-runtime/v2"; },
		(value) => { value.request_id = ""; },
		(value) => { value.current_user_message.unexpected = true; },
		(value) => { value.unexpected = true; },
		(value) => { value.governance_boundaries.authoritative_write = true; },
		(value) => { value.governance_boundaries.director_may_modify_code = true; },
		(value) => { value.governance_boundaries.formalization_requires_explicit_request = false; },
		(value) => { value.governance_boundaries.confirmation_is_separate = false; },
		(value) => { value.runtime_config.unexpected = true; },
		(value) => { value.available_skills = [{ skill_id: "skill", version: "1", enabled: true, unexpected: true }]; },
		(value) => { value.available_tools = [{ tool_id: "tool", allowed: false, authorization_id: null, idempotency_key: null, unexpected: true }]; },
	];
	for (const mutate of cases) {
		const value = requestPayload();
		mutate(value);
		rejects(() => validateDirectorRuntimeRequest(value));
	}
});

test("request enforces explicit tool authorization and unique tool ids", () => {
	const cases = [
		[{ tool_id: "tool", allowed: true, authorization_id: null, idempotency_key: "key" }],
		[{ tool_id: "tool", allowed: true, authorization_id: "auth", idempotency_key: null }],
		[{ tool_id: "tool", allowed: false, authorization_id: "auth", idempotency_key: null }],
		[
			{ tool_id: "tool", allowed: false, authorization_id: null, idempotency_key: null },
			{ tool_id: "tool", allowed: false, authorization_id: null, idempotency_key: null },
		],
	];
	for (const tools of cases) {
		const value = requestPayload();
		value.available_tools = tools;
		rejects(() => validateDirectorRuntimeRequest(value));
	}
});

test("open snapshots retain safe bounded JSON and reject nested sensitive keys", () => {
	const value = requestPayload();
	const safe = { custom_domain_fact: { nested: [1, true, "value"] } };
	value.authoritative_facts = safe;
	value.active_discussion_workspace = safe;
	value.relevant_discussion_events = [safe];
	value.active_formalization = { proposal: safe, plan_version: safe };
	value.permission_context = safe;
	assert.deepEqual(validateDirectorRuntimeRequest(value).authoritative_facts, safe);

	for (const key of ["api_key", "secret", "credential", "password", "authorization", "token", "access_token"]) {
		const sensitive = requestPayload();
		sensitive.authoritative_facts = { nested: { [key]: "must-not-cross" } };
		rejects(() => validateDirectorRuntimeRequest(sensitive));
	}
});

test("result is closed, correlated, and atomic", () => {
	assert.deepEqual(validateDirectorTurnResult(resultPayload()).request_id, "request-1");
	const cases = [
		(value) => { value.schema_version = "v2"; },
		(value) => { value.unexpected = true; },
		(value) => { value.turn_semantics.unexpected = true; },
		(value) => { value.discussion_lifecycle.unexpected = true; },
		(value) => { value.formalization.unexpected = true; },
		(value) => { value.runtime_metadata.unexpected = true; },
		(value) => { value.error = { code: "safe", stage: "runtime", retryable: false, safe_message: "safe", unexpected: true }; },
		(value) => { value.error = { code: "safe", stage: "runtime", retryable: false, safe_message: "safe" }; value.discussion_delta_candidate = { candidate: true }; },
		(value) => { value.error = { code: "safe", stage: "runtime", retryable: false, safe_message: "safe" }; value.formalization.proposal_candidate = { candidate: true }; },
	];
	for (const mutate of cases) {
		const value = resultPayload();
		mutate(value);
		rejects(() => validateDirectorTurnResult(value));
	}
	rejects(() => validateResultForRequest(validateDirectorRuntimeRequest(requestPayload()), resultPayload("other-request")));
});

test("result rejects sensitive candidate keys and unauthorized tool activity", () => {
	for (const key of ["api_key", "secret", "credential", "password", "authorization", "token", "access_token"]) {
		const value = resultPayload();
		value.discussion_delta_candidate = { nested: { [key]: "sensitive" } };
		rejects(() => validateDirectorTurnResult(value));
	}
	const request = requestPayload();
	request.available_tools = [{ tool_id: "tool", allowed: true, authorization_id: "auth", idempotency_key: "key" }];
	for (const activity of [
		{ tool_id: "unknown", authorization_id: "auth", idempotency_key: "key" },
		{ tool_id: "tool", authorization_id: "wrong", idempotency_key: "key" },
		{ tool_id: "tool", authorization_id: "auth", idempotency_key: "wrong" },
	]) {
		const result = resultPayload();
		result.tool_activity = [{ ...activity, status: "succeeded", safe_summary: null }];
		rejects(() => validateResultForRequest(validateDirectorRuntimeRequest(request), result));
	}
});
