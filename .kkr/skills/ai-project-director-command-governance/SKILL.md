# AI Project Director Command Governance Skill

> Skill name: `ai-project-director-command-governance`
> Recommended repository path: `.kkr/skills/ai-project-director-command-governance/SKILL.md`
> Purpose: Govern how ChatGPT generates and reviews task instructions for AI-Dev-Orchestrator / AI Project Director closure work.
> Primary product baseline: `docs/product/ai-project-director/page-information-architecture-20260518.md`

---

## 1. Purpose

This skill controls the instruction workflow for AI Project Director development, evidence verification, and closure.

It exists to prevent drift across long-running conversations. Whenever the user asks to continue AI Project Director work, ChatGPT must use this skill to decide:

1. which document is authoritative;
2. which model should execute the task;
3. what files must be checked first;
4. what boundaries must be enforced;
5. what evidence is required before advancing;
6. how to review execution reports against the real GitHub repository.

This skill does **not** replace the product design documents. It governs **how instructions are generated and reviewed**.

---

## 2. Authority hierarchy

When documents conflict, use this order.

### 2.1 Highest product authority

`docs/product/ai-project-director/page-information-architecture-20260518.md`

This is the master product baseline. All AI Project Director implementation, page work, backend closure, evidence scripts, and future task instructions must be traceable to this file.

The file defines the product direction as an AI project orchestration workbench: the user gives a goal; the AI project director creates plans, splits tasks, assigns agents, binds skills, supervises execution, identifies blockers, proposes adjustments, and escalates high-risk decisions for user approval.

It also defines the six primary navigation/page groups and cross-page mechanisms:

1. 工作台
2. 项目
3. 执行中心：任务队列、运行观测、仓库工作区
4. 成果中心：交付物、审批
5. 治理
6. 设置
7. 全局自动摘要机制

The implementation must preserve the document's constraints:

- no project rebuild;
- no technology stack replacement;
- no casual backend API protocol changes;
- no unbounded rewrites;
- no fake UI buttons;
- no UI that looks complete but lacks real closure;
- buttons must either call a real backend, navigate to a real page, or be disabled with a clear reason;
- page changes must remain aligned with the product baseline.

### 2.2 Derived planning and acceptance documents

The following documents are important, but they are derived from the master page information architecture document:

- `docs/product/ai-project-director/closure-flow-20260518.md`
- `docs/product/ai-project-director/closure-checklist-20260518.md`
- `docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md`
- `docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md`

Use them for closure flow, acceptance criteria, gap state, and evidence records. Do **not** let them redefine the product direction if they conflict with `page-information-architecture-20260518.md`.

### 2.3 Runtime evidence documents

Stage-specific verification documents prove what has been tested. They are evidence, not product authority.

Examples:

- `verification-project-director-real-ai-run-summary-*.md`
- `verification-project-director-provider-run-deliverable-approval-*.md`
- `verification-project-director-repository-binding-snapshot-*.md`
- `verification-project-director-file-locator-context-pack-*.md`

Use them to verify implementation state. Do not use them to change product scope.

### 2.4 Code and GitHub state

The real implementation state must be checked from the current `origin/main`.

Never continue based only on memory, a previous chat summary, or an executor's completion report.

---

## 3. When to use this skill

Use this skill whenever the user asks to:

- continue AI Project Director closure work;
- generate an instruction for Codex, DeepSeek, Claude Code, or another model;
- review an execution report;
- decide whether a BCG stage is Pass / Partial / Blocked / Missing;
- compare implementation with the AI Project Director product design;
- prevent future conversations from drifting.

---

## 4. Mandatory operating loop

Every task cycle must follow this loop.

### 4.1 Before generating a new instruction

ChatGPT must:

1. Check the latest GitHub `origin/main` commit.
2. Compare it with the user's reported commit hash.
3. Read or re-check the master product baseline if the task can affect product direction:
   - `docs/product/ai-project-director/page-information-architecture-20260518.md`
4. Read the relevant derived documents for the current stage:
   - closure flow;
   - closure checklist;
   - backend freeze;
   - execution ledger;
   - current verification evidence, if any.
5. Inspect the relevant implementation files before writing an instruction.
6. Determine whether the next task is:
   - evidence / script / documentation work;
   - minimal business-code repair;
   - frontend UX work;
   - product-document consistency audit;
   - blocked due to missing implementation.
7. Select the correct executor model.
8. Generate one short, bounded, checkable instruction.

### 4.2 After the executor reports completion

ChatGPT must:

1. Fetch the latest GitHub `origin/main`.
2. Verify the reported commit exists and is the current main.
3. Inspect commit diff or changed files.
4. Verify the executor did not exceed scope.
5. Verify critical code paths, not just document text.
6. Verify tests / live evidence commands match the task.
7. Verify documentation did not falsely mark Partial as Pass.
8. Verify AI Project Director total closure was not marked Pass prematurely.
9. Decide the gate:
   - Pass;
   - Partial;
   - Blocked;
   - Missing;
   - needs R1/R2 closeout.
10. Only then generate the next instruction.

---

## 5. Model assignment rules

### 5.1 DeepSeek is the default for evidence and verification

Use DeepSeek for:

- live evidence scripts;
- running evidence scripts;
- regression test execution;
- evidence JSON/report generation;
- verification documents;
- ledger/freeze document updates;
- implementation-vs-document consistency audits;
- stage gate summaries;
- proof collection and readback validation.

DeepSeek should **not** do broad business-code implementation. If DeepSeek finds a real implementation gap, it should stop and report the gap.

### 5.2 Codex is only for necessary business-code repair

Use Codex only when there is a clear implementation defect or missing business code, such as:

- missing backend route;
- broken service logic;
- security boundary bug;
- API response mismatch;
- repository safety bug;
- minimal frontend integration required by a defined phase.

Codex must not be assigned:

- live evidence script creation;
- running live evidence scripts;
- broad documentation updates;
- proof/report writing;
- product consistency audits;
- large refactors;
- exploratory work.

Codex may be asked to add or update narrow implementation-level tests directly tied to the code repair. Avoid asking Codex to run broad suites unless necessary.

### 5.3 Standard handoff after Codex

When Codex fixes business code:

1. Codex reports the code change and minimal tests.
2. ChatGPT reviews the real commit.
3. If the code repair is acceptable, the next task goes to DeepSeek for:
   - live evidence;
   - documentation;
   - ledger/freeze update;
   - gate proof.

Do not let Codex both fix the business code and own final evidence closure.

---

## 6. Mandatory instruction format

Every instruction generated by ChatGPT must include these blocks.

```text
建议使用模型：<DeepSeek / Codex>
任务类型：<证据脚本 / 文档回填 / 最小业务代码修补 / 前端集成 / 一致性审计>
原因：<why this model is appropriate>

请先确认 origin/main 最新提交为：
<commit_sha>

主产品基线：
docs/product/ai-project-director/page-information-architecture-20260518.md

当前阶段：
<BCG-xx / phase name>

目标：
<single clear objective>

必须先检查：
- <primary product doc if product direction relevant>
- <stage docs>
- <code files>
- <tests>
- <skills>

已知接口 / 能力：
- <existing routes/services>

实现 / 验证要求：
1. ...
2. ...

必须断言：
- ...

必须运行：
<commands>

文档 / 台账要求：
- <only if assigned to DeepSeek, or if explicitly allowed>

严格边界：
- ...

完成后回报：
1. 使用模型
2. 最新提交哈希
3. 修改文件列表
4. 关键 ID / API / evidence
5. 测试命令与结果
6. 是否改前端 / 是否运行 build
7. Gate 结论
```

Do not produce vague instructions such as "optimize this module" or "continue improving".

---

## 7. Mandatory review format

When reviewing a completion report, ChatGPT must respond using this structure:

```text
审查结论：<Pass / Partial / Blocked / Missing / R1 required>

已核对：
- origin/main commit
- changed files
- critical implementation files
- tests / evidence
- documentation state

符合项：
1. ...

问题 / 缺口：
1. ...

Gate：
<stage gate>
<AI Project Director total gate>

下一步：
<next model and bounded instruction>
```

If the executor report conflicts with repository state, repository state wins.

---

## 8. Gate definitions

### 8.1 Pass

A stage can be Pass only when:

- real API or real service path is used;
- real persisted data is read back;
- tests or live evidence prove the required assertions;
- documentation or ledger state is correct;
- no blocker remains for the stage's defined scope;
- the result maps back to `page-information-architecture-20260518.md`.

### 8.2 Partial

Use Partial when the main path works but an important gap remains, such as:

- security gap;
- missing executable rework task;
- UI not integrated;
- evidence exists but downstream chain cannot consume it;
- stage is usable but not complete.

### 8.3 Blocked

Use Blocked when the stage cannot proceed because:

- required backend route does not exist;
- required service logic is missing;
- data dependency is unavailable;
- safety boundary prevents valid execution;
- current implementation contradicts the primary product baseline.

### 8.4 Missing

Use Missing when there is only:

- documentation;
- mock evidence;
- simulated evidence;
- unverified implementation;
- claims without live proof.

### 8.5 AI Project Director total closure rule

Do not mark AI Project Director total closure as Pass until all required product chains have real evidence:

- goal / plan;
- task creation;
- worker run;
- run logs;
- AI summary;
- deliverable;
- approval;
- rework chain;
- repository binding;
- snapshot;
- file locator;
- context pack;
- change plan;
- change batch;
- preflight;
- commit candidate;
- apply-local / git commit, if in scope;
- release gate;
- governance;
- cost telemetry;
- rollup;
- frontend integration.

If any of these remain incomplete, total closure is Partial.

---

## 9. Boundaries that must be repeated in instructions

Unless the phase explicitly allows it, every instruction must prohibit:

- rebuilding the project;
- replacing the technology stack;
- casually changing backend API protocol;
- broad rewrites;
- fake UI buttons;
- mock/simulate evidence as functional proof;
- direct database modification to bypass APIs;
- printing or writing API keys;
- repository apply-local / git-commit;
- planning/apply;
- automatic worker execution;
- changing frontend when the phase is backend-only;
- running `apps/web build` unless frontend changed;
- marking Partial as Pass;
- marking AI Project Director total closure as Pass prematurely.

When the task is Codex-specific, add:

- Codex must not write or run live evidence scripts;
- Codex must not do broad documentation closure;
- Codex must only implement the minimal business-code fix and narrow tests.

When the task is DeepSeek-specific, add:

- DeepSeek must not do broad business-code repair;
- if code is missing or broken, stop and report the gap.

---

## 10. Primary product alignment checklist

Before allowing a stage to pass, map it back to the master product baseline.

Ask:

1. Does this stage support the AI project director vision from `page-information-architecture-20260518.md`?
2. Does it help the user move from goal to plan, execution, delivery, approval, repository work, governance, or summary?
3. Does the UI/API behavior avoid fake closure?
4. Does it preserve page responsibility boundaries?
5. Does it avoid dumping unrelated data into the wrong page?
6. Does it support global AI summary behavior when relevant?
7. Does it keep technical details behind appropriate detail views / evidence paths?
8. Can downstream stages consume this result?

If the answer is no, do not mark Pass.

---

## 11. Documentation rules

To avoid document sprawl:

1. Do not create new planning documents unless the user explicitly asks.
2. Use the primary product baseline as the product authority.
3. Use `backend-closure-gap-freeze-20260519-v2.md` for current gap state.
4. Use `execution-plan-backfill-ledger-20260519.md` for execution records.
5. Use stage verification docs only when a BCG stage needs evidence proof.
6. Do not add broad narrative documents for every small fix.
7. Put reusable workflow rules into this skill, not into scattered docs.
8. Keep evidence documents focused on facts: IDs, APIs, commands, results, gaps, gate.

---

## 12. Stage progression rules

1. Do not skip stages.
2. Do not enter the next stage while the current stage is Partial or Blocked unless the user explicitly approves the risk.
3. If a live evidence stage finds a code gap, stop and switch to a Codex repair instruction.
4. If Codex repairs code, switch back to DeepSeek for evidence closure.
5. If documentation says Pass but code does not prove it, downgrade the gate.
6. If code works but product baseline is not satisfied, downgrade the gate.
7. If a downstream stage cannot consume the result, downgrade the gate.

---

## 13. Standard DeepSeek instruction template

Use this template for evidence work.

```text
建议使用模型：DeepSeek。
任务类型：证据脚本 + 测试运行 + 文档/台账回填。
原因：本阶段需要验证真实链路，不需要业务代码实现。

请先确认 origin/main 最新提交为：
<commit_sha>

主产品基线：
docs/product/ai-project-director/page-information-architecture-20260518.md

目标：
<stage objective>

必须先检查：
- docs/product/ai-project-director/page-information-architecture-20260518.md
- docs/product/ai-project-director/backend-closure-gap-freeze-20260519-v2.md
- docs/product/ai-project-director/execution-plan-backfill-ledger-20260519.md
- <stage code files>
- <stage tests>

要求：
1. 使用真实 API / service path。
2. 使用真实 persisted data readback。
3. 不使用 mock/simulate 代替功能验收。
4. 如果发现缺业务代码，停止并回报，不要自行大改。
5. 回填 evidence docs / freeze / ledger。

严格边界：
- 不改业务代码。
- 不改前端。
- 不调用 apply-local / git-commit。
- 不调用 planning/apply，除非阶段明确允许。
- 不写主仓库工作树作为业务数据。
- 不修改数据库文件绕过接口。
- 不打印、不写入 API key。
- 不把总闭环写成 Pass。

完成后回报：
1. 使用模型
2. 最新提交哈希
3. 修改文件列表
4. 使用 API / IDs
5. live evidence 命令与结果
6. 普通回归测试命令与结果
7. 是否存在 Runtime Evidence Gap
8. Gate 结论
```

---

## 14. Standard Codex instruction template

Use this template only for business-code repair.

```text
建议使用模型：Codex。
任务类型：最小业务代码修补 + 窄范围测试。
原因：当前存在明确代码缺口，必须修业务逻辑后才能继续 evidence。

请先确认 origin/main 最新提交为：
<commit_sha>

主产品基线：
docs/product/ai-project-director/page-information-architecture-20260518.md

目标：
<one minimal code repair>

必须先检查：
- <exact code files>
- <related tests>
- docs/product/ai-project-director/page-information-architecture-20260518.md if product behavior is affected

实现要求：
1. 只修明确缺口。
2. 不做大规模重构。
3. 不改无关接口。
4. 保留安全边界。
5. 增加或更新最小必要测试。

严格边界：
- 不写 live evidence script。
- 不运行 live evidence script。
- 不负责文档验收闭环。
- 不改前端，除非阶段明确要求。
- 不调用 apply-local / git-commit。
- 不调用 planning/apply。
- 不新增后台 daemon。
- 不打印、不写入 API key。
- 不把总闭环写成 Pass。

必须运行：
<minimal targeted tests only>

完成后回报：
1. 使用模型：Codex
2. 最新提交哈希
3. 修改文件列表
4. 修复点
5. 测试命令与结果
6. 是否改前端 / 是否运行 build
7. Gate 结论：Code Ready / Evidence Pending
```

---

## 15. Executor report review checklist

When the user sends an executor report, ChatGPT must verify:

- reported commit equals `origin/main`;
- changed files match the task;
- no forbidden files were changed;
- route/service logic exists, not only tests;
- tests actually cover required assertions;
- evidence scripts do not silently convert failures into gaps unless the instruction allowed Partial;
- docs do not overstate Pass;
- product baseline remains satisfied;
- downstream stages can consume the result.

If any item fails, generate an R1/R2 closeout instruction instead of moving forward.

---

## 16. Project-specific standing facts

The AI Project Director closure process currently uses BCG-style evidence gates.

Important standing rules:

1. The product master baseline is `page-information-architecture-20260518.md`.
2. `backend-closure-gap-freeze-20260519-v2.md` tracks current closure state.
3. `execution-plan-backfill-ledger-20260519.md` tracks execution records.
4. Codex should only receive necessary code repair tasks.
5. DeepSeek should receive evidence, scripts, testing, and documentation tasks.
6. If a Codex fix affects a stage, DeepSeek must later prove it with evidence.
7. AI Project Director total closure remains Partial until every required chain is verified.

---

## 17. Opening prompt for future conversations

The user may start a new conversation with:

```text
请先读取 .kkr/skills/ai-project-director-command-governance/SKILL.md，
并严格按这个 skill 继续推进 AI Project Director 闭环。
主产品基线是 docs/product/ai-project-director/page-information-architecture-20260518.md。
先检查 GitHub 最新 origin/main，不要凭记忆继续。
```

When this prompt is used, ChatGPT must apply this skill before giving any instruction.
