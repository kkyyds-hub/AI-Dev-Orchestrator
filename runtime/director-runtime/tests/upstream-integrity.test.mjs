import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, lstatSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";

const runtimeRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const snapshotRoot = join(runtimeRoot, "upstream", "pi");
const manifestPath = join(runtimeRoot, "UPSTREAM_IMPORT_MANIFEST.json");
const lockPath = join(runtimeRoot, "package-lock.json");
const selectedSha = "936aff00918de1187f085f123c2812d8f2d67745";
const canonicalRepository = "https://github.com/earendil-works/pi.git";
const historicalAlias = "https://github.com/badlogic/pi-mono.git";
const repositoryId = 1035029907;
const expectedPackages = [
  ["packages/telemetry", "@earendil-works/pi-telemetry"],
  ["packages/ai", "@earendil-works/pi-ai"],
  ["packages/agent", "@earendil-works/pi-agent-core"],
];
const forbiddenPaths = [
  ".git",
  "node_modules",
  "dist",
  "coverage",
  "packages/coding-agent",
  "packages/tui",
  "packages/server",
  "packages/client",
  "packages/protocol",
  "packages/session-backends",
  "packages/evals",
];

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function walkSnapshot(directory, root = directory, files = [], directories = []) {
  const stat = lstatSync(directory);
  assert.equal(stat.isSymbolicLink(), false, `snapshot symlink: ${relative(root, directory) || "."}`);
  assert.equal(stat.isDirectory(), true, `snapshot entry is not a directory: ${relative(root, directory) || "."}`);
  directories.push(relative(root, directory) || ".");

  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
    const entryPath = join(directory, entry.name);
    const entryStat = lstatSync(entryPath);
    assert.equal(entryStat.isSymbolicLink(), false, `snapshot symlink: ${relative(root, entryPath)}`);
    if (entryStat.isDirectory()) {
      walkSnapshot(entryPath, root, files, directories);
      continue;
    }
    assert.equal(entryStat.isFile(), true, `snapshot entry is not a regular file: ${relative(root, entryPath)}`);
    files.push(relative(root, entryPath));
  }

  return { directories, files };
}

function readPackage(relativePath) {
  return JSON.parse(readFileSync(join(snapshotRoot, relativePath, "package.json"), "utf8"));
}

function declaredThirdPartyDependencies(packages) {
  const declarations = new Map();
  for (const [sourcePath, expectedName] of expectedPackages) {
    const packageJson = packages.get(sourcePath);
    assert.equal(packageJson.name, expectedName);
    for (const [name, declaration] of Object.entries(packageJson.dependencies ?? {})) {
      if (name.startsWith("@earendil-works/pi-")) {
        continue;
      }
      const values = declarations.get(name) ?? [];
      values.push({ package_name: packageJson.name, upstream_declaration: declaration });
      declarations.set(name, values);
    }
  }
  return [...declarations.entries()]
    .map(([name, upstream_declarations]) => ({ name, upstream_declarations }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

test("the controlled Pi snapshot is complete, pinned, and unpatched", () => {
  assert.equal(existsSync(manifestPath), true, "missing authoritative import manifest");
  assert.equal(existsSync(snapshotRoot), true, "missing upstream snapshot");
  assert.equal(existsSync(lockPath), true, "missing Director Runtime lockfile");

  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  assert.equal(manifest.schema_version, "p26-big-upstream-import/v1");
  assert.equal(manifest.canonical_repository, canonicalRepository);
  assert.equal(manifest.historical_alias, historicalAlias);
  assert.equal(manifest.repository_id, repositoryId);
  assert.equal(manifest.selected_sha, selectedSha);
  assert.equal(manifest.stable_release_reference.tag, "v0.84.1");
  assert.equal(manifest.stable_release_reference.sha, "53fa77ccd8a279eb87e92294ef3687b03ff80112");

  assert.deepEqual(
    manifest.imported_packages.map((item) => [item.source_path, item.name, item.version, item.classification]),
    expectedPackages.map(([sourcePath, name]) => [sourcePath, name, "0.84.1", "vendored pinned source"]),
  );
  assert.deepEqual(
    manifest.internal_dependency_closure,
    [
      { name: "@earendil-works/pi-telemetry", source_path: "packages/telemetry", classification: "vendored pinned source" },
      { name: "@earendil-works/pi-ai", source_path: "packages/ai", classification: "vendored pinned source" },
      { name: "@earendil-works/pi-agent-core", source_path: "packages/agent", classification: "vendored pinned source" },
    ],
  );

  for (const forbiddenPath of forbiddenPaths) {
    assert.equal(existsSync(join(snapshotRoot, forbiddenPath)), false, `forbidden snapshot path: ${forbiddenPath}`);
  }

  const packageJsons = new Map(expectedPackages.map(([sourcePath]) => [sourcePath, readPackage(sourcePath)]));
  for (const [sourcePath, expectedName] of expectedPackages) {
    const packageJson = packageJsons.get(sourcePath);
    assert.equal(packageJson.name, expectedName);
    assert.equal(packageJson.version, "0.84.1");
  }
  assert.equal(packageJsons.get("packages/agent").dependencies["@earendil-works/pi-ai"], "^0.84.1");
  assert.equal(packageJsons.get("packages/agent").dependencies["@earendil-works/pi-telemetry"], "^0.84.1");
  assert.equal(packageJsons.get("packages/ai").dependencies["@earendil-works/pi-telemetry"], "^0.84.1");

  const { files } = walkSnapshot(snapshotRoot);
  const manifestFiles = manifest.files.map((item) => item.path);
  assert.deepEqual(manifestFiles, [...manifestFiles].sort((left, right) => left.localeCompare(right)), "manifest paths are not stable");
  assert.deepEqual(files.sort((left, right) => left.localeCompare(right)), manifestFiles, "snapshot and manifest file sets differ");
  for (const file of manifest.files) {
    assert.equal(file.source_path, file.path);
    assert.equal(file.classification, "upstream-owned snapshot");
    assert.equal(sha256(join(snapshotRoot, file.path)), file.sha256, `hash mismatch: ${file.path}`);
  }

  assert.equal(
    readFileSync(join(snapshotRoot, "LICENSE"), "utf8"),
    readFileSync(join(runtimeRoot, "LICENSES", "pi-MIT.txt"), "utf8"),
    "snapshot and copied MIT licenses differ",
  );
  assert.match(readFileSync(join(runtimeRoot, "LOCAL_PATCHES.md"), "utf8"), /No local upstream patches\./);

  const lock = JSON.parse(readFileSync(lockPath, "utf8"));
  const expectedThirdParty = declaredThirdPartyDependencies(packageJsons);
  assert.deepEqual(
    manifest.third_party_dependencies.map(({ name, upstream_declarations }) => ({ name, upstream_declarations })),
    expectedThirdParty,
  );
  for (const dependency of manifest.third_party_dependencies) {
    assert.equal(typeof dependency.lock_resolved_version, "string");
    assert.equal(lock.packages[`node_modules/${dependency.name}`].version, dependency.lock_resolved_version);
  }
});

test("the standalone verifier accepts the snapshot", () => {
  const result = spawnSync(process.execPath, [join(runtimeRoot, "scripts", "verify-upstream.mjs")], {
    cwd: runtimeRoot,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});
