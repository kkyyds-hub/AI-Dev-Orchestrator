import type { AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "@earendil-works/pi-ai";

import type { DirectorRuntimeRequest, DirectorTurnResult, JsonObject } from "./protocol.js";

export const DIRECTOR_READ_FACT_TOOL_ID = "director_read_fact";

const parameters = Type.Object({
	selector: Type.Union([
		Type.Literal("project"),
		Type.Literal("task"),
		Type.Literal("repository"),
	]),
}, { additionalProperties: false });

type Activity = DirectorTurnResult["tool_activity"][number];
type FactResult = {
	status: "ok" | "partial" | "evidence_gap";
	project_id: string;
	selector: string;
	snapshot: JsonObject | null;
	evidence_gap: string | null;
};

/** Register only the one capability explicitly authorized by Python for this request. */
export function createDirectorFactTools(
	request: DirectorRuntimeRequest,
	activities: Activity[],
	executedCallIds: Set<string> = new Set(),
): AgentTool[] {
	const grant = request.available_tools.find((entry) => entry.tool_id === DIRECTOR_READ_FACT_TOOL_ID);
	if (
		grant?.allowed !== true
		|| !grant.authorization_id
		|| !grant.idempotency_key
		|| request.runtime_config.max_tool_rounds < 1
	) return [];

	let calls = 0;
	const tool: AgentTool<typeof parameters, FactResult> = {
		name: DIRECTOR_READ_FACT_TOOL_ID,
		label: "Read current project facts",
		description: "Read only project, task, or repository facts already present in this governed request. Missing or bounded evidence is reported explicitly.",
		parameters,
		executionMode: "sequential",
		async execute(callId, params) {
			executedCallIds.add(callId);
			const selector: unknown = params?.selector;
			let result: FactResult;
			let status: Activity["status"] = "succeeded";
			let safeSummary: string;
			if (calls >= request.runtime_config.max_tool_rounds) {
				result = gap(request.project_id, String(selector), "Read-only fact tool call limit reached.");
				status = "failed";
				safeSummary = result.evidence_gap!;
			} else if (selector !== "project" && selector !== "task" && selector !== "repository") {
				result = gap(request.project_id, String(selector), "Unsupported fact selector.");
				status = "failed";
				safeSummary = result.evidence_gap!;
			} else {
				calls += 1;
				result = readCurrentFact(request, selector);
				safeSummary = result.status === "evidence_gap"
					? `No ${selector} facts are available in the current request.`
					: `Read ${selector} facts from the current request.`;
			}
			activities.push({
				tool_id: grant.tool_id,
				authorization_id: grant.authorization_id,
				status,
				idempotency_key: grant.idempotency_key,
				safe_summary: safeSummary,
			});
			return { content: [{ type: "text", text: JSON.stringify(result) }], details: result };
		},
	};
	return [tool];
}

function readCurrentFact(request: DirectorRuntimeRequest, selector: "project" | "task" | "repository"): FactResult {
	const project = request.authoritative_facts.project_snapshot;
	if (!isObject(project) || project.id !== request.project_id
		|| typeof project.name !== "string" || typeof project.summary !== "string"
		|| typeof project.status !== "string" || typeof project.stage !== "string"
		|| !isObject(project.task_stats) || typeof project.task_stats.total_tasks !== "number") {
		return gap(request.project_id, selector, "Current project snapshot is missing or mismatched.");
	}
	if (selector === "project") {
		return { status: "ok", project_id: request.project_id, selector, snapshot: structuredClone(project), evidence_gap: null };
	}
	if (selector === "task") {
		const task = request.authoritative_facts.task_snapshot;
		if (!isObject(task) || !Array.isArray(task.items) || typeof task.has_more !== "boolean"
			|| typeof task.total !== "number" || typeof task.returned !== "number"
			|| !Number.isInteger(task.total) || !Number.isInteger(task.returned)
			|| task.returned !== task.items.length || task.total < task.returned
			|| task.has_more !== (task.total > task.returned)
			|| task.total !== project.task_stats.total_tasks
			|| task.ordered_by !== "updated_at_desc"
			|| task.items.some((item) => !isObject(item) || typeof item.id !== "string"
				|| typeof item.title !== "string" || typeof item.status !== "string"
				|| typeof item.priority !== "string" || typeof item.risk_level !== "string"
				|| typeof item.human_status !== "string" || typeof item.updated_at !== "string")) {
			return gap(request.project_id, selector, "Current task snapshot is missing or inconsistent.");
		}
		return {
			status: task.has_more ? "partial" : "ok",
			project_id: request.project_id,
			selector,
			snapshot: structuredClone(task),
			evidence_gap: task.has_more ? "Only the bounded task window is available." : null,
		};
	}
	const repository = request.authoritative_facts.repository_snapshot;
	if (!isObject(repository) || !("workspace" in repository) || !("latest_scan" in repository)
		|| (repository.workspace !== null && !isObject(repository.workspace))
		|| (repository.latest_scan !== null && !isObject(repository.latest_scan))) {
		return gap(request.project_id, selector, "Current repository snapshot is missing.");
	}
	const scan = repository.latest_scan;
	const evidenceGap = repository.workspace === null
		? "No repository workspace is present in this request."
		: scan === null
			? "No repository scan is present in this request."
			: !isObject(scan) || scan.status !== "success"
				? "The latest recorded repository scan did not succeed."
				: scan.language_breakdown_truncated === true
					? "The recorded language breakdown is truncated."
					: "The latest recorded scan may not reflect current repository state.";
	return {
		status: evidenceGap === null ? "ok" : "partial",
		project_id: request.project_id,
		selector,
		snapshot: structuredClone(repository),
		evidence_gap: evidenceGap,
	};
}

function gap(projectId: string, selector: string, reason: string): FactResult {
	return { status: "evidence_gap", project_id: projectId, selector, snapshot: null, evidence_gap: reason };
}

function isObject(value: unknown): value is JsonObject {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}
