export const DIRECTOR_RUNTIME_SCHEMA_VERSION = "p26-big-director-runtime/v1" as const;

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export type DirectorRuntimeRequest = {
	schema_version: typeof DIRECTOR_RUNTIME_SCHEMA_VERSION;
	request_id: string;
	project_id: string;
	session_id: string;
	message_id: string;
	current_user_message: {
		content: string;
		occurred_at: string;
		actor_claim: "user";
	};
	authoritative_facts: JsonObject;
	active_discussion_workspace: JsonObject | null;
	relevant_discussion_events: JsonObject[];
	active_formalization: {
		proposal: JsonObject | null;
		plan_version: JsonObject | null;
	};
	governance_boundaries: {
		authoritative_write: false;
		director_may_modify_code: false;
		formalization_requires_explicit_request: true;
		confirmation_is_separate: true;
		execution_boundary: "no_task_run_agent_session_before_execution";
	};
	available_skills: Array<{ skill_id: string; version: string; enabled: boolean }>;
	available_tools: Array<{
		tool_id: string;
		allowed: boolean;
		authorization_id: string | null;
		idempotency_key: string | null;
	}>;
	permission_context: JsonObject;
	runtime_config: {
		model_id: string;
		provider_profile_id: string;
		timeout_ms: number;
		max_tool_rounds: number;
	};
};

export type ToolActivityStatus =
	| "requested"
	| "authorized"
	| "started"
	| "succeeded"
	| "failed"
	| "cancelled";

export type DirectorTurnResult = {
	schema_version: typeof DIRECTOR_RUNTIME_SCHEMA_VERSION;
	request_id: string;
	response_text: string;
	turn_semantics: {
		conversation_mode: string;
		formal_action_requested: boolean;
		hypothetical_action: boolean;
		confidence: number | null;
	};
	discussion_lifecycle: {
		observed_status: string | null;
		suggested_next_status: string | null;
	};
	discussion_delta_candidate: JsonObject | null;
	formalization: {
		proposal_candidate: JsonObject | null;
		readiness: "not_ready" | "candidate" | "requires_confirmation";
	};
	tool_activity: Array<{
		tool_id: string;
		authorization_id: string | null;
		status: ToolActivityStatus;
		idempotency_key: string | null;
		safe_summary: string | null;
	}>;
	source_references: Array<{ message_id: string; kind: string }>;
	runtime_metadata: {
		runtime_state: "ready" | "busy" | "degraded" | "failed";
		model_id: string;
		provider_profile_id: string;
		usage: Record<string, number | null>;
		duration_ms: number;
		attempt: number;
	};
	error: {
		code: string;
		stage: "request" | "model" | "tool" | "result_validation" | "runtime";
		retryable: boolean;
		safe_message: string;
	} | null;
};

export class DirectorRuntimeContractError extends Error {
	public constructor(
		public readonly code: string,
		message: string,
	) {
		super(message);
		this.name = "DirectorRuntimeContractError";
	}
}

const toolActivityStatuses = new Set<ToolActivityStatus>([
	"requested",
	"authorized",
	"started",
	"succeeded",
	"failed",
	"cancelled",
]);
const resultRuntimeStates = new Set(["ready", "busy", "degraded", "failed"]);
const errorStages = new Set(["request", "model", "tool", "result_validation", "runtime"]);
const formalizationReadiness = new Set(["not_ready", "candidate", "requires_confirmation"]);
const sensitiveKey = /(?:api[_-]?key|(?:^|[_-])token(?:$|[_-]value)|auth(?:orization)?|credential|password|secret)/i;
const canonicalTimestamp = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-](\d{2}):(\d{2}))$/;

export function validateDirectorRuntimeRequest(value: unknown): DirectorRuntimeRequest {
	const request = object(value, "request");
	assertExactKeys(request, "request", ["schema_version", "request_id", "project_id", "session_id", "message_id", "current_user_message", "authoritative_facts", "active_discussion_workspace", "relevant_discussion_events", "active_formalization", "governance_boundaries", "available_skills", "available_tools", "permission_context", "runtime_config"]);
	requireSchemaVersion(request, "request");
	const currentUserMessage = object(request.current_user_message, "current_user_message");
	const activeFormalization = object(request.active_formalization, "active_formalization");
	const governance = object(request.governance_boundaries, "governance_boundaries");
	const runtimeConfig = object(request.runtime_config, "runtime_config");
	assertExactKeys(currentUserMessage, "current_user_message", ["content", "occurred_at", "actor_claim"]);
	assertExactKeys(activeFormalization, "active_formalization", ["proposal", "plan_version"]);
	assertExactKeys(governance, "governance_boundaries", ["authoritative_write", "director_may_modify_code", "formalization_requires_explicit_request", "confirmation_is_separate", "execution_boundary"]);
	assertExactKeys(runtimeConfig, "runtime_config", ["model_id", "provider_profile_id", "timeout_ms", "max_tool_rounds"]);

	for (const field of ["request_id", "project_id", "session_id", "message_id"] as const) {
		requireNonBlankString(request[field], field);
	}
	requireNonBlankString(currentUserMessage.content, "current_user_message.content");
	requireIsoDate(currentUserMessage.occurred_at, "current_user_message.occurred_at");
	if (currentUserMessage.actor_claim !== "user") fail("request_actor_claim_invalid");

	assertJsonObject(request.authoritative_facts, "authoritative_facts");
	assertNullableJsonObject(request.active_discussion_workspace, "active_discussion_workspace");
	assertJsonObjectArray(request.relevant_discussion_events, "relevant_discussion_events");
	assertNullableJsonObject(activeFormalization.proposal, "active_formalization.proposal");
	assertNullableJsonObject(activeFormalization.plan_version, "active_formalization.plan_version");
	assertJsonObject(request.permission_context, "permission_context");

	if (
		governance.authoritative_write !== false ||
		governance.director_may_modify_code !== false ||
		governance.formalization_requires_explicit_request !== true ||
		governance.confirmation_is_separate !== true ||
		governance.execution_boundary !== "no_task_run_agent_session_before_execution"
	) {
		fail("request_governance_boundaries_invalid");
	}

	const skills = array(request.available_skills, "available_skills");
	for (const [index, skill] of skills.entries()) {
		const item = object(skill, `available_skills[${index}]`);
		assertExactKeys(item, `available_skills[${index}]`, ["skill_id", "version", "enabled"]);
		requireNonBlankString(item.skill_id, `available_skills[${index}].skill_id`);
		requireNonBlankString(item.version, `available_skills[${index}].version`);
		requireBoolean(item.enabled, `available_skills[${index}].enabled`);
	}

	const tools = array(request.available_tools, "available_tools");
	const toolIds = new Set<string>();
	for (const [index, tool] of tools.entries()) {
		const item = object(tool, `available_tools[${index}]`);
		assertExactKeys(item, `available_tools[${index}]`, ["tool_id", "allowed", "authorization_id", "idempotency_key"]);
		requireNonBlankString(item.tool_id, `available_tools[${index}].tool_id`);
		if (toolIds.has(item.tool_id as string)) fail("request_tool_id_duplicate");
		toolIds.add(item.tool_id as string);
		requireBoolean(item.allowed, `available_tools[${index}].allowed`);
		assertNullableNonBlankString(item.authorization_id, `available_tools[${index}].authorization_id`);
		assertNullableNonBlankString(item.idempotency_key, `available_tools[${index}].idempotency_key`);
		if (item.allowed && (item.authorization_id === null || item.idempotency_key === null)) {
			fail("request_tool_authorization_incomplete");
		}
		if (!item.allowed && (item.authorization_id !== null || item.idempotency_key !== null)) {
			fail("request_tool_authorization_implicit");
		}
	}

	requireNonBlankString(runtimeConfig.model_id, "runtime_config.model_id");
	requireNonBlankString(runtimeConfig.provider_profile_id, "runtime_config.provider_profile_id");
	requirePositiveFiniteNumber(runtimeConfig.timeout_ms, "runtime_config.timeout_ms");
	requireNonNegativeInteger(runtimeConfig.max_tool_rounds, "runtime_config.max_tool_rounds");
	return request as DirectorRuntimeRequest;
}

export function validateDirectorTurnResult(value: unknown): DirectorTurnResult {
	const result = object(value, "result");
	assertExactKeys(result, "result", ["schema_version", "request_id", "response_text", "turn_semantics", "discussion_lifecycle", "discussion_delta_candidate", "formalization", "tool_activity", "source_references", "runtime_metadata", "error"]);
	requireSchemaVersion(result, "result");
	requireNonBlankString(result.request_id, "request_id");
	requireString(result.response_text, "response_text");
	const semantics = object(result.turn_semantics, "turn_semantics");
	assertExactKeys(semantics, "turn_semantics", ["conversation_mode", "formal_action_requested", "hypothetical_action", "confidence"]);
	requireNonBlankString(semantics.conversation_mode, "turn_semantics.conversation_mode");
	requireBoolean(semantics.formal_action_requested, "turn_semantics.formal_action_requested");
	requireBoolean(semantics.hypothetical_action, "turn_semantics.hypothetical_action");
	assertNullableFiniteNumber(semantics.confidence, "turn_semantics.confidence");

	const lifecycle = object(result.discussion_lifecycle, "discussion_lifecycle");
	assertExactKeys(lifecycle, "discussion_lifecycle", ["observed_status", "suggested_next_status"]);
	assertNullableString(lifecycle.observed_status, "discussion_lifecycle.observed_status");
	assertNullableString(lifecycle.suggested_next_status, "discussion_lifecycle.suggested_next_status");
	assertNullableJsonObject(result.discussion_delta_candidate, "discussion_delta_candidate");

	const formalization = object(result.formalization, "formalization");
	assertExactKeys(formalization, "formalization", ["proposal_candidate", "readiness"]);
	assertNullableJsonObject(formalization.proposal_candidate, "formalization.proposal_candidate");
	if (typeof formalization.readiness !== "string" || !formalizationReadiness.has(formalization.readiness)) {
		fail("result_formalization_readiness_invalid");
	}

	const activities = array(result.tool_activity, "tool_activity");
	for (const [index, activity] of activities.entries()) {
		const item = object(activity, `tool_activity[${index}]`);
		assertExactKeys(item, `tool_activity[${index}]`, ["tool_id", "authorization_id", "status", "idempotency_key", "safe_summary"]);
		requireNonBlankString(item.tool_id, `tool_activity[${index}].tool_id`);
		assertNullableNonBlankString(item.authorization_id, `tool_activity[${index}].authorization_id`);
		assertNullableNonBlankString(item.idempotency_key, `tool_activity[${index}].idempotency_key`);
		assertNullableString(item.safe_summary, `tool_activity[${index}].safe_summary`);
		if (typeof item.status !== "string" || !toolActivityStatuses.has(item.status as ToolActivityStatus)) {
			fail("result_tool_activity_status_invalid");
		}
	}

	const references = array(result.source_references, "source_references");
	for (const [index, reference] of references.entries()) {
		const item = object(reference, `source_references[${index}]`);
		assertExactKeys(item, `source_references[${index}]`, ["message_id", "kind"]);
		requireNonBlankString(item.message_id, `source_references[${index}].message_id`);
		requireNonBlankString(item.kind, `source_references[${index}].kind`);
	}

	const metadata = object(result.runtime_metadata, "runtime_metadata");
	assertExactKeys(metadata, "runtime_metadata", ["runtime_state", "model_id", "provider_profile_id", "usage", "duration_ms", "attempt"]);
	if (typeof metadata.runtime_state !== "string" || !resultRuntimeStates.has(metadata.runtime_state)) {
		fail("result_runtime_state_invalid");
	}
	requireNonBlankString(metadata.model_id, "runtime_metadata.model_id");
	requireNonBlankString(metadata.provider_profile_id, "runtime_metadata.provider_profile_id");
	assertUsage(metadata.usage);
	requireNonNegativeFiniteNumber(metadata.duration_ms, "runtime_metadata.duration_ms");
	requireNonNegativeInteger(metadata.attempt, "runtime_metadata.attempt");
	assertError(result.error);
	if (result.error !== null && (result.discussion_delta_candidate !== null || formalization.proposal_candidate !== null)) {
		fail("result_error_cannot_include_candidate");
	}
	return result as DirectorTurnResult;
}

export function validateResultForRequest(request: DirectorRuntimeRequest, value: unknown): DirectorTurnResult {
	const result = validateDirectorTurnResult(value);
	if (result.request_id !== request.request_id) fail("result_request_id_mismatch");
	const authorizations = new Map(request.available_tools.map((tool) => [tool.tool_id, tool]));
	for (const activity of result.tool_activity) {
		const authorization = authorizations.get(activity.tool_id);
		if (
			authorization === undefined ||
			!authorization.allowed ||
			authorization.authorization_id !== activity.authorization_id ||
			authorization.idempotency_key !== activity.idempotency_key
		) {
			fail("result_tool_activity_unauthorized");
		}
	}
	return result;
}

function object(value: unknown, path: string): Record<string, unknown> {
	if (value === null || typeof value !== "object" || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) {
		fail(`${path}_must_be_object`);
	}
	return value as Record<string, unknown>;
}

function assertExactKeys(value: Record<string, unknown>, path: string, allowed: string[]): void {
	const allowedKeys = new Set(allowed);
	for (const key of Object.keys(value)) {
		if (!allowedKeys.has(key)) fail(`${path}_unexpected_key`);
	}
}

function array(value: unknown, path: string): unknown[] {
	if (!Array.isArray(value)) fail(`${path}_must_be_array`);
	return value;
}

function requireSchemaVersion(value: Record<string, unknown>, path: string): void {
	if (value.schema_version !== DIRECTOR_RUNTIME_SCHEMA_VERSION) fail(`${path}_schema_version_invalid`);
}

function requireString(value: unknown, path: string): void {
	if (typeof value !== "string") fail(`${path}_must_be_string`);
}

function requireNonBlankString(value: unknown, path: string): void {
	if (typeof value !== "string" || value.trim() !== value || value.length === 0) fail(`${path}_must_be_non_blank_string`);
}

function assertNullableNonBlankString(value: unknown, path: string): void {
	if (value !== null) requireNonBlankString(value, path);
}

function assertNullableString(value: unknown, path: string): void {
	if (value !== null) requireString(value, path);
}

function requireBoolean(value: unknown, path: string): void {
	if (typeof value !== "boolean") fail(`${path}_must_be_boolean`);
}

function requirePositiveFiniteNumber(value: unknown, path: string): void {
	if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) fail(`${path}_must_be_positive_number`);
}

function requireNonNegativeFiniteNumber(value: unknown, path: string): void {
	if (typeof value !== "number" || !Number.isFinite(value) || value < 0) fail(`${path}_must_be_non_negative_number`);
}

function requireNonNegativeInteger(value: unknown, path: string): void {
	if (typeof value !== "number" || !Number.isInteger(value) || value < 0) fail(`${path}_must_be_non_negative_integer`);
}

function assertNullableFiniteNumber(value: unknown, path: string): void {
	if (value !== null && (typeof value !== "number" || !Number.isFinite(value))) fail(`${path}_must_be_nullable_finite_number`);
}

function requireIsoDate(value: unknown, path: string): void {
	requireNonBlankString(value, path);
	const timestamp = value as string;
	const match = canonicalTimestamp.exec(timestamp);
	if (match === null) fail(`${path}_must_be_iso_date`);
	const [year, month, day, hour, minute, second, offsetHour, offsetMinute] = [
		Number(match[1]),
		Number(match[2]),
		Number(match[3]),
		Number(match[4]),
		Number(match[5]),
		Number(match[6]),
		Number(match[8] ?? 0),
		Number(match[9] ?? 0),
	];
	const daysInMonth = [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1] ?? 0;
	if (
		year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth ||
		hour > 23 || minute > 59 || second > 59 || offsetHour > 23 || offsetMinute > 59
	) {
		fail(`${path}_must_be_iso_date`);
	}
}

function assertJsonObject(value: unknown, path: string): asserts value is JsonObject {
	const candidate = object(value, path);
	assertBoundedJson(candidate, path);
}

function assertNullableJsonObject(value: unknown, path: string): void {
	if (value !== null) assertJsonObject(value, path);
}

function assertJsonObjectArray(value: unknown, path: string): void {
	for (const [index, entry] of array(value, path).entries()) assertJsonObject(entry, `${path}[${index}]`);
}

function assertBoundedJson(value: unknown, path: string): asserts value is JsonValue {
	if (value === null || typeof value === "string" || typeof value === "boolean") return;
	if (typeof value === "number") {
		if (Number.isFinite(value)) return;
		fail(`${path}_must_be_json_value`);
	}
	if (Array.isArray(value)) {
		for (const [index, entry] of value.entries()) assertBoundedJson(entry, `${path}[${index}]`);
		return;
	}
	const candidate = object(value, path);
	for (const [key, entry] of Object.entries(candidate)) {
		if (sensitiveKey.test(key)) fail(`${path}_contains_sensitive_handle`);
		assertBoundedJson(entry, `${path}.${key}`);
	}
}

function assertUsage(value: unknown): void {
	const usage = object(value, "runtime_metadata.usage");
	for (const [key, entry] of Object.entries(usage)) {
		requireNonBlankString(key, "runtime_metadata.usage_key");
		assertNullableFiniteNumber(entry, `runtime_metadata.usage.${key}`);
	}
}

function assertError(value: unknown): void {
	if (value === null) return;
	const error = object(value, "error");
	assertExactKeys(error, "error", ["code", "stage", "retryable", "safe_message"]);
	requireNonBlankString(error.code, "error.code");
	if (typeof error.stage !== "string" || !errorStages.has(error.stage)) fail("error.stage_invalid");
	requireBoolean(error.retryable, "error.retryable");
	requireNonBlankString(error.safe_message, "error.safe_message");
}

function fail(code: string): never {
	throw new DirectorRuntimeContractError(code, `Director runtime contract validation failed: ${code}`);
}
