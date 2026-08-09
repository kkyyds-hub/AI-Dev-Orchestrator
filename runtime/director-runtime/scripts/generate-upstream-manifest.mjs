import { createHash } from "node:crypto";
import { lstatSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const runtimeRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const snapshotRoot = join(runtimeRoot, "upstream", "pi");
const selectedSha = "936aff00918de1187f085f123c2812d8f2d67745";
const packages = [
  ["packages/telemetry", "@earendil-works/pi-telemetry"],
  ["packages/ai", "@earendil-works/pi-ai"],
  ["packages/agent", "@earendil-works/pi-agent-core"],
];

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function snapshotFiles(directory, root = directory, files = []) {
  const stat = lstatSync(directory);
  if (stat.isSymbolicLink() || !stat.isDirectory()) {
    throw new Error(`invalid snapshot directory: ${relative(root, directory) || "."}`);
  }
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
    const entryPath = join(directory, entry.name);
    const entryStat = lstatSync(entryPath);
    if (entryStat.isSymbolicLink()) {
      throw new Error(`snapshot symlink: ${relative(root, entryPath)}`);
    }
    if (entryStat.isDirectory()) {
      snapshotFiles(entryPath, root, files);
      continue;
    }
    if (!entryStat.isFile()) {
      throw new Error(`non-regular snapshot entry: ${relative(root, entryPath)}`);
    }
    files.push(relative(root, entryPath));
  }
  return files;
}

const packageJsons = new Map(
  packages.map(([sourcePath, expectedName]) => {
    const packageJson = JSON.parse(readFileSync(join(snapshotRoot, sourcePath, "package.json"), "utf8"));
    if (packageJson.name !== expectedName || packageJson.version !== "0.84.1") {
      throw new Error(`unexpected package identity: ${sourcePath}`);
    }
    return [sourcePath, packageJson];
  }),
);
const lock = JSON.parse(readFileSync(join(runtimeRoot, "package-lock.json"), "utf8"));
const dependencyDeclarations = new Map();
for (const [, packageJson] of packageJsons) {
  for (const [name, declaration] of Object.entries(packageJson.dependencies ?? {})) {
    if (name.startsWith("@earendil-works/pi-")) {
      continue;
    }
    const declarations = dependencyDeclarations.get(name) ?? [];
    declarations.push({ package_name: packageJson.name, upstream_declaration: declaration });
    dependencyDeclarations.set(name, declarations);
  }
}
const thirdPartyDependencies = [...dependencyDeclarations.entries()]
  .map(([name, upstream_declarations]) => {
    const resolvedVersion = lock.packages[`node_modules/${name}`]?.version;
    if (typeof resolvedVersion !== "string") {
      throw new Error(`lockfile has no resolved version for ${name}`);
    }
    return { name, upstream_declarations, lock_resolved_version: resolvedVersion };
  })
  .sort((left, right) => left.name.localeCompare(right.name));
const files = snapshotFiles(snapshotRoot)
  .sort((left, right) => left.localeCompare(right))
  .map((path) => ({
    path,
    sha256: sha256(join(snapshotRoot, path)),
    source_path: path,
    classification: "upstream-owned snapshot",
  }));
const retrievedAt = process.env.P26_BIG_UPSTREAM_RETRIEVED_AT ?? new Date().toISOString();
const manifest = {
  schema_version: "p26-big-upstream-import/v1",
  canonical_repository: "https://github.com/earendil-works/pi.git",
  historical_alias: "https://github.com/badlogic/pi-mono.git",
  repository_id: 1035029907,
  selected_sha: selectedSha,
  selected_commit_date: "2026-08-09T02:11:00+02:00",
  selected_commit_subject: "docs(agent): complete explicit-state harness design",
  retrieved_at: retrievedAt,
  stable_release_reference: {
    tag: "v0.84.1",
    sha: "53fa77ccd8a279eb87e92294ef3687b03ff80112",
  },
  imported_paths: ["LICENSE", "tsconfig.base.json", "packages/telemetry", "packages/ai", "packages/agent"],
  imported_packages: packages.map(([source_path]) => {
    const packageJson = packageJsons.get(source_path);
    return { source_path, name: packageJson.name, version: packageJson.version, classification: "vendored pinned source" };
  }),
  internal_dependency_closure: packages.map(([source_path]) => ({
    name: packageJsons.get(source_path).name,
    source_path,
    classification: "vendored pinned source",
  })),
  third_party_dependencies: thirdPartyDependencies,
  files,
};

writeFileSync(join(runtimeRoot, "UPSTREAM_IMPORT_MANIFEST.json"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`wrote ${files.length} snapshot hashes and ${thirdPartyDependencies.length} third-party dependencies`);
