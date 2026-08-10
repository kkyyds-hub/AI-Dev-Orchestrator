# Local Patches

No local upstream patches.

The contents of `upstream/pi/` are an upstream-owned snapshot. Project-owned
changes belong outside that directory unless a later approved `fork-patch` is
recorded here with its upstream baseline, affected files, reason, upgrade risk,
and compatibility test.

## Project-owned replacements

`classification = replacement`

`surface = upstream full package build orchestration`

`replacement = selective Director core build`

`upstream baseline = 936aff00918de1187f085f123c2812d8f2d67745`

`reason = root tsgo toolchain excluded; generated provider catalog excluded`

`source modifications = none`

`provider catalog = excluded`

`upgrade risk = the selective core entry graphs must be revalidated when the pinned upstream SHA changes`

`verification command = npm run verify:pi-core-build`

This replacement is project-owned build orchestration. `replacement != fork-patch`;
it neither changes nor adds files to the upstream snapshot.
