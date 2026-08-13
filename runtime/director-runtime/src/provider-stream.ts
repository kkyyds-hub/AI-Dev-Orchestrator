import type { StreamFn } from "@earendil-works/pi-agent-core";
import type {
	AssistantMessageEventStream,
	Context,
	Model,
	SimpleStreamOptions,
} from "@earendil-works/pi-ai";

import type { DirectorRuntimeRequest } from "./protocol.js";

const ENV_PROVIDER_MODE = "DIRECTOR_RUNTIME_PROVIDER_MODE";
const ENV_PROVIDER_BASE_URL = "DIRECTOR_RUNTIME_PROVIDER_BASE_URL";
const ENV_PROVIDER_API_KEY = "DIRECTOR_RUNTIME_PROVIDER_API_KEY";
const ENV_PROVIDER_PROFILE_ID = "DIRECTOR_RUNTIME_PROVIDER_PROFILE_ID";

export const OPENAI_COMPATIBLE_MODE = "openai_compatible" as const;

type OpenAICompletionsStreamSimple = (
	model: Model<"openai-completions">,
	context: Context,
	options?: SimpleStreamOptions,
) => AssistantMessageEventStream;

/**
 * The vendored Pi AI OpenAI-completions adapter. It is reached through a
 * computed-specifier dynamic import because the runtime TypeScript paths map
 * only the bare `@earendil-works/pi-ai` entry point; the compiled adapter is
 * resolved at runtime from the prepared `dist/node_modules` core build.
 */
const OPENAI_COMPLETIONS_SUBPATH = "@earendil-works/pi-ai/api/openai-completions";

let cachedStreamSimple: OpenAICompletionsStreamSimple | undefined;

async function loadOpenAICompletionsStreamSimple(): Promise<OpenAICompletionsStreamSimple> {
	if (!cachedStreamSimple) {
		const mod = (await import(OPENAI_COMPLETIONS_SUBPATH)) as {
			streamSimple: OpenAICompletionsStreamSimple;
		};
		cachedStreamSimple = mod.streamSimple;
	}
	return cachedStreamSimple;
}

function readEnv(name: string): string | undefined {
	const value = process.env[name];
	return value && value.length > 0 ? value : undefined;
}

export interface OpenAICompatibleRuntime {
	model: Model<"openai-completions">;
	streamFn: StreamFn;
}

/**
 * Build the provider-backed runtime for one request, failing closed before any
 * provider call when the injected profile does not correlate with the request,
 * or when the required credential/base URL are absent.
 */
export function createOpenAICompatibleRuntime(request: DirectorRuntimeRequest): OpenAICompatibleRuntime {
	const injectedProfileId = readEnv(ENV_PROVIDER_PROFILE_ID);
	if (request.runtime_config.provider_profile_id !== injectedProfileId) {
		throw new Error("director_runtime_provider_profile_mismatch");
	}

	const baseUrl = readEnv(ENV_PROVIDER_BASE_URL);
	if (!baseUrl) {
		throw new Error("director_runtime_provider_base_url_missing");
	}

	const apiKey = readEnv(ENV_PROVIDER_API_KEY);
	if (!apiKey) {
		throw new Error("director_runtime_provider_api_key_missing");
	}

	return {
		model: createOpenAICompatibleModel(request, baseUrl),
		streamFn: createOpenAICompatibleStreamFn(apiKey),
	};
}

function createOpenAICompatibleModel(
	request: DirectorRuntimeRequest,
	baseUrl: string,
): Model<"openai-completions"> {
	return {
		id: request.runtime_config.model_id,
		name: request.runtime_config.model_id,
		api: "openai-completions",
		provider: "director-openai-compatible",
		baseUrl,
		reasoning: false,
		input: ["text"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 128000,
		maxTokens: 4096,
	};
}

function createOpenAICompatibleStreamFn(apiKey: string): StreamFn {
	return async (model, context, options) => {
		const streamSimple = await loadOpenAICompletionsStreamSimple();
		return streamSimple(model as Model<"openai-completions">, context, {
			...options,
			apiKey,
		});
	};
}

export { ENV_PROVIDER_MODE };
