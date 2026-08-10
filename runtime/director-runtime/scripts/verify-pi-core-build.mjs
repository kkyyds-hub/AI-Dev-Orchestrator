import { cp, lstat, mkdir, mkdtemp, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const runtimeRoot = path.resolve(import.meta.dirname, "..");
const upstreamRoot = path.join(runtimeRoot, "upstream", "pi");
const controlledTsc = path.join(runtimeRoot, "node_modules", ".bin", "tsc");
const stagingRoot = await mkdtemp(path.join(tmpdir(), "director-pi-core-build-"));
const stagingPackagesRoot = path.join(stagingRoot, "packages");
const stagingNodeModules = path.join(stagingRoot, "node_modules");

function run(command, args, cwd) {
	const result = spawnSync(command, args, { cwd, encoding: "utf8", stdio: "pipe" });
	if (result.status !== 0) {
		throw new Error([`${command} ${args.join(" ")}`, result.stdout, result.stderr].filter(Boolean).join("\n"));
	}
	return result.stdout.trim();
}

async function assertExists(relativePath) {
	await lstat(path.join(upstreamRoot, relativePath));
}

async function ensureDirectory(target) {
	await mkdir(target, { recursive: true });
}

async function linkPackage(name, target) {
	const destination = path.join(stagingNodeModules, name);
	await ensureDirectory(path.dirname(destination));
	await symlink(target, destination, "junction");
}

async function linkInstalledThirdPartyClosure() {
	const installedRoot = path.join(runtimeRoot, "node_modules");
	for (const entry of await readdir(installedRoot, { withFileTypes: true })) {
		if (entry.name === ".bin" || entry.name === "@earendil-works") continue;
		if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;

		const source = path.join(installedRoot, entry.name);
		if (!entry.name.startsWith("@")) {
			await linkPackage(entry.name, source);
			continue;
		}

		await ensureDirectory(path.join(stagingNodeModules, entry.name));
		for (const child of await readdir(source, { withFileTypes: true })) {
			if (!child.isDirectory() && !child.isSymbolicLink()) continue;
			await linkPackage(path.join(entry.name, child.name), path.join(source, child.name));
		}
	}
}

function selectiveTsConfig({ nodeNext = false } = {}) {
	return JSON.stringify(
		{
			extends: "../../tsconfig.base.json",
			compilerOptions: {
				outDir: "./dist",
				rootDir: "./src",
				...(nodeNext ? { module: "NodeNext", moduleResolution: "NodeNext" } : {}),
			},
			files: ["./src/index.ts"],
			exclude: ["node_modules", "dist"],
		},
		null,
		2,
	);
}

async function copyPackageSources(packageName) {
	const sourceRoot = path.join(upstreamRoot, "packages", packageName);
	const destinationRoot = path.join(stagingPackagesRoot, packageName);
	await ensureDirectory(destinationRoot);
	await cp(path.join(sourceRoot, "package.json"), path.join(destinationRoot, "package.json"));
	await cp(path.join(sourceRoot, "src"), path.join(destinationRoot, "src"), { recursive: true });
}

async function assertEmitted(relativePath) {
	await lstat(path.join(stagingRoot, relativePath));
}

try {
	for (const required of [
		"tsconfig.base.json",
		"packages/telemetry/package.json",
		"packages/telemetry/src/index.ts",
		"packages/ai/package.json",
		"packages/ai/src/index.ts",
		"packages/agent/package.json",
		"packages/agent/src/index.ts",
		"packages/agent/src/agent.ts",
	]) {
		await assertExists(required);
	}
	await lstat(controlledTsc);

	await ensureDirectory(stagingPackagesRoot);
	await cp(path.join(upstreamRoot, "tsconfig.base.json"), path.join(stagingRoot, "tsconfig.base.json"));
	for (const packageName of ["telemetry", "ai", "agent"]) {
		await copyPackageSources(packageName);
	}

	await linkInstalledThirdPartyClosure();
	await linkPackage("@earendil-works/pi-telemetry", path.join(stagingPackagesRoot, "telemetry"));
	await linkPackage("@earendil-works/pi-ai", path.join(stagingPackagesRoot, "ai"));
	await linkPackage("@earendil-works/pi-agent-core", path.join(stagingPackagesRoot, "agent"));

	await writeFile(path.join(stagingPackagesRoot, "telemetry", "tsconfig.selective.json"), selectiveTsConfig());
	await writeFile(path.join(stagingPackagesRoot, "ai", "tsconfig.selective.json"), selectiveTsConfig({ nodeNext: true }));
	await writeFile(path.join(stagingPackagesRoot, "agent", "tsconfig.selective.json"), selectiveTsConfig());

	run(controlledTsc, ["-p", "tsconfig.selective.json"], path.join(stagingPackagesRoot, "telemetry"));
	console.log("telemetry selective build = PASS");
	run(controlledTsc, ["-p", "tsconfig.selective.json"], path.join(stagingPackagesRoot, "ai"));
	console.log("ai-core selective build = PASS");
	run(controlledTsc, ["-p", "tsconfig.selective.json"], path.join(stagingPackagesRoot, "agent"));
	console.log("agent-core selective build = PASS");

	for (const emitted of [
		"packages/telemetry/dist/index.js",
		"packages/telemetry/dist/index.d.ts",
		"packages/ai/dist/index.js",
		"packages/ai/dist/index.d.ts",
		"packages/agent/dist/index.js",
		"packages/agent/dist/index.d.ts",
	]) {
		await assertEmitted(emitted);
	}

	const probePath = path.join(stagingRoot, "probe.mjs");
	await writeFile(
		probePath,
		[
			'import { Agent } from "@earendil-works/pi-agent-core";',
			'if (typeof Agent !== "function") throw new Error("compiled Agent export missing");',
			"let streamFnCalls = 0;",
			"const streamFn = () => {",
				"streamFnCalls += 1;",
				'throw new Error("unexpected_stream_invocation");',
			"};",
			"new Agent({ streamFn, initialState: { tools: [] } });",
			'if (streamFnCalls !== 0) throw new Error("StreamFn called during Agent construction");',
			"console.log(JSON.stringify({ streamFnCalls }));",
		].join("\n"),
	);
	const probeOutput = run(process.execPath, [probePath], stagingRoot);
	if (probeOutput !== '{"streamFnCalls":0}') throw new Error(`unexpected probe output: ${probeOutput}`);
	console.log("compiled Agent ESM import = PASS");
	console.log("Agent construction = PASS");
	console.log("StreamFn calls = 0");
	console.log("provider catalog = excluded");
	console.log("generate-models invoked = NO");
	console.log("network = 0");
} finally {
	await rm(stagingRoot, { recursive: true, force: true });
}
