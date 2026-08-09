import {
	DirectorRuntimeContractError,
	validateDirectorRuntimeRequest,
	validateResultForRequest,
} from "./protocol.js";

async function main(): Promise<void> {
	const input = await readStandardInput();
	let parsed: unknown;
	try {
		parsed = JSON.parse(input);
	} catch {
		write({ ok: false, code: "probe_input_invalid_json" });
		process.exitCode = 1;
		return;
	}

	try {
		if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
			throw new DirectorRuntimeContractError("probe_input_invalid", "Probe input must be an object.");
		}
		const envelope = parsed as { request?: unknown; result?: unknown };
		const request = validateDirectorRuntimeRequest(envelope.request);
		if (envelope.result !== undefined) validateResultForRequest(request, envelope.result);
		write({ ok: true });
	} catch (error) {
		const code = error instanceof DirectorRuntimeContractError ? error.code : "probe_validation_failed";
		write({ ok: false, code });
		process.exitCode = 1;
	}
}

function readStandardInput(): Promise<string> {
	return new Promise((resolve, reject) => {
		let input = "";
		process.stdin.setEncoding("utf8");
		process.stdin.on("data", (chunk: string) => {
			input += chunk;
		});
		process.stdin.on("end", () => resolve(input));
		process.stdin.on("error", reject);
	});
}

function write(value: object): void {
	process.stdout.write(`${JSON.stringify(value)}\n`);
}

void main();
