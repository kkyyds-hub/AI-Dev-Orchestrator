import assert from "node:assert/strict";
import { existsSync, lstatSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const runtimeRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const upstreamRoot = join(runtimeRoot, "upstream", "pi");
const lockPath = join(runtimeRoot, "package-lock.json");
const selectedPackages = [
	["telemetry", "@earendil-works/pi-telemetry"],
	["ai", "@earendil-works/pi-ai"],
	["agent", "@earendil-works/pi-agent-core"],
];
const buildDependencies = new Map([
	["typescript", "5.9.3"],
	["@types/node", "24.12.4"],
]);

function selectedDependencies() {
	const dependencies = new Map();
	const selectedBuildDependencies = new Map();
	for (const [directory, expectedName] of selectedPackages) {
		const manifest = JSON.parse(readFileSync(join(upstreamRoot, "packages", directory, "package.json"), "utf8"));
		assert.equal(manifest.name, expectedName);
		for (const [name, version] of Object.entries(manifest.dependencies ?? {})) {
			if (!name.startsWith("@earendil-works/pi-")) dependencies.set(name, version);
		}
		for (const name of buildDependencies.keys()) {
			if (manifest.devDependencies?.[name]) selectedBuildDependencies.set(name, manifest.devDependencies[name]);
		}
	}
	assert.deepEqual(selectedBuildDependencies, buildDependencies);
	return dependencies;
}

test("locked Pi core build closure remains reproducible and externally staged", () => {
	const beforeStaging = new Set(
		readdirSync(tmpdir(), { withFileTypes: true })
			.filter((entry) => entry.isDirectory() && entry.name.startsWith("director-pi-core-build-"))
			.map((entry) => entry.name),
	);
	const lock = JSON.parse(readFileSync(lockPath, "utf8"));
	assert.equal(lock.lockfileVersion, 3);

	const dependencies = selectedDependencies();
	assert.equal(dependencies.size, 13);
	for (const [name, version] of dependencies) {
		assert.equal(lock.packages[`node_modules/${name}`]?.version, version, `${name} lock parity`);
	}
	for (const [name, version] of buildDependencies) {
		assert.equal(lock.packages[`node_modules/${name}`]?.version, version, `${name} build lock parity`);
		assert.equal(JSON.parse(readFileSync(join(runtimeRoot, "node_modules", name, "package.json"), "utf8")).version, version);
	}

	const result = spawnSync(process.execPath, [join(runtimeRoot, "scripts", "verify-pi-core-build.mjs")], {
		cwd: runtimeRoot,
		encoding: "utf8",
	});
	assert.equal(result.status, 0, result.stderr || result.stdout);
	assert.match(result.stdout, /compiled Agent ESM import = PASS/);
	assert.match(result.stdout, /Agent construction = PASS/);
	assert.match(result.stdout, /StreamFn calls = 0/);
	assert.match(result.stdout, /provider catalog = excluded/);
	assert.match(result.stdout, /network = 0/);

	const afterStaging = readdirSync(tmpdir(), { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && entry.name.startsWith("director-pi-core-build-"))
		.map((entry) => entry.name);
	assert.deepEqual(afterStaging, [...beforeStaging].sort(), "selective-build staging was not cleaned up");
	assert.equal(existsSync(join(upstreamRoot, "packages", "agent", "dist")), false);
	assert.equal(lstatSync(join(upstreamRoot, "packages", "agent", "src", "index.ts")).isFile(), true);
});
