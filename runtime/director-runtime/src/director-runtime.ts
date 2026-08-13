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

import {
	type DirectorRuntimeRequest,
	type DirectorTurnResult,
	validateDirectorRuntimeRequest,
	validateResultForRequest,
} from "./protocol.js";

const SYNTHETIC_RESPONSE_TEXT = "synthetic director runtime response";

export async function executeDirectorRuntimeRequest(
	request: DirectorRuntimeRequest,
	streamFn: StreamFn = createSyntheticStreamFn(),
): Promise<DirectorTurnResult> {
	const startedAt = Date.now();
	const model = createSyntheticModel(request);
	const agent = new Agent({
		streamFn,
		initialState: {
			model,
			tools: [],
		},
	});

	await agent.prompt(request.current_user_message.content);
	const assistantMessage = agent.state.messages.at(-1);
	if (assistantMessage?.role !== "assistant" || assistantMessage.errorMessage) {
		throw new Error("synthetic_agent_terminal_state_invalid");
	}
	const responseText = assistantMessage.content
		.filter((content) => content.type === "text")
		.map((content) => content.text)
		.join("");

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
		tool_activity: [],
		source_references: [{ message_id: request.message_id, kind: "current_user_message" }],
		runtime_metadata: {
			runtime_state: "ready",
			model_id: request.runtime_config.model_id,
			provider_profile_id: request.runtime_config.provider_profile_id,
			usage: {},
			duration_ms: Date.now() - startedAt,
			attempt: 0,
		},
		error: null,
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
		const result = await executeDirectorRuntimeRequest(request, createProcessSyntheticStreamFn());
		process.stdout.write(`${JSON.stringify(result)}\n`);
	} catch {
		process.stderr.write("director_runtime_failed\n");
		process.exitCode = 1;
	}
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
