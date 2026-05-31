# Stage 3 项目页 AI 总结 Runtime Evidence 审计

> 文档类型：Stage 3 project AI summary Runtime evidence verification
> 审计日期：2026-05-31
> 审计人/工具：DeepSeek (via Claude Code harness)
> 仓库：`https://github.com/kkyyds-hub/AI-Dev-Orchestrator.git`
> 基准 commit（审计时）：`79bc634712f32b671e86c0bc40e40968cc15a8d7`
> 基准 commit（复核刷新）：`e8b58ec359212457a08c4a129db294054ba951ff`
> 前置阶段：R1-P RC Pass（AI Project Director Release Candidate）
> 主产品基线：`docs/product/ai-project-director/page-information-architecture-20260518.md`
> 对应审计文档：`docs/product/project-summary/AI-Dev-Orchestrator-project-ai-summary-stage3-audit-20260531.md`

---

## 1. 验证范围

验证阶段 3 项目页 AI 总结按钮是否真实闭环。本次仅做 Runtime evidence 审计和文档回填，不修改业务代码。

---

## 2. 后端 API 验证结果

### 2.1 GET /projects/{project_id}/ai-summary

| 断言 | 预期 | 实际 | 结果 |
|---|---|---|---|
| 只读当前 active summary | 不触发生成 | 返回 active_summary=None（空态）| Pass |
| 无 summary 时返回空态 | active_summary=null | `{"project_id":"...", "active_summary": null}` | Pass |
| 404 for missing project | 404 | 测试通过 | Pass |

代码位置：`runtime/orchestrator/app/api/routes/projects.py:1975-2000`

### 2.2 POST /projects/{project_id}/ai-summary/generate

| 断言 | 预期 | 实际 | 结果 |
|---|---|---|---|
| 生成并保存 rule_fallback 总结 | source=rule_fallback | source="rule_fallback", triggered_ai=false | Pass |
| 不调用真实 provider | 无 OpenAI / DeepSeek 调用 | model_provider="local_rule_engine" | Pass |
| 生成后 GET 能 readback | same id + markdown | active_summary.id == generated.id | Pass |
| 幂等：同 source 重复调用复用 | 返回相同 id | 第二次 POST generate 返回相同 id | Pass |

代码位置：`runtime/orchestrator/app/api/routes/projects.py:2003-2027`
服务实现：`runtime/orchestrator/app/services/project_ai_summary_service.py:49-80`

### 2.3 POST /projects/{project_id}/ai-summary/regenerate

| 断言 | 预期 | 实际 | 结果 |
|---|---|---|---|
| 重新生成 | 201 + new snapshot | 201, new id != old id | Pass |
| 旧 summary 标记 stale | mark_active_stale 执行 | 旧记录 stale=true | Pass |
| 新 summary 成为 active | active_summary 返回新记录 | readback 返回新 id | Pass |
| 生成后 GET 能 readback | same new id | active_summary.id == regenerated.id | Pass |

代码位置：`runtime/orchestrator/app/api/routes/projects.py:2030-2055`
服务实现：`runtime/orchestrator/app/services/project_ai_summary_service.py:82-83`

### 2.4 持久化字段

| 字段 | 存在 | 说明 |
|---|---|---|
| source | ✓ | `RunAISummarySource.RULE_FALLBACK` → `"rule_fallback"` |
| source_hash | ✓ | = source_fingerprint（SHA-256 of source_payload JSON）|
| source_version | ✓ | `"project.summary.v1"` |
| stale | ✓ | 默认 false；regenerate 时旧记录标记 true |
| summary_markdown | ✓ | 中文 Markdown，6 节结构（项目结论/当前状态/当前重点/阶段进展/风险与阻塞/下一步建议）|
| generated_at | ✓ | UTC datetime，创建时设置 |

Domain model：`runtime/orchestrator/app/domain/project_ai_summary.py`
Repository：`runtime/orchestrator/app/repositories/project_ai_summary_repository.py`
DB Table：`runtime/orchestrator/app/core/db_tables.py:159-217`（`project_ai_summaries` 表）

### 2.5 中文 Markdown 复核（2026-05-31 第 2 轮）

Codex 已将摘要从英文 5 节改为中文 6 节。复核确认：

**包含的中文小节（6 节）：**

| 小节标题 | 内容 | 结果 |
|---|---|---|
| `## 项目结论` | 项目名称 + 阶段 + 状态 + summary | Pass |
| `## 当前状态` | 项目状态、任务总数、已完成/执行中/已阻塞/待人工处理、最近更新时间 | Pass |
| `## 当前重点` | Top 3 活跃任务，含中文状态/优先级/风险标签 | Pass |
| `## 阶段进展` | 当前阶段、下一目标阶段、是否可推进、阶段阻塞原因 | Pass |
| `## 风险与阻塞` | **新增**：当前阻塞任务数量、待人工处理任务数量、阶段阻塞原因或无阻塞说明 | Pass |
| `## 下一步建议` | 优先解除阶段阻塞、处理阻塞任务、跟进待人工处理、推进任务 | Pass |

**不含的英文标题：**

| 英文标题 | 确认不出现 |
|---|---|
| `## Project Conclusion` | ✓ 已确认 |
| `## Current Status` | ✓ 已确认 |
| `## Current Focus` | ✓ 已确认 |
| `## Stage Progress` | ✓ 已确认 |
| `## Next Steps` | ✓ 已确认 |

**"风险与阻塞"小节内容验证：**

| 内容 | 结果 |
|---|---|
| 当前阻塞任务数量 | ✓ （如 `当前阻塞任务数量：1。`）|
| 当前待人工处理任务数量 | ✓ （如 `当前待人工处理任务数量：1。`）|
| 阶段阻塞原因（若有） | ✓ |
| 无阻塞时说明（若阶段守卫已通过） | ✓ |

代码位置：`runtime/orchestrator/app/services/project_ai_summary_service.py:265-276`（`_build_markdown` 中 risk_lines）
测试验证：`runtime/orchestrator/tests/test_project_ai_summary_api.py:110-124`（`_assert_project_summary_payload`）

---

## 3. 前端按钮闭环验证结果

### 3.1 项目总结卡片

| 断言 | 预期 | 实际 | 结果 |
|---|---|---|---|
| 存在"项目总结"卡片 | ProjectAiSummaryCard | 在 ProjectDetailHeader 中渲染 | Pass |
| 无 summary 时"生成项目总结"按钮 | 点击 → POST generate | handleGenerate → generateProjectAiSummary | Pass |
| 有 summary 时"重新生成项目总结"按钮 | 点击 → POST regenerate | handleRegenerate → regenerateProjectAiSummary | Pass |
| generate 成功后自动 readback | POST 后 GET | handleGenerate → await generate → await readbackSummary | Pass |
| regenerate 成功后自动 readback | POST 后 GET | handleRegenerate → await regenerate → await readbackSummary | Pass |
| 主界面展示 Markdown | RunAiSummaryMarkdown 组件 | react-markdown 安全渲染 | Pass |

代码位置：
- `apps/web/src/features/project-summary/ProjectAiSummaryCard.tsx`
- `apps/web/src/features/project-summary/api.ts`
- `apps/web/src/features/project-summary/types.ts`
- 使用位置：`apps/web/src/features/projects/components/ProjectDetailHeader.tsx:69`

### 3.2 来源 badge

| 断言 | 预期 | 实际 | 结果 |
|---|---|---|---|
| rule_fallback → "规则回退" | warning tone | StatusBadge label="规则回退" tone="warning" | Pass |
| ai → "AI 生成" | success tone | StatusBadge label="AI 生成" tone="success" | Pass |

### 3.3 stale 标识

| 断言 | 预期 | 实际 | 结果 |
|---|---|---|---|
| stale=true → "摘要可能已过期" | warning tone | StatusBadge label="摘要可能已过期" tone="warning" | Pass |

### 3.4 技术字段不展示

前端 UI 不展示以下技术字段（仅存在 TypeScript type 定义中供内部使用）：
- model_provider ✓
- model_name ✓
- source_fingerprint ✓
- provider_receipt_id ✓
- prompt_hash ✓
- triggered_ai ✓

### 3.5 无假按钮

- 按钮均真实调用 POST API ✓
- 无 alert-only / console-only 行为 ✓
- 按钮通过 `disabled={isBusy}` 控制状态 ✓

---

## 4. 测试命令与结果

### 4.1 后端集成测试

```
cd runtime/orchestrator
python -m pytest tests/test_project_ai_summary_api.py -q
```

**结果（第 1 轮，commit 79bc634）：4 passed in 2.45s**
**结果（第 2 轮复核，commit e8b58ec）：4 passed in 2.42s**（测试文件已更新为中文断言）

| 测试 | 结果 | 备注 |
|---|---|---|---|
| test_get_project_ai_summary_does_not_generate_when_empty | Pass | GET 返回空态 |
| test_generate_project_ai_summary_saves_and_get_reads_back | Pass | 包含中文 6 节断言 + 英文标题否定断言 |
| test_regenerate_project_ai_summary_creates_new_saved_snapshot | Pass | regenerate 新建 + readback 一致 |
| test_project_ai_summary_endpoints_return_404_for_missing_project | Pass | 404 正确返回 |

测试更新要点（第 2 轮）：
- 断言 `## 项目结论` / `## 当前状态` / `## 当前重点` / `## 阶段进展` / `## 风险与阻塞` / `## 下一步建议` 全部存在
- 否定断言 `## Project Conclusion` / `## Current Status` / `## Current Focus` / `## Stage Progress` / `## Next Steps` 均不出现
- 断言 `当前阻塞任务数量：1` 和 `当前待人工处理任务数量：1`

### 4.2 Run AI Summary 回归测试

```
cd runtime/orchestrator
python -m pytest tests/test_run_ai_summaries.py -q
```

**结果：35 passed in 7.03s**

### 4.3 Python 编译检查

```
cd runtime/orchestrator
python -m compileall app
```

**结果：全部通过，无编译错误**

### 4.4 前端构建

```
cd apps/web
npm.cmd run build
```

**结果：499 modules transformed, built in 3.53s，无错误**

### 4.5 Live HTTP Smoke（TestClient）

通过 FastAPI TestClient 执行完整 smoke 流程：

**第 1 轮（commit 79bc634）：**
```
1. GET /projects/{new_id}/ai-summary          → 200, active_summary=None       ✓
2. POST /projects/{id}/ai-summary/generate     → 200, source=rule_fallback      ✓
3. GET /projects/{id}/ai-summary readback      → active_summary.id matches      ✓
4. POST /projects/{id}/ai-summary/regenerate   → 201, new_id != old_id          ✓
5. GET /projects/{id}/ai-summary readback      → active_summary.id = new_id     ✓
```

**第 2 轮复核（commit e8b58ec，含中文 Markdown 验证）：**
```
1. GET /projects/{new_id}/ai-summary          → 200, active_summary=None       ✓
2. POST /projects/{id}/ai-summary/generate     → 200, source=rule_fallback      ✓
   - ## 项目结论 / 当前状态 / 当前重点 / 阶段进展 / 风险与阻塞 / 下一步建议 ✓
   - 无英文标题（Project Conclusion / Current Status / Current Focus / Stage Progress / Next Steps）✓
   - "当前阻塞任务数量" 与 "当前待人工处理任务数量" 存在 ✓
3. GET /projects/{id}/ai-summary readback      → active_summary.id matches      ✓
4. POST /projects/{id}/ai-summary/regenerate   → 201, new_id != old_id          ✓
5. GET /projects/{id}/ai-summary readback      → active_summary.id = new_id     ✓
```

**两轮全部通过。**

---

## 5. 安全边界验证

### 5.1 是否触发真实 provider

**否。** ProjectAISummaryService 全程使用本地规则引擎（model_provider="local_rule_engine"），代码中无 provider_openai / deepseek-v4-pro 调用。

确认文件：`runtime/orchestrator/app/services/project_ai_summary_service.py`
- 无 `import openai` 或无 OpenAI SDK 引用
- `MODEL_PROVIDER = "local_rule_engine"`
- `MODEL_NAME = "project_summary.rule_fallback.v1"`
- `source = RunAISummarySource.RULE_FALLBACK`

### 5.2 是否触发 Worker Pool / planning/apply / apply-local / git-commit

**否。** ProjectAISummaryService 及其路由端点不涉及：
- Worker Pool 调度
- planning/apply 调用
- apply-local 仓库写入
- git-commit 仓库提交

Grep 确认：project_ai_summary_service.py 不含 `worker`, `planning`, `apply_local`, `apply-local`, `git.commit` 关键词。

---

## 6. 风险与限制

| # | 风险 | 说明 | 控制 |
|---|---|---|---|
| 1 | AI 生成模式尚未实现 | 阶段 3 仅实现 rule_fallback，source 始终为 "rule_fallback" | 后续阶段可接入真实 provider，复用现有 API 合同 |
| 2 | ~~摘要内容为英文~~ | **已消除。** Codex 已完成中文 Markdown 返工，当前摘要为中文 6 节结构（含"## 风险与阻塞"） | 复核确认：中文标签、中文内容、中文小节标题全部就绪 |
| 3 | 聚合数据源有限 | 当前仅聚合 project + task_stats + task_tree + stage_guard | deliverable / approval / cost 等数据可后续加入 |
| 4 | 无后台自动刷新 | 摘要需手动触发；数据变更后不自动标记 stale | source_fingerprint 机制已就绪，后续可接入事件触发 |
| 5 | 手动打开卡片才加载 | 卡片展开时才 loadSummary，不是页面打开时 | 设计意图：避免不必要的 GET 请求 |

---

## 7. Gate 结论

### 7.1 Stage 3 项目页 AI 总结 Gate

**Pass**

判定依据：
1. 后端 3 端点全部真实可用（GET / generate / regenerate）
2. 持久化字段完整（source, source_hash, source_version, stale, summary_markdown, generated_at）
3. 前端"项目总结"卡片真实闭环（按钮 → POST → GET readback → Markdown 展示）
4. 来源 badge 正确区分"规则回退"/"AI 生成"
5. stale badge 在 stale=true 时展示
6. 技术字段不在 UI 暴露
7. 无假按钮、无 alert-only / console-only
8. 后端测试 4 项通过 + Run 回归 35 项通过
9. 前端构建成功（499 modules）
10. Live smoke 5 步全部通过
11. 未调用真实 provider（DeepSeek / OpenAI）
12. 未调用 Worker Pool / planning/apply / apply-local / git-commit

### 7.2 AI Project Director Total Closure

**不涉及本次判定。** Total closure 仍为 Partial（CL-16 Evidence Partial）。

---

## 8. 补充说明

- 本次审计未修改任何业务代码
- 仅新增本 evidence 文档（第 1 轮）；第 2 轮仅刷新本 evidence 文档
- CL-16 仍为 Evidence Partial，不在本次审计范围内
- AI Project Director total closure 不在本次阶段 3 范围内

### 8.1 第 2 轮复核变更摘要（commit e8b58ec）

Codex 完成中文 Markdown 返工后，本 evidence 文档刷新内容：
- 修正"摘要内容为英文"为已消除
- 补录中文 6 节小节清单（含新增的"## 风险与阻塞"）
- 确认无英文标题残留
- 补录"风险与阻塞"小节内容核验（阻塞任务数、待人工处理数、阶段阻塞原因）
- 测试断言已更新为中文标题验证 + 英文标题否定断言
