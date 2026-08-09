import { createHash } from "node:crypto";
import { existsSync, lstatSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const runtimeRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const snapshotRoot = join(runtimeRoot, "upstream", "pi");
const manifestPath = join(runtimeRoot, "UPSTREAM_IMPORT_MANIFEST.json");
const expectedPackages = [
  ["packages/telemetry", "@earendil-works/pi-telemetry"],
  ["packages/ai", "@earendil-works/pi-ai"],
  ["packages/agent", "@earendil-works/pi-agent-core"],
];
const forbiddenPaths = [".git", "node_modules", "dist", "coverage", "packages/coding-agent", "packages/tui", "packages/server", "packages/client", "packages/protocol", "packages/session-backends", "packages/evals"];

function fail(message) {
  throw new Error(`upstream verification failed: ${message}`);
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function walk(directory, root = directory, files = []) {
  const stat = lstatSync(directory);
  if (stat.isSymbolicLink() || !stat.isDirectory()) {
    fail(`invalid snapshot directory: ${relative(root, directory) || "."}`);
  }
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
    const entryPath = join(directory, entry.name);
    const entryStat = lstatSync(entryPath);
    if (entryStat.isSymbolicLink()) {
      fail(`snapshot symlink: ${relative(root, entryPath)}`);
    }
    if (entryStat.isDirectory()) {
      walk(entryPath, root, files);
    } else if (entryStat.isFile()) {
      files.push(relative(root, entryPath));
    } else {
      fail(`non-regular snapshot entry: ${relative(root, entryPath)}`);
    }
  }
  return files.sort((left, right) => left.localeCompare(right));
}

if (!existsSync(manifestPath) || !existsSync(snapshotRoot)) {
  fail("manifest or snapshot is missing");
}
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
if (
  manifest.schema_version !== "p26-big-upstream-import/v1" ||
  manifest.canonical_repository !== "https://github.com/earendil-works/pi.git" ||
  manifest.historical_alias !== "https://github.com/badlogic/pi-mono.git" ||
  manifest.repository_id !== 1035029907 ||
  manifest.selected_sha !== "936aff00918de1187f085f123c2812d8f2d67745"
) {
  fail("manifest provenance mismatch");
}
const declaredPackages = manifest.imported_packages.map((item) => [item.source_path, item.name, item.version, item.classification]);
const expectedDeclaredPackages = expectedPackages.map(([sourcePath, name]) => [sourcePath, name, "0.84.1", "vendored pinned source"]);
if (JSON.stringify(declaredPackages) !== JSON.stringify(expectedDeclaredPackages)) {
  fail("imported internal package set mismatch");
}
for (const forbiddenPath of forbiddenPaths) {
  if (existsSync(join(snapshotRoot, forbiddenPath))) {
    fail(`forbidden snapshot path: ${forbiddenPath}`);
  }
}
for (const [sourcePath, expectedName] of expectedPackages) {
  const packageJson = JSON.parse(readFileSync(join(snapshotRoot, sourcePath, "package.json"), "utf8"));
  if (packageJson.name !== expectedName || packageJson.version !== "0.84.1") {
    fail(`package identity mismatch: ${sourcePath}`);
  }
}
const agentPackage = JSON.parse(readFileSync(join(snapshotRoot, "packages/agent/package.json"), "utf8"));
const aiPackage = JSON.parse(readFileSync(join(snapshotRoot, "packages/ai/package.json"), "utf8"));
if (agentPackage.dependencies["@earendil-works/pi-ai"] !== "^0.84.1" || agentPackage.dependencies["@earendil-works/pi-telemetry"] !== "^0.84.1" || aiPackage.dependencies["@earendil-works/pi-telemetry"] !== "^0.84.1") {
  fail("internal dependency closure mismatch");
}
const snapshotFiles = walk(snapshotRoot);
const manifestFiles = manifest.files.map((item) => item.path);
if (JSON.stringify(snapshotFiles) !== JSON.stringify(manifestFiles)) {
  fail("manifest file set mismatch");
}
for (const file of manifest.files) {
  if (file.source_path !== file.path || file.classification !== "upstream-owned snapshot") {
    fail(`manifest classification mismatch: ${file.path}`);
  }
  if (sha256(join(snapshotRoot, file.path)) !== file.sha256) {
    fail(`manifest hash mismatch: ${file.path}`);
  }
}
if (readFileSync(join(snapshotRoot, "LICENSE"), "utf8") !== readFileSync(join(runtimeRoot, "LICENSES/pi-MIT.txt"), "utf8")) {
  fail("MIT license copy mismatch");
}
if (!/No local upstream patches\./.test(readFileSync(join(runtimeRoot, "LOCAL_PATCHES.md"), "utf8"))) {
  fail("LOCAL_PATCHES.md does not declare no upstream patch");
}
console.log(`verified ${manifest.files.length} snapshot files at ${manifest.selected_sha}`);
