# Dependency Security Review

**Date:** 2026-07-11
**Commit:** `36a1855d3bc3d595468db32b79e6e34b6d4f12e8`
**Branch:** `chore/oss-readiness`
**Node.js:** v22.22.1
**npm:** 10.9.4
**Python:** 3.12.13

## Scope

This is a point-in-time snapshot of `npm audit` output against the committed
`apps/web/package-lock.json`. It documents known advisories; it does not fix
them. Dependency remediation requires a separate compatibility-reviewed change.

## All Dependencies (8 total)

| Severity | Count |
| --- | --- |
| Low | 1 |
| Moderate | 2 |
| High | 5 |
| Critical | 0 |

## Production Dependencies Only (3 total)

| Severity | Count |
| --- | --- |
| High | 3 |
| Critical | 0 |

## Production High-Severity Advisories

### 1. @remix-run/router — XSS via Open Redirects

- **Package:** `@remix-run/router` (transitive: `react-router`, `react-router-dom`)
- **Severity:** High
- **Advisory:** [GHSA-2w69-qvjg-hvjx](https://github.com/advisories/GHSA-2w69-qvjg-hvjx)
- **Path:** `react-router-dom` → `react-router` → `@remix-run/router`
- **Classification:** Application-layer XSS in the routing library. Exploitable
  if an attacker can control a redirect target passed to the router. In this
  project, the web control surface runs locally and is not exposed to the public
  internet by default. Risk increases if the frontend is ever served remotely
  without additional sanitization.
- **Fix:** Upgrade `react-router-dom` to a version that resolves the
  transitive dependency. The current lockfile pins `@remix-run/router` at
  `<=1.23.1`.

### 2. picomatch — Method Injection in POSIX Character Classes

- **Package:** `picomatch`
- **Severity:** High
- **Advisories:**
  [GHSA-3v7f-55p6-f55p](https://github.com/advisories/GHSA-3v7f-55p6-f55p),
  [GHSA-c2c7-rcm5-vvqj](https://github.com/advisories/GHSA-c2c7-rcm5-vvqj)
- **Path:** Direct dependency and via `tinyglobby`
- **Classification:** Glob-matching library with method injection and ReDoS
  vulnerabilities. Affects file-glob operations in the build/dev toolchain. In
  this project `picomatch` is used through build tooling; the ReDoS vector
  requires crafted glob patterns. Risk is primarily in development and build
  contexts, not in the runtime application serving user input.
- **Fix:** Upgrade `picomatch` to `>=2.3.2` or `>=4.0.4`. Some paths require
  upstream tool updates.

### 3. picomatch — ReDoS via extglob quantifiers

- Same package and path as above. Listed as a separate advisory but resolved by
  the same upgrade.

## Dev-Only Advisories (not in production view)

| Package | Severity | Advisory |
| --- | --- | --- |
| `@babel/core` | Low | [GHSA-4x5r-pxfx-6jf8](https://github.com/advisories/GHSA-4x5r-pxfx-6jf8) — arbitrary file read via sourceMappingURL |
| `esbuild` | Moderate | [GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99) — dev server request forgery |
| `vite` | Moderate | Depends on vulnerable `esbuild` |
| `postcss` | Low | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93) — XSS via unescaped `</style>` |

## Notes

- This is a snapshot only. No dependency versions were changed in this branch.
- `npm audit fix` may resolve some findings without breaking changes; `npm audit
  fix --force` may introduce breaking changes (e.g., Vite 8.x).
- The backend (`runtime/orchestrator`) uses bounded Python dependency ranges
  without a committed lockfile. Python dependency auditing is not covered here.
- This repository does not currently have committed CI dependency scanning, SBOM
  generation, or provenance verification.
