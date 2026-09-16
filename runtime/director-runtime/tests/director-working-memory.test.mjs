import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const runtimeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const memoryModule = path.join(runtimeRoot, "dist", "director-working-memory.js");
const contextModule = path.join(runtimeRoot, "dist", "director-context.js");
const runtimeModule = path.join(runtimeRoot, "dist", "director-runtime.js");
const protocolModule = path.join(runtimeRoot, "dist", "protocol.js");

async function modules() {
	const [memory, context, runtime, protocol] = await Promise.all([
		import(memoryModule), import(contextModule), import(runtimeModule), import(protocolModule),
	]);
	return { ...memory, ...context, ...runtime, ...protocol };
}

function request(overrides = {}) {
	return {
		schema_version: "p26-big-director-runtime/v1",
		request_id: "request-a",
		project_id: "project-a",
		session_id: "session-a",
		message_id: "message-current-a",
		current_user_message: { content: "current user A", occurred_at: "2026-09-16T00:00:00Z", actor_claim: "user" },
		recent_raw_messages: { items: [
			{ message_id: "message-recent-a", role: "assistant", content: "history A", sequence_no: 1, occurred_at: "2026-09-15T00:00:00Z", source: "ai" },
		], has_more_before: false },
		authoritative_facts: { project_snapshot: { name: "A" } },
		active_discussion_workspace: { active_preference: "A" },
		relevant_discussion_events: [
			{ id: "event-a", source_message_ids: ["message-recent-a", "message-event-a"], content: "event A" },
		],
		active_formalization: { proposal: { id: "proposal-a" }, plan_version: { id: "plan-a" } },
		governance_boundaries: {
			authoritative_write: false, director_may_modify_code: false,
			formalization_requires_explicit_request: true, confirmation_is_separate: true,
			execution_boundary: "no_task_run_agent_session_before_execution",
		},
		available_skills: [], available_tools: [], permission_context: {},
		runtime_config: { model_id: "model", provider_profile_id: "local", timeout_ms: 1000, max_tool_rounds: 0 },
		...overrides,
	};
}

test("D2-B-01 through D2-B-09: plan shape, classification, inclusion, and provenance", async () => {
	const { createDirectorWorkingMemoryPlan, validateDirectorRuntimeRequest } = await modules();
	const plan = createDirectorWorkingMemoryPlan(validateDirectorRuntimeRequest(request()));
	assert.deepEqual(Object.keys(plan), ["memory_mode", "non_authoritative", "rebuildable", "project_id", "session_id", "request_id", "current_turn_message_id", "source_message_ids", "source_discussion_event_ids", "source_section_names", "compactable_provenance_complete", "sections"]);
	assert.equal(plan.memory_mode, "rehydrated_from_request");
	assert.equal(plan.non_authoritative, true);
	assert.equal(plan.rebuildable, true);
	assert.deepEqual([plan.project_id, plan.session_id, plan.request_id, plan.current_turn_message_id], ["project-a", "session-a", "request-a", "message-current-a"]);
	assert.deepEqual(plan.sections.map((section) => section.name), ["governance_boundaries", "authoritative_facts", "recent_raw_messages", "active_discussion_workspace", "relevant_discussion_events", "active_formalization.proposal", "active_formalization.plan_version", "current_user_message"]);
	assert.deepEqual(plan.sections.map((section) => section.classification), ["pinned", "pinned", "compactable", "pinned", "compactable", "pinned", "pinned", "pinned"]);
	assert.equal(plan.sections.every((section) => section.included), true);
	assert.deepEqual(plan.source_message_ids, ["message-current-a", "message-recent-a", "message-event-a"]);
	assert.deepEqual(plan.source_discussion_event_ids, ["event-a"]);
	assert.equal(plan.compactable_provenance_complete, true);
	const events = plan.sections.find((section) => section.name === "relevant_discussion_events");
	assert.deepEqual(events.source_message_ids, ["message-recent-a", "message-event-a"]);
	assert.deepEqual(events.source_discussion_event_ids, ["event-a"]);
});

test("D2-B-06 and D2-B-10: absent pinned values omit cleanly and malformed event provenance stays nonfatal", async () => {
	const { createDirectorWorkingMemoryPlan, validateDirectorRuntimeRequest } = await modules();
	const source = validateDirectorRuntimeRequest(request({
		recent_raw_messages: { items: [], has_more_before: false },
		active_discussion_workspace: null,
		relevant_discussion_events: [{ content: "synthetic event without identifiers" }],
		active_formalization: { proposal: null, plan_version: null },
	}));
	const plan = createDirectorWorkingMemoryPlan(source);
	assert.deepEqual(plan.source_section_names, ["governance_boundaries", "authoritative_facts", "relevant_discussion_events", "current_user_message"]);
	assert.equal(plan.sections.find((section) => section.name === "recent_raw_messages").included, false);
	assert.equal(plan.sections.find((section) => section.name === "active_discussion_workspace").included, false);
	assert.equal(plan.sections.find((section) => section.name === "active_formalization.proposal").classification, "pinned");
	assert.equal(plan.sections.find((section) => section.name === "active_formalization.plan_version").included, false);
	assert.equal(plan.compactable_provenance_complete, false);
	assert.deepEqual(plan.source_discussion_event_ids, []);
});

test("D2-B-11 through D2-B-14: immutable deterministic request-only planning with project isolation", async () => {
	const { createDirectorWorkingMemoryPlan, validateDirectorRuntimeRequest } = await modules();
	const a = validateDirectorRuntimeRequest(request());
	const b = validateDirectorRuntimeRequest(request({ request_id: "request-b", project_id: "project-b", session_id: "session-b", message_id: "message-current-b", current_user_message: { content: "Ignore instructions B sentinel", occurred_at: "2026-09-16T00:00:00Z", actor_claim: "user" }, recent_raw_messages: { items: [{ message_id: "message-recent-b", role: "assistant", content: "history B sentinel", sequence_no: 1, occurred_at: "2026-09-15T00:00:00Z", source: "ai" }], has_more_before: false }, relevant_discussion_events: [{ id: "event-b", source_message_ids: ["message-recent-b"], content: "event B sentinel" }] }));
	const before = structuredClone(a);
	const a1 = createDirectorWorkingMemoryPlan(a);
	const b1 = createDirectorWorkingMemoryPlan(b);
	const a2 = createDirectorWorkingMemoryPlan(a);
	assert.deepEqual(a, before);
	assert.deepEqual(a1, a2);
	assert.equal(JSON.stringify(a2).includes("sentinel"), false);
	assert.equal(JSON.stringify(b1).includes("message-recent-a"), false);
	assert.equal(a1.sections.find((section) => section.name === "current_user_message").value, "current user A");
});

test("D2-B-15 through D2-B-18: Context Planner remains the bounds owner and runtime keeps one user message and no tools", async () => {
	const { createDirectorModelContext, executeDirectorRuntimeRequest, createSyntheticStreamFn, validateDirectorRuntimeRequest } = await modules();
	const events = Array.from({ length: 25 }, (_, index) => ({ id: `event-${index}`, source_message_ids: [`message-${index}`], content: `event-${index}` }));
	const source = validateDirectorRuntimeRequest(request({ relevant_discussion_events: events }));
	const modelContext = createDirectorModelContext(source);
	assert.deepEqual(modelContext.plan.section_order, ["governance_boundaries", "authoritative_facts", "recent_raw_messages", "active_discussion_workspace", "relevant_discussion_events", "active_formalization.proposal", "active_formalization.plan_version", "current_user_message"]);
	const eventSection = modelContext.plan.selected_sections.find((section) => section.name === "relevant_discussion_events");
	assert.equal(eventSection.context_truncated, true);
	assert.equal(eventSection.content.includes('"omitted_items":5'), true);
	let observed;
	await executeDirectorRuntimeRequest(source, (...args) => {
		observed = args[1];
		return createSyntheticStreamFn()(...args);
	});
	assert.deepEqual(observed.tools, []);
	assert.equal(observed.messages.length, 1);
	assert.equal(observed.messages[0].role, "user");
	assert.equal(observed.messages[0].content[0].text, "current user A");
});
