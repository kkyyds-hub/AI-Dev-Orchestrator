import { cp, lstat, mkdir, mkdtemp, readFile, readdir, readlink, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const runtimeRoot = path.resolve(import.meta.dirname, "..");
const upstreamRoot = path.join(runtimeRoot, "upstream", "pi");
const controlledTsc = path.join(runtimeRoot, "node_modules", ".bin", "tsc");
const stagingRoot = await mkdtemp(path.join(tmpdir(), "director-pi-core-build-"));
const stagingPackagesRoot = path.join(stagingRoot, "packages");
const stagingNodeModules = path.join(stagingRoot, "node_modules");
const piPackages = [
	{ directory: "telemetry", name: "@earendil-works/pi-telemetry", nodeNext: false },
	{ directory: "ai", name: "@earendil-works/pi-ai", nodeNext: true },
	{ directory: "agent", name: "@earendil-works/pi-agent-core", nodeNext: false },
];
const buildOnlyDependencyNames = ["typescript", "@types/node"];

function run(command, args, cwd) {
	const result = spawnSync(command, args, { cwd, encoding: "utf8", stdio: "pipe" });
	if (result.status !== 0) {
		throw new Error([`${command} ${args.join(" ")}`, result.stdout, result.stderr].filter(Boolean).join("\n"));
	}
	return `${result.stdout}${result.stderr}`;
}

async function readJson(filePath) {
	return JSON.parse(await readFile(filePath, "utf8"));
}

async function assertExists(relativePath) {
	await lstat(path.join(upstreamRoot, relativePath));
}

function packageNameFromLockPath(lockPath) {
	const segments = lockPath.split("/");
	const nodeModulesIndex = segments.lastIndexOf("node_modules");
	if (nodeModulesIndex < 0 || nodeModulesIndex === segments.length - 1) {
		throw new Error(`invalid lock package path: ${lockPath}`);
	}
	return segments[nodeModulesIndex + 1].startsWith("@")
		? `${segments[nodeModulesIndex + 1]}/${segments[nodeModulesIndex + 2]}`
		: segments[nodeModulesIndex + 1];
}

async function copyLockedThirdPartyPackages(lock) {
	const copiedLockPaths = [];
	const lockPaths = Object.keys(lock.packages)
		.filter((lockPath) => lockPath.startsWith("node_modules/") && !lockPath.startsWith("node_modules/@earendil-works/"))
		.sort((left, right) => left.split("/").length - right.split("/").length || left.localeCompare(right));

	for (const lockPath of lockPaths) {
		const lockEntry = lock.packages[lockPath];
		if (typeof lockEntry?.version !== "string") {
			throw new Error(`lock entry has no version: ${lockPath}`);
		}

		const source = path.join(runtimeRoot, lockPath);
		let sourceStat;
		try {
			sourceStat = await lstat(source);
		} catch (error) {
			if (error?.code === "ENOENT" && lockEntry.optional === true) continue;
			throw error;
		}
		if (!sourceStat.isDirectory() || sourceStat.isSymbolicLink()) {
			throw new Error(`locked package is not a real directory: ${lockPath}`);
		}

		const installedManifest = await readJson(path.join(source, "package.json"));
		if (installedManifest.name !== packageNameFromLockPath(lockPath) || installedManifest.version !== lockEntry.version) {
			throw new Error(`installed package does not match lock entry: ${lockPath}`);
		}

		await cp(source, path.join(stagingRoot, lockPath), {
			recursive: true,
			filter: (sourcePath) => path.basename(sourcePath) !== "node_modules",
		});
		copiedLockPaths.push(lockPath);
	}

	return copiedLockPaths;
}

function selectiveTsConfig({ nodeNext }) {
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

async function copyPiPackageSources(piPackage) {
	const sourceRoot = path.join(upstreamRoot, "packages", piPackage.directory);
	const destinationRoot = path.join(stagingPackagesRoot, piPackage.directory);
	await mkdir(destinationRoot, { recursive: true });
	await cp(path.join(sourceRoot, "package.json"), path.join(destinationRoot, "package.json"));
	await cp(path.join(sourceRoot, "src"), path.join(destinationRoot, "src"), { recursive: true });
	await writeFile(path.join(destinationRoot, "tsconfig.selective.json"), selectiveTsConfig(piPackage));
	return destinationRoot;
}

async function linkPiPackage(piPackage, target) {
	const linkPath = path.join(stagingNodeModules, piPackage.name);
	await mkdir(path.dirname(linkPath), { recursive: true });
	await symlink(target, linkPath, "junction");
}

async function assertStagingSymlinksStayInternal(directory) {
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const entryPath = path.join(directory, entry.name);
		const stat = await lstat(entryPath);
		if (stat.isSymbolicLink()) {
			const target = path.resolve(path.dirname(entryPath), await readlink(entryPath));
			if (!target.startsWith(`${stagingRoot}${path.sep}`)) {
				throw new Error(`staging symlink escapes closure: ${entryPath}`);
			}
			continue;
		}
		if (stat.isDirectory()) await assertStagingSymlinksStayInternal(entryPath);
	}
}

async function assertEmitted(relativePath) {
	await lstat(path.join(stagingRoot, relativePath));
}

try {
	for (const piPackage of piPackages) {
		for (const required of [`packages/${piPackage.directory}/package.json`, `packages/${piPackage.directory}/src/index.ts`]) {
			await assertExists(required);
		}
	}
	await assertExists("tsconfig.base.json");
	await lstat(controlledTsc);

	const lock = await readJson(path.join(runtimeRoot, "package-lock.json"));
	if (lock.lockfileVersion !== 3 || typeof lock.packages !== "object" || lock.packages === null) {
		throw new Error("unsupported package-lock format");
	}
	const directDependencies = new Map();
	const buildOnlyDependencies = new Map();
	for (const piPackage of piPackages) {
		const manifest = await readJson(path.join(upstreamRoot, "packages", piPackage.directory, "package.json"));
		if (manifest.name !== piPackage.name) throw new Error(`unexpected Pi package identity: ${piPackage.directory}`);
		for (const [name, version] of Object.entries(manifest.dependencies ?? {})) {
			if (!name.startsWith("@earendil-works/pi-")) directDependencies.set(name, version);
		}
		for (const name of buildOnlyDependencyNames) {
			const version = manifest.devDependencies?.[name];
			if (typeof version !== "string") continue;
			const previous = buildOnlyDependencies.get(name);
			if (previous !== undefined && previous !== version) {
				throw new Error(`selected Pi packages disagree on build dependency version: ${name}`);
			}
			buildOnlyDependencies.set(name, version);
		}
	}
	for (const name of buildOnlyDependencyNames) {
		const expectedVersion = buildOnlyDependencies.get(name);
		if (typeof expectedVersion !== "string" || lock.packages[`node_modules/${name}`]?.version !== expectedVersion) {
			throw new Error(`build dependency is not locked at the selected Pi version: ${name}`);
		}
	}
	const typescriptVersion = buildOnlyDependencies.get("typescript");
	if (!run(controlledTsc, ["--version"], runtimeRoot).includes(`Version ${typescriptVersion}`)) {
		throw new Error("controlled tsc version does not match the lockfile");
	}
	for (const [name, expectedVersion] of directDependencies) {
		if (lock.packages[`node_modules/${name}`]?.version !== expectedVersion) {
			throw new Error(`selected direct dependency is not locked at the upstream version: ${name}`);
		}
	}

	const copiedLockPaths = await copyLockedThirdPartyPackages(lock);
	await mkdir(stagingPackagesRoot, { recursive: true });
	await cp(path.join(upstreamRoot, "tsconfig.base.json"), path.join(stagingRoot, "tsconfig.base.json"));
	const stagedPiRoots = new Map();
	for (const piPackage of piPackages) {
		const target = await copyPiPackageSources(piPackage);
		stagedPiRoots.set(piPackage.name, target);
		await linkPiPackage(piPackage, target);
	}
	await assertStagingSymlinksStayInternal(stagingNodeModules);

	const stagedTsc = path.join(stagingNodeModules, "typescript", "bin", "tsc");
	if (!run(stagedTsc, ["--version"], stagingRoot).includes(`Version ${typescriptVersion}`)) {
		throw new Error("staged tsc version does not match the lockfile");
	}
	run(stagedTsc, ["-p", "tsconfig.selective.json"], stagedPiRoots.get("@earendil-works/pi-telemetry"));
	console.log("telemetry selective build = PASS");
	run(stagedTsc, ["-p", "tsconfig.selective.json"], stagedPiRoots.get("@earendil-works/pi-ai"));
	console.log("ai-core selective build = PASS");
	run(stagedTsc, ["-p", "tsconfig.selective.json"], stagedPiRoots.get("@earendil-works/pi-agent-core"));
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
	const probeOutput = run(process.execPath, [probePath], stagingRoot).trim();
	if (probeOutput !== '{"streamFnCalls":0}') throw new Error(`unexpected probe output: ${probeOutput}`);
	console.log("compiled Agent ESM import = PASS");
	console.log("Agent construction = PASS");
	console.log("StreamFn calls = 0");
	console.log(`selected direct dependencies = ${directDependencies.size}`);
	console.log(`locked third-party package paths copied = ${copiedLockPaths.length}`);
	console.log(`TypeScript lock version = ${typescriptVersion}`);
	console.log("provider catalog = excluded");
	console.log("generate-models invoked = NO");
	console.log("network = 0");
} finally {
	await rm(stagingRoot, { recursive: true, force: true });
}
