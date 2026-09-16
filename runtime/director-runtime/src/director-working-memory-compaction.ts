import type { JsonObject, JsonValue } from "./protocol.js";
import type {
	DirectorWorkingMemoryPlan,
	DirectorWorkingMemorySection,
	DirectorWorkingMemorySectionName,
} from "./director-working-memory.js";

const MINIMUM_TARGET_CHARACTERS = 400;
const MAXIMUM_TARGET_CHARACTERS = 12_000;

export type DirectorWorkingMemorySummary = {
	non_authoritative: true;
	rebuildable: true;
	project_id: string;
	session_id: string;
	source_request_id: string;
	source_turn_identity: { message_id: string };
	summary_text: string;
	source_message_ids: readonly string[];
	source_discussion_event_ids: readonly string[];
	source_section_names: readonly DirectorWorkingMemorySectionName[];
	compaction_applied: true;
	original_size: number;
	compacted_size: number;
	truncated_or_incomplete: true;
};

export type DirectorWorkingMemoryCompactionResult = {
	summary: DirectorWorkingMemorySummary | null;
	reason: "compacted" | "nothing_to_compact" | "provenance_incomplete" | "within_budget";
};

/**
 * Produce a bounded, deterministic projection of compactable working context.
 * This deliberately does not infer facts or summarize semantically.
 */
export function createDirectorWorkingMemorySummary(
	workingMemory: DirectorWorkingMemoryPlan,
	options: { targetCharacters: number },
): DirectorWorkingMemoryCompactionResult {
	const targetCharacters = validateTargetCharacters(options.targetCharacters);
	const sections = workingMemory.sections.filter(
		(section) => section.classification === "compactable" && section.included && section.value !== null,
	);
	if (sections.length === 0) return { summary: null, reason: "nothing_to_compact" };
	if (!workingMemory.compactable_provenance_complete) {
		return { summary: null, reason: "provenance_incomplete" };
	}

	const sourceCorpus = canonicalJson(sections.map((section) => ({ name: section.name, value: section.value! })));
	if (sourceCorpus.length <= targetCharacters) return { summary: null, reason: "within_budget" };

	const sourceSectionNames = sections.map((section) => section.name);
	const summaryText = boundedProjection(sourceCorpus, sourceSectionNames, targetCharacters);
	return {
		summary: {
			non_authoritative: true,
			rebuildable: true,
			project_id: workingMemory.project_id,
			session_id: workingMemory.session_id,
			source_request_id: workingMemory.request_id,
			source_turn_identity: { message_id: workingMemory.current_turn_message_id },
			summary_text: summaryText,
			source_message_ids: uniqueInOrder(sections.flatMap((section) => section.source_message_ids)),
			source_discussion_event_ids: uniqueInOrder(sections.flatMap((section) => section.source_discussion_event_ids)),
			source_section_names: sourceSectionNames,
			compaction_applied: true,
			original_size: sourceCorpus.length,
			compacted_size: summaryText.length,
			truncated_or_incomplete: true,
		},
		reason: "compacted",
	};
}

function validateTargetCharacters(value: number): number {
	if (!Number.isInteger(value) || value < MINIMUM_TARGET_CHARACTERS || value > MAXIMUM_TARGET_CHARACTERS) {
		throw new Error("director_working_memory_compaction_target_invalid");
	}
	return value;
}

function boundedProjection(
	sourceCorpus: string,
	sectionNames: readonly DirectorWorkingMemorySectionName[],
	targetCharacters: number,
): string {
	const render = (prefixLength: number): string => canonicalJson({
		kind: "NON_AUTHORITATIVE_WORKING_MEMORY_PROJECTION",
		compactable_sections: [...sectionNames],
		truncated: true,
		original_characters: sourceCorpus.length,
		rendered_prefix: sourceCorpus.slice(0, prefixLength),
	});
	if (render(0).length > targetCharacters) {
		throw new Error("director_working_memory_compaction_target_too_small");
	}
	let low = 0;
	let high = sourceCorpus.length;
	while (low < high) {
		const midpoint = Math.ceil((low + high) / 2);
		if (render(midpoint).length <= targetCharacters) low = midpoint;
		else high = midpoint - 1;
	}
	return render(low);
}

function canonicalJson(value: JsonValue): string {
	if (value === null || typeof value !== "object") return JSON.stringify(value);
	if (Array.isArray(value)) return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
	const object = value as JsonObject;
	return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(object[key]!)}`).join(",")}}`;
}

function uniqueInOrder(values: readonly string[]): string[] {
	const result: string[] = [];
	for (const value of values) if (!result.includes(value)) result.push(value);
	return result;
}
