## Problem And Scope

Describe the problem, intended audience, and explicit out-of-scope areas.

## Implementation Summary

Explain the change and the existing architecture it extends.

## Security Impact

- Trust boundaries affected:
- Shell, filesystem, Git, provider, credential, review, approval, or evidence impact:
- New failure or abuse cases:
- Mitigations and negative tests:

Use `None` only with a short explanation.

## Tests And Evidence

List exact commands, results, warnings, smoke modes, and manual checks. Distinguish
focused evidence from the complete repository baseline.

```text
command
result
```

## Documentation

- [ ] Public behavior, setup, configuration, and limitations are documented.
- [ ] English and Chinese README claims remain aligned, if affected.
- [ ] Experimental, partial, planned, or blocked behavior is labeled honestly.
- [ ] Threat model or security policy changes are included, if required.

## Compatibility Impact

Describe API, schema, persisted data, dependency, provider, executor, UI, and
existing-workflow compatibility. State `No compatibility change` only when
verified.

## Rollback

Describe how to disable or revert this change and what state or data remains.

## Checklist

- [ ] The diff is focused and contains no unrelated generated or local files.
- [ ] No secret, token, password, private URL, personal data, or credential was added.
- [ ] Commands and links added by this change were verified.
- [ ] Unsupported adoption, security, performance, or completion claims were not added.
- [ ] Known failures and remaining maintainer decisions are disclosed.
