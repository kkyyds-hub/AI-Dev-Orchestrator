import assert from "node:assert/strict";
import test from "node:test";

const { createDirectorFactTools } = await import("../dist/director-fact-tools.js");
const { executeDirectorRuntimeRequest, createSyntheticStreamFn } = await import("../dist/director-runtime.js");
const { createAssistantMessageEventStream } = await import("../dist/node_modules/@earendil-works/pi-ai/dist/index.js");

function request(projectId = "project-a", overrides = {}) {
  return {
    request_id: "turn-1",
    project_id: projectId,
    session_id: "session-a",
    message_id: "message-a",
    runtime_config: { max_tool_rounds: 3 },
    available_tools: [{ tool_id: "director_read_fact", allowed: true, authorization_id: "auth-a", idempotency_key: "read-a" }],
    authoritative_facts: {
      project_snapshot: { id: projectId, name: `Project ${projectId}`, summary: "Grounded summary", status: "active", stage: "intake", task_stats: { total_tasks: 2 } },
      task_snapshot: { total: 2, returned: 1, has_more: true, ordered_by: "updated_at_desc", items: [{ id: "task-a", title: "Only visible task", status: "pending", priority: "medium", risk_level: "low", owner_role_code: null, human_status: "pending", updated_at: "2026-09-16T00:00:00Z" }] },
      repository_snapshot: { workspace: { display_name: "repo-a", access_mode: "read_only", default_base_branch: "main" }, latest_scan: null },
    },
    ...overrides,
  };
}

async function read(tool, selector) {
  const result = await tool.execute("call-1", { selector });
  return JSON.parse(result.content[0].text);
}

function runtimeRequest() {
  const source = request("project-a");
  Object.assign(source, {
    schema_version: "p26-big-director-runtime/v1",
    current_user_message: { content: "What is the project?", occurred_at: "2026-09-16T00:00:00Z", actor_claim: "user" },
    recent_raw_messages: { items: [], has_more_before: false },
    active_discussion_workspace: null,
    relevant_discussion_events: [],
    active_formalization: { proposal: null, plan_version: null },
    governance_boundaries: { authoritative_write: false, director_may_modify_code: false, formalization_requires_explicit_request: true, confirmation_is_separate: true, execution_boundary: "no_task_run_agent_session_before_execution" },
    available_skills: [],
    permission_context: {},
    runtime_config: { model_id: "local", provider_profile_id: "local", timeout_ms: 1000, max_tool_rounds: 1 },
  });
  return source;
}

test("only the Python-authorized current-request tool is registered", async () => {
  assert.deepEqual(createDirectorFactTools(request("project-a", { available_tools: [] }), []), []);
  assert.deepEqual(createDirectorFactTools(request("project-a", { available_tools: [{ tool_id: "director_read_fact", allowed: false, authorization_id: null, idempotency_key: null }] }), []), []);
  assert.deepEqual(createDirectorFactTools(request("project-a", { runtime_config: { max_tool_rounds: 0 } }), []), []);
  const activities = [];
  const [tool] = createDirectorFactTools(request(), activities);
  assert.equal(tool.name, "director_read_fact");
  const response = await read(tool, "project");
  assert.equal(response.status, "ok");
  assert.equal(response.project_id, "project-a");
  assert.equal(response.snapshot.name, "Project project-a");
  assert.deepEqual(activities, [{ tool_id: "director_read_fact", authorization_id: "auth-a", status: "succeeded", idempotency_key: "read-a", safe_summary: "Read project facts from the current request." }]);
});

test("selectors stay inside one request and report partial or missing evidence", async () => {
  const [a] = createDirectorFactTools(request("project-a"), []);
  const [b] = createDirectorFactTools(request("project-b"), []);
  assert.equal((await read(a, "project")).snapshot.name, "Project project-a");
  assert.equal((await read(b, "project")).snapshot.name, "Project project-b");
  const task = await read(a, "task");
  assert.equal(task.status, "partial");
  assert.equal(task.snapshot.returned, 1);
  assert.equal(task.evidence_gap, "Only the bounded task window is available.");
  const repository = await read(a, "repository");
  assert.equal(repository.status, "partial");
  assert.equal(repository.evidence_gap, "No repository scan is present in this request.");
  const [scanned] = createDirectorFactTools(request("project-a", { authoritative_facts: {
    project_snapshot: { id: "project-a", name: "Project project-a", summary: "Grounded summary", status: "active", stage: "intake", task_stats: { total_tasks: 0 } },
    repository_snapshot: { workspace: { display_name: "repo-a", access_mode: "read_only", default_base_branch: "main" }, latest_scan: { status: "success", scanned_at: "2026-01-01T00:00:00Z", file_count: 12, language_breakdown_truncated: false } },
  } }), []);
  assert.equal((await read(scanned, "repository")).status, "partial");
  assert.match((await read(scanned, "repository")).evidence_gap, /may not reflect current/);
  const [missing] = createDirectorFactTools(request("project-a", { authoritative_facts: {} }), []);
  assert.equal((await read(missing, "project")).status, "evidence_gap");
  assert.equal((await read(missing, "task")).status, "evidence_gap");
  assert.equal((await read(missing, "repository")).status, "evidence_gap");
  const [incomplete] = createDirectorFactTools(request("project-a", { authoritative_facts: { project_snapshot: { id: "project-a" } } }), []);
  assert.equal((await read(incomplete, "project")).status, "evidence_gap");
  const inconsistentFacts = request("project-a");
  inconsistentFacts.authoritative_facts.task_snapshot.has_more = false;
  const [inconsistent] = createDirectorFactTools(inconsistentFacts, []);
  assert.equal((await read(inconsistent, "task")).status, "evidence_gap");
  const staleFacts = request("project-a");
  staleFacts.authoritative_facts.project_snapshot.task_stats.total_tasks = 99;
  const [stale] = createDirectorFactTools(staleFacts, []);
  assert.equal((await read(stale, "task")).status, "evidence_gap");
});

test("invalid selector and exceeded call budget fail without reading another source", async () => {
  const activities = [];
  const [tool] = createDirectorFactTools(request("project-a", { runtime_config: { max_tool_rounds: 1 } }), activities);
  assert.equal((await read(tool, "project")).status, "ok");
  assert.equal((await read(tool, "unknown")).status, "evidence_gap");
  assert.equal(activities[1].status, "failed");
  assert.equal(activities[1].safe_summary, "Read-only fact tool call limit reached.");
});

test("Agent executes the authorized read and returns protocol-valid activity", async () => {
  const source = runtimeRequest();
  let calls = 0;
  const streamFn = (model, context) => {
    calls += 1;
    assert.equal(context.tools.length, 1);
    if (calls === 2) {
      const prior = JSON.stringify(context.messages);
      assert.match(prior, /Project project-a/);
      return createSyntheticStreamFn("Grounded answer")(model, context);
    }
    const stream = createAssistantMessageEventStream();
    stream.push({
      type: "done", reason: "toolUse",
      message: {
        role: "assistant", content: [{ type: "toolCall", id: "call-1", name: "director_read_fact", arguments: { selector: "project" } }],
        api: model.api, provider: model.provider, model: model.id,
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "toolUse", timestamp: Date.now(),
      },
    });
    return stream;
  };
  const result = await executeDirectorRuntimeRequest(source, streamFn);
  assert.equal(calls, 2);
  assert.equal(result.response_text, "Grounded answer");
  assert.deepEqual(result.tool_activity, [{ tool_id: "director_read_fact", authorization_id: "auth-a", status: "succeeded", idempotency_key: "read-a", safe_summary: "Read project facts from the current request." }]);
  assert.equal(result.discussion_delta_candidate, null);
  assert.equal(result.formalization.proposal_candidate, null);
});

test("Agent records rejected tool arguments without any authoritative candidate", async () => {
  const source = runtimeRequest();
  let calls = 0;
  const streamFn = (model, context) => {
    calls += 1;
    const stream = createAssistantMessageEventStream();
    stream.push({
      type: "done", reason: "toolUse",
      message: {
        role: "assistant", content: [{ type: "toolCall", id: "bad-call", name: "director_read_fact", arguments: { selector: "external_file" } }],
        api: model.api, provider: model.provider, model: model.id,
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "toolUse", timestamp: Date.now(),
      },
    });
    return stream;
  };
  const result = await executeDirectorRuntimeRequest(source, streamFn);
  assert.equal(calls, 1);
  assert.equal(result.error.stage, "tool");
  assert.equal(result.tool_activity[0].status, "failed");
  assert.equal(result.discussion_delta_candidate, null);
  assert.equal(result.formalization.proposal_candidate, null);
});

test("repeated tool requests stop after the authorized call budget", async () => {
  const source = runtimeRequest();
  let calls = 0;
  const streamFn = (model, context) => {
    calls += 1;
    if (calls === 4) return createSyntheticStreamFn("Too late")(model, context);
    const stream = createAssistantMessageEventStream();
    stream.push({
      type: "done", reason: "toolUse",
      message: {
        role: "assistant", content: [{ type: "toolCall", id: `call-${calls}`, name: "director_read_fact", arguments: { selector: "project" } }],
        api: model.api, provider: model.provider, model: model.id,
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "toolUse", timestamp: Date.now(),
      },
    });
    return stream;
  };
  const result = await executeDirectorRuntimeRequest(source, streamFn);
  assert.equal(calls, 2);
  assert.equal(result.error.stage, "tool");
  assert.deepEqual(result.tool_activity.map((activity) => activity.status), ["succeeded", "failed"]);
  assert.equal(result.discussion_delta_candidate, null);
});
