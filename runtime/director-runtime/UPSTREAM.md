# Pi Upstream Snapshot

## Provenance

| Field | Value |
| --- | --- |
| Canonical repository | `https://github.com/earendil-works/pi.git` |
| Historical alias | `https://github.com/badlogic/pi-mono.git` |
| GitHub repository ID | `1035029907` |
| Selected immutable SHA | `936aff00918de1187f085f123c2812d8f2d67745` |
| Selected commit date | `2026-08-09T02:11:00+02:00` |
| Selected commit subject | `docs(agent): complete explicit-state harness design` |
| Stable release reference | `v0.84.1` at `53fa77ccd8a279eb87e92294ef3687b03ff80112` |
| Retrieval date | `2026-08-09T15:54:31.957Z` |
| License | MIT, `Copyright (c) 2025 Mario Zechner` |

The historical alias permanently redirects to the canonical repository. Upstream
`main` moving forward does not update this snapshot. Only a new Director Gate
may select a different immutable SHA.

## Imported Snapshot

The snapshot imports these exact upstream paths, without source changes:

```text
LICENSE
tsconfig.base.json
packages/telemetry
packages/ai
packages/agent
```

The included package versions are `@earendil-works/pi-telemetry` `0.84.1`,
`@earendil-works/pi-ai` `0.84.1`, and `@earendil-works/pi-agent-core`
`0.84.1`. The internal closure is `agent -> ai -> telemetry`, plus
`agent -> telemetry`. All three are `vendored pinned source` at the selected
SHA.

The snapshot intentionally excludes coding-agent, tui, protocol, client,
server, session-backends, evals, unrelated examples, release artifacts, Git
metadata, `node_modules`, `dist`, and coverage data.

## Dependency Policy

The import manifest derives third-party direct dependencies from the three
selected package manifests and records both each upstream declaration and the
resolved version in this runtime's `package-lock.json`. A source range such as
`^0.84.1` does not make this snapshot floating.

Technical dependency does not grant governance authority. Provider credential
policy, provider allowlists, model selection, usage/accounting, retry/fallback,
and authoritative-state decisions remain owned by the AI-Dev-Orchestrator
Governance Kernel. This snapshot does not read credentials or call a provider.

## Reproduction

Run from the repository root, with an empty temporary directory outside the
repository:

```bash
TMP_PI="$(mktemp -d)"
git clone --filter=blob:none --no-checkout https://github.com/earendil-works/pi.git "$TMP_PI"
git -C "$TMP_PI" fetch origin 936aff00918de1187f085f123c2812d8f2d67745
git -C "$TMP_PI" checkout --detach 936aff00918de1187f085f123c2812d8f2d67745
git -C "$TMP_PI" archive 936aff00918de1187f085f123c2812d8f2d67745 LICENSE tsconfig.base.json packages/telemetry packages/ai packages/agent | tar -x -C runtime/director-runtime/upstream/pi
cp runtime/director-runtime/upstream/pi/LICENSE runtime/director-runtime/LICENSES/pi-MIT.txt
(cd runtime/director-runtime && npm install --package-lock-only --ignore-scripts)
(cd runtime/director-runtime && node scripts/generate-upstream-manifest.mjs)
(cd runtime/director-runtime && npm run verify:upstream && npm test)
```

The source extraction is path-limited and contains no `.git` metadata. The
authoritative manifest is `UPSTREAM_IMPORT_MANIFEST.json`; it hashes every
regular snapshot file in stable lexicographic path order. The verifier fails on
a missing declared file, an undeclared snapshot file, hash mismatch, or any
symlink.

## Upgrade Procedure

Do not use `main`, `latest`, or a semver range as vendor provenance. A future
Director Gate must freeze a new SHA, re-audit the internal closure, rerun the
path-limited archive, regenerate the independent lockfile and manifest, compare
all hashes, run the integrity checks, and record any approved upstream patch in
`LOCAL_PATCHES.md`.
