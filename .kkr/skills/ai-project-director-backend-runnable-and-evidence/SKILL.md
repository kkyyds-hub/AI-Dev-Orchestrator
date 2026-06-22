# AI Project Director Backend Runnable and Evidence Skill
> Skill name: `ai-project-director-backend-runnable-and-evidence`
> Recommended repository path: `.kkr/skills/ai-project-director-backend-runnable-and-evidence/SKILL.md`
> Purpose: Govern long-running backend runnable baseline, smoke evidence, and evidence-driven AI Director task generation for AI-Dev-Orchestrator.
> Generated date: `2026-06-22`
---
## 1. Purpose
This skill governs long-running AI Project Director work after P9-REL backend executor evidence closeout.
Use it to prevent future long threads from only stacking feature slices while skipping the product-like backend runnable path.
It requires future work to make the backend:
1. startable through a clear local path;
2. checkable through a repeatable smoke harness;
3. reproducible with isolated runtime data;
4. safe from product runtime Git writes;
5. grounded in readonly repository evidence before AI Director task generation.
This skill does not replace `.kkr/skills/ai-project-director-command-governance/SKILL.md`.
It supplements that command governance skill with backend runnable baseline and evidence-driven director rules.
The core operating principle is simple:
- first prove the backend can run as a product path;
- then let AI Director inspect readonly repo evidence;
- then compose tasks from evidence;
- then assign executor-backed programmer and reviewer agents.
Do not let a strong executor sub-gate become a total-loop Pass claim.
## 2. Current verified baseline
Current recorded status:
- `P9-REL backend executor integration`: `Pass with note`
- `P9 production-safe long-running executor lifecycle`: `Partial`
- `AI Project Director total loop`: `Partial`
- Codex controlled native smoke passed
- Claude Code controlled native smoke passed
- Codex supervisor-managed native smoke passed
- Claude Code supervisor-managed native smoke passed
- TaskWorker supervisor-managed silent launch wiring passed
- Worker subprocess lifecycle safety gate passed
The `Pass with note` means backend evidence supports controlled native smoke, supervisor-managed smoke, Worker silent launch wiring, and Worker subprocess lifecycle safety gate.
It does not mean product-grade long-running lifecycle is complete.
It does not mean AI Project Director total loop is Pass.
Critical commits:
- `3a9877320213d470b8f7b6e4e5ec89a7b2c9559c` - `backend: wire native process supervisor into smoke`
- `501a9d8e60eb8f0fa6e005a5f15b78a8e74a7a1e` - `backend: wire process supervisor into worker silent launch`
- `f48a14d8abf31129a4740e9f1cc04a2fc086c8fa` - `backend: guard worker native subprocess lifecycle`
- `2a73229444cd93a26613b3f0660b298237bf99f6` - `docs: update P9 real executor launch ledger`
Baseline evidence surfaces include:
- `runtime/orchestrator/app/external_executors/actual_native_launcher.py`
- `runtime/orchestrator/app/external_executors/actual_process_supervisor.py`
- `runtime/orchestrator/app/external_executors/actual_native_smoke.py`
- `runtime/orchestrator/app/workers/task_worker.py`
- `runtime/orchestrator/scripts/p9_real_executor_native_smoke.py`
- `runtime/orchestrator/tests/test_real_executor_native_smoke.py`
- `runtime/orchestrator/tests/test_worker_workspace_readonly_validation.py`
- `docs/product/ai-project-director/P9-REL-real-executor-launch-evidence-ledger-20260622.md`
## 3. Non-negotiable boundaries
Repeat these boundaries in every generated task that uses this skill.
- Frontend stays frozen unless the user explicitly approves frontend work.
- Product runtime Git write is forbidden.
- No product runtime `git add`, `git commit`, `git push`, PR, or merge.
- Development workflow `git add`, `git commit`, and `git push` is allowed and required for task delivery when the user asks for repository delivery.
- Do not expose pid, raw command, stdout, stderr, env, token, secret, or api_key.
- Do not use `shell=True`.
- Do not introduce a new subprocess boundary unless the task explicitly scopes it.
- Do not touch `docs/superpowers/`.
- Keep AI Project Director total loop as `Partial` until final UAT proves the whole chain.
Do not confuse two Git domains:
1. development Git operations by the coding agent for repository delivery;
2. product runtime Git writes performed by AI-Dev-Orchestrator itself.
Only the first domain is allowed here.
The second domain remains forbidden and not implemented by this skill.
## 4. Long-thread priority order
Future long-thread token spend must follow this order unless the user explicitly overrides it.
### Priority 1: P9-RUN-A Backend Runnable Baseline and Product Smoke Harness
Goal:
- define a Mac / `uv` standard startup path;
- run with isolated SQLite / runtime data;
- import `app.main:app`;
- call `init_database`;
- prove `GET /health`;
- create a simulate task;
- call `POST /workers/run-once`;
- read task detail and runs;
- emit a JSON smoke summary;
- do not start Codex or Claude;
- do not open product runtime Git write.
This is the default next task until it passes.
### Priority 2: P10-A Project Director Readonly Repo Evidence Pack
Goal:
- give AI Director real repository evidence before plan or task generation;
- keep the evidence pack readonly;
- include related files, impact paths, forbidden paths, suggested tests, risks, and unknowns;
- do not write the repository;
- do not start a write-capable executor.
### Priority 3: P10-B Evidence-Grounded Task Composer
Goal:
- make AI Director generate tasks from the evidence pack;
- require every task to include evidence references;
- require allowed files, forbidden files, and targeted tests;
- forbid tasks generated only from one user sentence when repo evidence is available.
### Priority 4: P10-C Executor-Backed Programmer and Reviewer Agents
Goal:
- make programmer agent executor-backed by default;
- make reviewer agent executor-backed for deep review;
- keep AI Director itself not permanently bound to an executor;
- allow AI Director to schedule a readonly reviewer executor when review depth requires it.
### Priority 5: Long-running executor lifecycle
Goal:
- make supervisor more than smoke cleanup;
- support status, heartbeat, timeout, terminate, kill, and cleanup;
- consider long-running behavior only after runnable baseline and evidence-driven tasking are proven;
- do not open product runtime Git writes early.
## 5. Backend runnable baseline rules
Use these acceptance rules for P9-RUN-A.
- Backend must have a one-command smoke script.
- Smoke must use isolated temporary runtime data.
- Smoke must not pollute `runtime/orchestrator/data`.
- Smoke must output a JSON summary.
- Smoke must prove the basic API and Worker simulate main chain.
- Smoke must not really start Codex.
- Smoke must not really start Claude Code.
- Smoke must not perform product runtime Git writes.
- README must give Mac / `uv` startup commands.
- README must distinguish normal smoke, real executor smoke, and unfinished long-running lifecycle.
Minimum P9-RUN-A smoke path:
1. create isolated temp runtime directory;
2. configure SQLite/runtime data to that directory;
3. import `app.main:app`;
4. initialize database;
5. call `GET /health`;
6. create one simulate task through the public API;
7. call `POST /workers/run-once`;
8. read task detail and run history through public APIs;
9. emit machine-readable JSON summary;
10. clean up temp data.
Do not accept direct database mutation as smoke proof.
Do not accept unit tests alone as product runnable proof.
Do not accept native executor smoke as a replacement for the baseline product smoke.
## 6. Evidence pack rules
Use these rules for P10-A.
- Evidence pack is readonly repository reconnaissance before AI Director assigns tasks.
- Evidence pack is not execution completion.
- Evidence pack is not user approval.
- Evidence pack is not Git write authorization.
- Evidence pack must not contain secret, token, or api_key values.
- Evidence pack must record unknowns instead of pretending complete knowledge.
- Evidence pack must be referenceable by generated task instructions.
Required evidence pack fields:
- `origin_main_commit`
- `related_files`
- `impact_paths`
- `forbidden_paths`
- `suggested_tests`
- `risks`
- `unknowns`
- `evidence_refs`
- `product_runtime_git_write_allowed=false`
If the evidence pack cannot identify enough repository facts, the next task must be an evidence improvement task, not a programmer implementation task.
## 7. Task instruction generation rules
Every long-line task generated under this skill must include:
- expected `origin/main` commit;
- start mismatch stop rule;
- allowed files;
- forbidden files;
- product runtime Git forbidden statement;
- development `git add` / `git commit` / `git push` required statement when repository delivery is requested;
- targeted tests only;
- report checklist;
- `AI Project Director 总闭环 remains Partial`.
The start mismatch stop rule must say:
```text
If origin/main is not the expected commit, stop, report the latest commit hash and commit message, and do not continue from stale state.
```
Allowed files and forbidden files must be explicit paths or path globs.
Do not say "modify relevant files" when the task can name the intended surfaces.
Do not ask an executor to run broad suites unless the risk requires it.
Do not let executor tasks imply product runtime Git write capability.
## 8. Review rules
When reviewing execution results, apply this order:
1. Check latest GitHub `origin/main`.
2. Verify the reported commit equals current `origin/main`.
3. Inspect the diff.
4. Inspect critical code or document files.
5. Inspect test or evidence commands and outputs.
6. Compare changed paths against allowed and forbidden paths.
7. Decide the gate from repository facts, not executor self-assessment.
Use these verdicts precisely:
- `Pass with note`: stage evidence passes, but a stated downstream gap remains.
- `Partial`: main progress exists, but required stage proof or downstream readiness is missing.
- `Blocked`: current state prevents valid progress without a fix, missing dependency, or user decision.
If review finds a problem, generate a small R1 fix task.
Do not resend the full original task unless the work is structurally unusable.
Do not advance to P10-A until P9-RUN-A has real smoke evidence.
Do not mark AI Project Director total loop as Pass from a backend-only result.
## 9. Standard next task decision
When the user asks "下一步做什么", decide from the backend runnable baseline state.
If P9-RUN-A Backend Runnable Baseline and Product Smoke Harness has not passed, recommend:
```text
P9-RUN-A Backend Runnable Baseline and Product Smoke Harness
```
Reason:
- backend must become startable, smoke-checkable, and reproducible before AI Director produces more implementation tasks.
Only after P9-RUN-A passes, recommend:
```text
P10-A Project Director Readonly Repo Evidence Pack
```
Reason:
- AI Director should inspect real repo evidence before composing programmer or reviewer tasks.
If a user asks for a different next step, report the risk and follow the explicit user instruction only if it does not violate the non-negotiable boundaries.
## 10. Standard report checklist
Every completion report under this skill must include:
1. latest `origin/main` hash
2. commit message
3. modified files
4. whether `apps/web` changed
5. whether runtime app changed
6. whether tests changed
7. whether `docs/superpowers/` stayed untouched
8. targeted tests and results
9. `git diff --check`
10. `git status --short --untracked-files=all`
11. pushed
12. Gate
13. AI Project Director total loop remains `Partial`
Use short factual wording.
Do not translate `Pass`, `Partial`, or `Blocked` into softer labels.
Do not hide untracked files.
Do not report "clean" if unrelated untracked files remain.
For this skill itself, a valid delivery report must also state:
- skill contains P9-RUN-A priority;
- skill contains P10-A evidence pack rules;
- skill explicitly forbids product runtime Git writes;
- skill explicitly requires development Git delivery when requested;
- skill explicitly keeps AI Project Director total loop as `Partial`.
