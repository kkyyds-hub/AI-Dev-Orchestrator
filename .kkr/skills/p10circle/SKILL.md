---
name: p10circle
description: Use when continuing AI-Dev-Orchestrator AI Project Director P10 work that must move from readonly repository evidence to evidence-grounded task composition, executor-backed programmer/reviewer agent binding, and dry-run orchestration without product runtime Git writes or premature total-loop Pass claims.
---
# AI Project Director P10 Evidence-to-Agent Chain Skill
> Skill name: `p10circle`
> Recommended Codex path: `/Users/kk/.codex/skills/p10circle/SKILL.md`
> Recommended repository path: `.kkr/skills/p10circle/SKILL.md`
> Purpose: Govern P10-A to P10-D long-running evidence-to-agent chain for AI-Dev-Orchestrator.
> Generated date: `2026-06-22`
---
## 1. Purpose
Use this skill to govern P10 long-running work in AI-Dev-Orchestrator.
It exists to keep P10 in this order:
1. repo evidence;
2. evidence-grounded task composer;
3. programmer / reviewer agent binding;
4. dry-run orchestration.
This skill prevents AI Director from generating tasks from only one user sentence.
It prevents strong executor capability from hiding weak boss-level task definition.
It requires AI Director to inspect readonly repository evidence before composing or assigning tasks.
It requires every generated task to carry evidence, allowed files, forbidden files, tests, risks, and unknowns.
It does not replace `.kkr/skills/ai-project-director-command-governance/SKILL.md`.
It does not replace `.kkr/skills/ai-project-director-backend-runnable-and-evidence/SKILL.md`.
It supplements those skills with P10-A to P10-D sequence and Gate rules.
Creation note:
- `.kkr/skills/ai-project-director-task-instruction-composer/SKILL.md` was missing during creation.
- Do not create that old skill as part of P10 work.
- Do not treat the missing old skill as a blocker for using `p10circle`.
## 2. Current baseline before P10
Current verified state before P10:
- `P9-REL backend executor integration`: `Pass with note`
- `P9-RUN-A Backend runnable baseline`: `Pass with note`
- `P9 production-safe long-running executor lifecycle`: `Partial`
- `AI Project Director total loop`: `Partial`
- P9-RUN-A has isolated runtime data smoke.
- P9-RUN-A smoke does not start Codex.
- P9-RUN-A smoke does not start Claude Code.
- Product runtime Git write remains forbidden.
Critical commits:
- `2a73229444cd93a26613b3f0660b298237bf99f6` - `docs: update P9 real executor launch ledger`
- `198ae96f37982a1b9f5efd03f58bc16533586b4c` - `docs: add backend runnable evidence skill`
- `714a9137c652bccbc5c9dd1ba8921e4778560628` - `backend: add runnable baseline smoke`
Baseline evidence:
- P9-REL ledger records controlled Codex / Claude native smoke and Worker subprocess safety gate.
- P9-RUN-A smoke proves backend import, DB init, `/health`, task create, `workers/run-once`, task detail, and run readback.
- Backend runnable proof is not total product closure.
- Long-running executor lifecycle remains unfinished.
## 3. Non-negotiable boundaries
Repeat these boundaries in every P10 task:
- Product runtime Git write is forbidden.
- No product runtime `git add`, `git commit`, `git push`, PR, or merge.
- Development `git add`, `git commit`, and `git push` is allowed and required for repository task delivery.
- No frontend work unless the user explicitly approves it.
- Do not expose pid, raw command, stdout, stderr, env, token, secret, or api_key.
- Do not use `shell=True`.
- Do not create a new subprocess boundary unless explicitly scoped.
- Do not touch `docs/superpowers/`.
- Keep AI Project Director total loop as `Partial` until final UAT.
- P10 evidence pack is readonly and is not execution.
- P10 generated task is not approval.
- P10 agent binding is not product Git write authorization.
Treat product runtime Git and development Git as separate domains.
Development Git delivers repository changes by the coding agent.
Product runtime Git would be AI-Dev-Orchestrator itself writing Git.
P10 must not imply the second domain is available.
## 4. P10 stage sequence
Run P10 in strict order: P10-A, then P10-B, then P10-C, then P10-D.
### P10-A Project Director Readonly Repo Evidence Pack
Goal:
- Make AI Director collect real repository evidence before plans or tasks.
- Keep the evidence pack readonly.
- Do not modify code.
- Do not write the repository.
- Do not start a write-capable executor.
- Do not open product runtime Git write.
Required output fields:
- `origin_main_commit`
- `evidence_pack_id`
- `repo_root`
- `related_files`
- `impact_paths`
- `forbidden_paths`
- `suggested_tests`
- `risks`
- `unknowns`
- `evidence_refs`
- `source_detail`
- `product_runtime_git_write_allowed=false`
- `frontend_required=false`
P10-A Gate:
- `Pass`: evidence pack is generated from real repository inspection.
- `Partial`: evidence pack is incomplete but safe and honest.
- `Blocked`: evidence pack guesses without repository facts.
### P10-B Evidence-Grounded Task Composer
Goal:
- Make AI Director compose tasks from a P10-A evidence pack.
- Require every task to cite `evidence_refs`.
- Require every task to include `allowed_files` and `forbidden_files`.
- Require every task to include `targeted_tests`.
- Require every task to include `risks` and `unknowns`.
- Forbid tasks created only from one user sentence when repository evidence exists.
Required output fields:
- `source_evidence_pack_id`
- `composed_tasks`
- `allowed_files`
- `forbidden_files`
- `required_reading`
- `targeted_tests`
- `risk_notes`
- `unknowns`
- `user_confirmation_required`
- `product_runtime_git_write_allowed=false`
P10-B Gate:
- `Pass`: every generated task references evidence.
- `Partial`: composer works but tasks lack tests or boundaries.
- `Blocked`: tasks are generated without an evidence pack.
### P10-C Executor-Backed Programmer and Reviewer Agent Binding
Goal:
- Make programmer agent executor-backed by default.
- Make reviewer agent executor-backed for deep review.
- Keep AI Director itself not permanently bound to an executor.
- Allow AI Director to schedule a readonly reviewer executor.
- Keep agent binding separate from real Git write authorization.
Definitions:
- Director = planner / reviewer / dispatcher.
- Programmer Agent = executor-backed implementation worker.
- Reviewer Agent = readonly or deep-review executor-backed reviewer.
- Evidence Pack = required input before task creation.
- Task Composer = evidence-grounded instruction generator.
P10-C Gate:
- `Pass`: programmer and reviewer role binding is explicit and safe.
- `Partial`: role model exists but is not wired to task dispatch.
- `Blocked`: AI Director becomes a permanent executor or product Git write is implied.
### P10-D Evidence-to-Agent Dry-Run Orchestration
Goal:
- Prove with backend dry-run or simulate harness:
  user goal -> repo evidence pack -> evidence-grounded tasks -> programmer/reviewer assignment -> no product Git write.
- Allow simulate / dry-run behavior.
- Do not require real long-running executor.
- Do not claim product total-loop Pass.
Must prove:
- evidence pack created;
- task composer consumed evidence pack;
- tasks include allowed and forbidden files;
- programmer / reviewer assignment exists;
- reviewer path stays readonly unless explicitly scoped;
- `product_runtime_git_write_allowed=false`;
- `frontend_required=false`;
- AI Project Director total loop remains `Partial`.
P10-D Gate:
- `Pass with note`: dry-run chain proves evidence-to-agent orchestration without product Git write.
- `Partial`: only part of the chain is proven.
- `Blocked`: it starts write-capable execution or claims total-loop Pass.
## 5. Long-thread execution rules
- P10-A-D may run in one long thread only with serial stage Gates.
- Do not start P10-B until P10-A is `Pass`.
- Do not start P10-C until P10-B is `Pass`.
- Do not start P10-D until P10-C is `Pass`.
- If any stage is `Blocked`, stop and report.
- Do not continue by inventing completion.
- Every stage must have a commit or explicitly explain why no commit is valid.
- Prefer one commit per stage.
- Avoid one giant commit that is hard to review.
- If the user asks to run everything at once, still keep stage checkpoints.
- Record checkpoint A after evidence pack.
- Record checkpoint B after task composer.
- Record checkpoint C after agent binding.
- Record checkpoint D after dry-run chain.
## 6. Required minimal evidence for each stage
P10-A evidence:
- file search / repository inspection evidence;
- `source_detail`;
- `unknowns`.
P10-B evidence:
- generated task references `evidence_pack_id`;
- `allowed_files` / `forbidden_files`;
- `targeted_tests`.
P10-C evidence:
- agent role binding model;
- executor-backed decision rules;
- readonly reviewer rules.
P10-D evidence:
- dry-run harness output;
- no product Git write;
- no frontend required;
- no Codex / Claude long-running lifecycle claim.
Do not accept self-report as evidence.
Repository state, diff, output JSON, targeted tests, and current `origin/main` are stronger than executor narrative.
## 7. Instruction generation rules
Every P10 subtask instruction must include:
- expected `origin/main` commit;
- start mismatch stop rule;
- allowed files;
- forbidden files;
- product runtime Git forbidden statement;
- development `git add` / `git commit` / `git push` required statement;
- targeted tests only;
- Gate checklist;
- `AI Project Director 总闭环 remains Partial`.
Use this start mismatch rule:
```text
If origin/main is not the expected commit, stop, report the latest commit hash and commit message, and do not continue from stale state.
```
Forbid these instruction patterns:
- "自行决定"
- "全面检查"
- "顺便优化"
- "相关文件都可以改"
- "跑全量测试"
- "如果方便就提交"
Prefer bounded tasks with exact paths, exact outputs, and exact report fields.
## 8. Review rules
When reviewing P10 output:
1. Check latest GitHub `origin/main`.
2. Compare base and head.
3. Inspect changed files.
4. Inspect critical implementation or skill files.
5. Inspect targeted tests or evidence output.
6. Check product runtime Git boundary.
7. Check whether evidence / task / dry-run was overstated as real completion.
8. Decide Gate.
If review finds a problem:
- Generate an R1 small repair task.
- Do not resend the whole P10-A-D task.
- Do not enter the next stage.
- Do not mark total loop `Pass`.
## 9. Standard P10 long-run report checklist
Every P10 long-thread report must include:
1. latest `origin/main` hash
2. commits per substage
3. modified files by substage
4. P10-A Gate
5. P10-B Gate
6. P10-C Gate
7. P10-D Gate
8. evidence pack output summary
9. task composer output summary
10. agent binding output summary
11. dry-run orchestration output summary
12. targeted tests and results
13. `git diff --check`
14. `git status --short --untracked-files=all`
15. whether `apps/web` changed
16. whether `docs/superpowers/` stayed untouched
17. whether product runtime Git write remains forbidden
18. whether AI Project Director total loop remains `Partial`
19. pushed
Do not hide untracked user files.
Do not report "clean" if unrelated untracked files remain.
## 10. Default next instruction after this skill
After this skill is created, the default next task is:
```text
P10-A-D Long Run / Evidence-to-Agent Dry-Run Chain
```
Execution must keep staged checkpoints:
- checkpoint A after evidence pack;
- checkpoint B after task composer;
- checkpoint C after agent binding;
- checkpoint D after dry-run chain.
Default next task priority:
1. Start with P10-A readonly repo evidence pack.
2. Advance only after P10-A Gate is `Pass`.
3. Compose evidence-grounded tasks in P10-B.
4. Bind programmer / reviewer agents in P10-C.
5. Prove the dry-run chain in P10-D.
Final reminder:
- P10-D dry-run can be `Pass with note`.
- AI Project Director total loop remains `Partial`.
- Product runtime Git write remains forbidden.
