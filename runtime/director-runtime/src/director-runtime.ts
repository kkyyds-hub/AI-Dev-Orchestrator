import {
	Agent,
	type StreamFn,
} from "@earendil-works/pi-agent-core";
import {
	createAssistantMessageEventStream,
	type Api,
	type AssistantMessage,
	type Model,
} from "@earendil-works/pi-ai";
import { fileURLToPath } from "node:url";

import { createOpenAICompatibleRuntime, ENV_PROVIDER_MODE, OPENAI_COMPATIBLE_MODE } from "./provider-stream.js";
import { createDirectorProviderSemanticSummarizer } from "./director-provider-semantic-summarizer.js";
import type { DirectorWorkingMemorySemanticSummarizer } from "./director-working-memory-semantic-compaction.js";
import {
	type DirectorRuntimeRequest,
	type DirectorTurnResult,
	validateDirectorRuntimeRequest,
	validateResultForRequest,
} from "./protocol.js";
import { createDirectorModelContext, createDirectorModelContextWithSemanticWorkingMemory } from "./director-context.js";
import { createDirectorFactTools, DIRECTOR_READ_FACT_TOOL_ID } from "./director-fact-tools.js";

const SYNTHETIC_RESPONSE_TEXT = "synthetic director runtime response";
const SEMANTIC_COMPACTION_MODE = "DIRECTOR_RUNTIME_SEMANTIC_COMPACTION_MODE";
const MINIMUM_SEMANTIC_ATTEMPT_MS = 5_000;
const MAXIMUM_SEMANTIC_TIMEOUT_MS = 10_000;

export async function executeDirectorRuntimeRequest(
	request: DirectorRuntimeRequest,
	streamFn: StreamFn = createSyntheticStreamFn(),
	model: Model<Api> = createSyntheticModel(request),
	options: { semanticSummarizer?: DirectorWorkingMemorySemanticSummarizer } = {},
): Promise<DirectorTurnResult> {
	const startedAt = Date.now();
	const modelContext = semanticTimeoutFor(request) !== null && options.semanticSummarizer !== undefined
		? await createDirectorModelContextWithSemanticWorkingMemory(request, { summarizer: options.semanticSummarizer })
		: createDirectorModelContext(request);
	const toolActivity: DirectorTurnResult["tool_activity"] = [];
	const executedCallIds = new Set<string>();
	const registeredTools = createDirectorFactTools(request, toolActivity, executedCallIds);
	let toolFailure = false;
	const agent = new Agent({
		streamFn,
		shouldStopAfterTurn: () => toolFailure || toolActivity.some((activity) => activity.status === "failed"),
		initialState: {
			model,
			systemPrompt: modelContext.systemPrompt,
			tools: registeredTools,
		},
	});
	if (registeredTools.length > 0) {
		const grant = request.available_tools.find((item) => item.tool_id === DIRECTOR_READ_FACT_TOOL_ID)!;
		agent.subscribe((event) => {
			if (event.type !== "tool_execution_end") return;
			if (event.isError) toolFailure = true;
			if (event.toolName !== DIRECTOR_READ_FACT_TOOL_ID || executedCallIds.has(event.toolCallId)) return;
			// Pi rejects malformed or truncated arguments before execute() runs.
			toolActivity.push({
				tool_id: grant.tool_id,
				authorization_id: grant.authorization_id,
				status: "failed",
				idempotency_key: grant.idempotency_key,
				safe_summary: "Read-only fact tool invocation failed validation.",
			});
		});
	}

	await agent.prompt(modelContext.userPrompt);
	const failedToolAttempt = toolFailure || toolActivity.some((activity) => activity.status === "failed");
	const assistantMessage = agent.state.messages.at(-1);
	if (!failedToolAttempt && (assistantMessage?.role !== "assistant" || assistantMessage.errorMessage)) {
		throw new Error("director_runtime_agent_terminal_state_invalid");
	}
	const responseText = assistantMessage?.role === "assistant" && !failedToolAttempt ? assistantMessage.content
		.filter((content) => content.type === "text")
		.map((content) => content.text)
		.join("") : "";

	return validateResultForRequest(request, {
		schema_version: "p26-big-director-runtime/v1",
		request_id: request.request_id,
		response_text: responseText,
		turn_semantics: {
			conversation_mode: "general_discussion",
			formal_action_requested: false,
			hypothetical_action: false,
			confidence: null,
		},
		discussion_lifecycle: {
			observed_status: null,
			suggested_next_status: null,
		},
		discussion_delta_candidate: null,
		formalization: {
			proposal_candidate: null,
			readiness: "not_ready",
		},
		tool_activity: toolActivity,
		source_references: [{ message_id: request.message_id, kind: "current_user_message" }],
		runtime_metadata: {
			runtime_state: failedToolAttempt ? "failed" : "ready",
			model_id: request.runtime_config.model_id,
			provider_profile_id: request.runtime_config.provider_profile_id,
			usage: {},
			duration_ms: Date.now() - startedAt,
			attempt: 0,
		},
		error: failedToolAttempt ? {
			code: "director_runtime_fact_tool_failed",
			stage: "tool",
			retryable: false,
			safe_message: "The read-only fact tool failed; no authoritative candidate was produced.",
		} : null,
	});
}

export function createSyntheticStreamFn(responseText = SYNTHETIC_RESPONSE_TEXT): StreamFn {
	return (model) => {
		const stream = createAssistantMessageEventStream();
		stream.push({
			type: "done",
			reason: "stop",
			message: createSyntheticAssistantMessage(model, responseText),
		});
		return stream;
	};
}

function createSyntheticModel(request: DirectorRuntimeRequest): Model<"synthetic-director"> {
	return {
		id: request.runtime_config.model_id,
		name: request.runtime_config.model_id,
		api: "synthetic-director",
		provider: "synthetic-local",
		baseUrl: "synthetic://director-runtime",
		reasoning: false,
		input: ["text"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 1024,
		maxTokens: 64,
	};
}

function createSyntheticAssistantMessage<TApi extends Api>(
	model: Model<TApi>,
	responseText: string,
): AssistantMessage {
	return {
		role: "assistant",
		content: [{ type: "text", text: responseText }],
		api: model.api,
		provider: model.provider,
		model: model.id,
		usage: {
			input: 0,
			output: 0,
			cacheRead: 0,
			cacheWrite: 0,
			totalTokens: 0,
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
		},
		stopReason: "stop",
		timestamp: Date.now(),
	};
}

async function main(): Promise<void> {
	try {
		const request = validateDirectorRuntimeRequest(await readRequestLine());
		const runtime = createProcessRuntime(request);
		const semanticTimeout = semanticTimeoutFor(request);
		const semanticSummarizer = semanticTimeout === null
			? undefined
			: createDirectorProviderSemanticSummarizer(runtime.model, runtime.streamFn, { timeoutMs: semanticTimeout });
		const result = await executeDirectorRuntimeRequest(request, runtime.streamFn, runtime.model, { semanticSummarizer });
		process.stdout.write(`${JSON.stringify(result)}\n`);
	} catch {
		process.stderr.write("director_runtime_failed\n");
		process.exitCode = 1;
	}
}

function semanticTimeoutFor(request: DirectorRuntimeRequest): number | null {
	if (
		process.env[SEMANTIC_COMPACTION_MODE] !== "enabled"
		|| process.env[ENV_PROVIDER_MODE] !== OPENAI_COMPATIBLE_MODE
		|| request.runtime_config.timeout_ms < MINIMUM_SEMANTIC_ATTEMPT_MS
	) return null;
	return Math.min(MAXIMUM_SEMANTIC_TIMEOUT_MS, Math.floor(request.runtime_config.timeout_ms / 4));
}

function createProcessRuntime(request: DirectorRuntimeRequest): {
	model: Model<Api>;
	streamFn: StreamFn;
} {
	if (process.env[ENV_PROVIDER_MODE] === OPENAI_COMPATIBLE_MODE) {
		return createOpenAICompatibleRuntime(request);
	}
	return { model: createSyntheticModel(request), streamFn: createProcessSyntheticStreamFn() };
}

function createProcessSyntheticStreamFn(): StreamFn {
	if (process.env.DIRECTOR_RUNTIME_SYNTHETIC_MODE === "throw") {
		return () => {
			throw new Error("synthetic_stream_failure");
		};
	}
	if (process.env.DIRECTOR_RUNTIME_SYNTHETIC_MODE === "block") {
		return async () => await new Promise<never>(() => {});
	}
	return createSyntheticStreamFn();
}

async function readRequestLine(): Promise<unknown> {
	let input = "";
	for await (const chunk of process.stdin) input += chunk;
	const lines = input.split(/\r?\n/).filter((line) => line.length > 0);
	if (lines.length !== 1) throw new Error("director_runtime_input_line_invalid");
	return JSON.parse(lines[0]!);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
	void main();
}
