import type { DirectorRuntimeRequest, JsonObject, JsonValue } from "./protocol.js";

export const DIRECTOR_WORKING_MEMORY_SECTION_ORDER = [
	"governance_boundaries",
	"authoritative_facts",
	"recent_raw_messages",
	"active_discussion_workspace",
	"relevant_discussion_events",
	"active_formalization.proposal",
	"active_formalization.plan_version",
	"current_user_message",
] as const;

export type DirectorWorkingMemorySectionName = (typeof DIRECTOR_WORKING_MEMORY_SECTION_ORDER)[number];

export type DirectorWorkingMemorySection = {
	name: DirectorWorkingMemorySectionName;
	classification: "pinned" | "compactable";
	included: boolean;
	value: JsonValue | null;
	source_message_ids: readonly string[];
	source_discussion_event_ids: readonly string[];
};

export type DirectorWorkingMemoryPlan = {
	memory_mode: "rehydrated_from_request";
	non_authoritative: true;
	rebuildable: true;
	project_id: string;
	session_id: string;
	request_id: string;
	current_turn_message_id: string;
	source_message_ids: readonly string[];
	source_discussion_event_ids: readonly string[];
	source_section_names: readonly DirectorWorkingMemorySectionName[];
	compactable_provenance_complete: boolean;
	sections: readonly DirectorWorkingMemorySection[];
};

type EventProvenance = {
	event_id: string | null;
	message_ids: readonly string[];
	complete: boolean;
};

/**
 * Rebuild one disposable, non-authoritative Runtime working-memory plan from a
 * validated request. This is intentionally synchronous and has no state beyond
 * its input: authoritative and governed state stay owned by Python.
 */
export function createDirectorWorkingMemoryPlan(request: DirectorRuntimeRequest): DirectorWorkingMemoryPlan {
	const eventProvenance = request.relevant_discussion_events.map(eventProvenanceFor);
	const recentMessageIds = request.recent_raw_messages.items.map((message) => message.message_id);
	const eventMessageIds = eventProvenance.flatMap((event) => event.message_ids);
	const eventIds = eventProvenance.flatMap((event) => event.event_id === null ? [] : [event.event_id]);
	const sections: readonly DirectorWorkingMemorySection[] = [
		section("governance_boundaries", "pinned", true, request.governance_boundaries),
		section("authoritative_facts", "pinned", true, request.authoritative_facts),
		section(
			"recent_raw_messages",
			"compactable",
			request.recent_raw_messages.items.length > 0,
			request.recent_raw_messages,
			recentMessageIds,
		),
		section(
			"active_discussion_workspace",
			"pinned",
			request.active_discussion_workspace !== null,
			request.active_discussion_workspace,
		),
		section(
			"relevant_discussion_events",
			"compactable",
			request.relevant_discussion_events.length > 0,
			request.relevant_discussion_events,
			eventMessageIds,
			eventIds,
		),
		section(
			"active_formalization.proposal",
			"pinned",
			request.active_formalization.proposal !== null,
			request.active_formalization.proposal,
		),
		section(
			"active_formalization.plan_version",
			"pinned",
			request.active_formalization.plan_version !== null,
			request.active_formalization.plan_version,
		),
		section("current_user_message", "pinned", true, request.current_user_message.content, [request.message_id]),
	];

	return {
		memory_mode: "rehydrated_from_request",
		non_authoritative: true,
		rebuildable: true,
		project_id: request.project_id,
		session_id: request.session_id,
		request_id: request.request_id,
		current_turn_message_id: request.message_id,
		source_message_ids: uniqueInOrder([request.message_id, ...recentMessageIds, ...eventMessageIds]),
		source_discussion_event_ids: uniqueInOrder(eventIds),
		source_section_names: sections.filter((entry) => entry.included).map((entry) => entry.name),
		compactable_provenance_complete: eventProvenance.every((event) => event.complete),
		sections,
	};
}

function section(
	name: DirectorWorkingMemorySectionName,
	classification: DirectorWorkingMemorySection["classification"],
	included: boolean,
	value: JsonValue | null,
	sourceMessageIds: readonly string[] = [],
	sourceDiscussionEventIds: readonly string[] = [],
): DirectorWorkingMemorySection {
	return {
		name,
		classification,
		included,
		value: value === null ? null : structuredClone(value),
		source_message_ids: uniqueInOrder(sourceMessageIds),
		source_discussion_event_ids: uniqueInOrder(sourceDiscussionEventIds),
	};
}

function eventProvenanceFor(event: JsonObject): EventProvenance {
	const rawId = event.id;
	const rawSourceMessageIds = event.source_message_ids;
	const eventId = isNonBlankString(rawId) ? rawId : null;
	const completeSourceMessageIds = Array.isArray(rawSourceMessageIds)
		&& rawSourceMessageIds.every(isNonBlankString);
	return {
		event_id: eventId,
		message_ids: completeSourceMessageIds ? uniqueInOrder(rawSourceMessageIds) : [],
		complete: eventId !== null && completeSourceMessageIds,
	};
}

function isNonBlankString(value: JsonValue | undefined): value is string {
	return typeof value === "string" && value.trim().length > 0;
}

function uniqueInOrder(values: readonly string[]): string[] {
	const result: string[] = [];
	for (const value of values) {
		if (!result.includes(value)) result.push(value);
	}
	return result;
}
