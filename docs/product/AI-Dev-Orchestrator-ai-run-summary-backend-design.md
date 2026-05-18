# AI-Dev-Orchestrator AI 运行摘要后端设计

> 建议仓库路径：`docs/product/AI-Dev-Orchestrator-ai-run-summary-backend-design.md`
> 设计版本：V1.0
> 当前阶段：阶段 2B-R5（运行摘要正文技术噪音收口）
> 后续真实 AI 调用：阶段 2C

---

## 1. 背景

AI-Dev-Orchestrator 前端已完成阶段 1（运行页规则摘要 + 技术日志弹窗）。当前后端已具备 AI 运行摘要的存储和规则回退生成能力，但在以下方面存在契约缺口：

- 缺少单数当前摘要接口（前端 2B 默认接入需要）
- 缺少 `created_at` / `updated_at` / `error_summary` 字段
- Repository 缺少正式状态流方法（pending → succeeded / failed）
- Markdown 标题与前端设计要求不完全对齐

阶段 2A-R2 仅补齐以上契约漏项，不真实调用 AI，不接前端 UI。

---

## 2. 存储设计

### 2.1 AI 摘要独立存储

AI 摘要存储在 `run_ai_summaries` 表中，与 `runs.result_summary` **完全独立**：

- `runs.result_summary` — 运行执行器生成的后端拼接日志文本（英文 provider 摘要），保持原有含义不变
- `run_ai_summaries.summary_markdown` — AI 或规则引擎生成的中文 Markdown 摘要

**AI 摘要绝不覆盖 `runs.result_summary`。**

### 2.2 表结构

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `run_id` | UUID FK→runs.id | 所属运行 |
| `project_id` | UUID? | 所属项目 |
| `task_id` | UUID? | 所属任务 |
| `deliverable_id` | UUID? | 关联交付件（当前未使用） |
| `summary_type` | Enum | 摘要类型（当前仅使用 RUN） |
| `status` | Enum | pending / succeeded / failed |
| `source` | Enum | ai / rule_fallback |
| `summary_markdown` | Text | 中文 Markdown 摘要正文 |
| `source_version` | String(40) | 摘要生成逻辑版本 |
| `source_fingerprint` | String(128) | 运行数据指纹（SHA-256） |
| `source_hash` | String(128) | 同 source_fingerprint（兼容） |
| `model_provider` | String(100)? | 生成摘要的模型服务 |
| `model_name` | String(100)? | 生成摘要的模型名称 |
| `prompt_hash` | String(128) | 提示词 SHA-256 |
| `provider_receipt_id` | String(100)? | 模型回执 ID |
| `generated_at` | DateTime(tz) | 摘要生成时间 |
| `created_at` | DateTime(tz) | 记录创建时间 |
| `updated_at` | DateTime(tz) | 最后更新时间 |
| `error_summary` | Text? | 失败原因（仅 status=failed） |
| `stale` | Boolean | 是否已被新摘要取代 |

---

## 3. API 设计

### 3.1 单数当前摘要接口（阶段 2B 前端默认接入）

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/runs/{run_id}/ai-summary` | 获取当前 active summary；无摘要时返回 `active_summary: null` |
| `POST` | `/runs/{run_id}/ai-summary/generate` | 生成或复用当前 active summary |
| `POST` | `/runs/{run_id}/ai-summary/regenerate` | 强制重新生成，标记旧摘要 stale |

**GET 响应格式（`RunAISummaryCurrentResponse`）**：
```json
{
  "run_id": "uuid",
  "active_summary": { ... } | null
}
```

### 3.2 复数历史接口（调试/查询历史）

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/runs/{run_id}/ai-summaries` | 获取全部历史摘要 + active summary |
| `POST` | `/runs/{run_id}/ai-summaries` | 生成或复用摘要（与单数 generate 同逻辑） |
| `POST` | `/runs/{run_id}/ai-summaries/regenerate` | 强制重新生成 |

### 3.3 单数与复数接口的关系

- **单数接口**是后续前端 2B 的主入口。语义更清晰（当前摘要 vs 历史列表）。
- **复数接口**保留作为调试/历史查询用途，逻辑与单数接口共享同一个 Service。
- 两套接口调用相同的 `RunAISummaryService` 方法，行为一致。

---

## 4. 状态流设计

### 4.1 摘要生命周期

```
[开始] → PENDING → SUCCEEDED (规则回退或 AI 成功)
                  → FAILED (AI 调用失败，记录 error_summary)

Source 数据变化 → 旧 active 标记 stale → 生成新 SUCCEEDED/FAILED 摘要
用户主动 regenerate → 旧 active 标记 stale → 生成新摘要
```

### 4.2 source=rule_fallback 与 source=ai 的区别

| 属性 | rule_fallback | ai |
|---|---|---|
| 生成方式 | 本地规则引擎（不调用外部模型） | DeepSeek/OpenAI 等外部模型 |
| model_provider | `local_rule_engine` | 实际 provider key |
| model_name | `run_summary.rule_fallback.v2` | 实际 model name |
| prompt_hash | 规则引擎的 prompt 文本哈希 | 真实发送的 prompt 哈希 |
| provider_receipt_id | `null` | 模型回执 ID |
| 当前阶段 | 阶段 2A 已实现 | 阶段 2C 实现 |

### 4.3 error_summary 的用途

- `status=succeeded` 时：`error_summary=null`
- `status=failed` 时：`error_summary` 保存失败原因，例如：
  - `"DeepSeek API timeout after 120s"`
  - `"Provider returned HTTP 429 rate limit"`
  - `"Response JSON parse error"`
- `status=pending` 时：`error_summary=null`（尚未完成，无错误信息）

### 4.4 source_fingerprint / prompt_hash 的作用

- `source_fingerprint`：对运行数据的 SHA-256 指纹。当运行数据（status, result_summary, verification_summary 等）变化时，指纹也会变化。用于判断是否需要重新生成摘要。
- `prompt_hash`：对生成提示词的 SHA-256 哈希。当提示词模板版本或运行数据变化时，prompt_hash 变化。用于判断摘要是否基于最新提示词模板生成。

---

## 5. Repository 状态流方法

| 方法 | 签名 | 说明 |
|---|---|---|
| `get_active_by_run_id` | `(run_id) -> RunAISummary \| None` | 获取当前 active RUN 摘要 |
| `upsert_pending` | `(summary) -> RunAISummary` | 插入新 pending 记录（旧 active 标记 stale） |
| `mark_succeeded` | `(summary_id, markdown, fingerprint?, prompt_hash?) -> RunAISummary \| None` | 标记为成功并写入最终内容 |
| `mark_failed` | `(summary_id, error_summary) -> RunAISummary \| None` | 标记为失败并写入错误原因 |
| `mark_stale_if_source_changed` | `(run_id, current_fingerprint) -> list[RunAISummary]` | 当指纹变化时标记旧摘要 stale |

---

## 6. Markdown 输出格式

### 6.1 固定 5 个标题

```markdown
## 运行结论
## 已完成内容
## 风险与注意事项
## 下一步建议
## 技术依据
```

### 6.2 技术依据内容

"技术依据"段落必须列出摘要生成所依据的源数据，字段缺失时写"未记录"：

```markdown
## 技术依据
- 运行状态：succeeded
- 结果摘要：（run.result_summary 或 "未记录"）
- 验证摘要：（run.verification_summary 或 "未记录"）
- 质量检查：通过 / 拦截 / 未记录
- 模型服务 Key：deepseek（run.provider_key 或 "未记录"）
- 模型名称：deepseek-v4-pro（run.model_name 或 "未记录"）
- 模型回执 ID：receipt-xxx（run.provider_receipt_id 或 "未记录"）
```

不允许编造交付件或审批结果。

---

## 7. 阶段规划

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 1 | 前端规则摘要 + 技术日志弹窗 | 已完成 |
| 阶段 2A-R1 | 后端 AI 摘要存储 + 规则回退生成骨架 | 已完成 |
| 阶段 2A-R2 | 单数接口 + 字段补齐 + Repository 状态流 + Markdown 收口 | 已完成 |
| 阶段 2A-R3 | 历史数据迁移与接口硬化 | 已完成 |
| 阶段 2B | 前端接入单数摘要接口 | 已完成 |
| 阶段 2B-R1 | 单主卡片替代双摘要卡 | 已完成 |
| 阶段 2B-R2 | 提示去重与接口诊断收口 | 已完成 |
| 阶段 2B-R3 | 运行摘要来源文案收口 | 已完成 |
| 阶段 2B-R4 | 文档哈希修正 + 提示去重 + 废弃组件清理 | 已完成 |
| 阶段 2B-R5 | 运行摘要正文技术噪音收口 | 已完成 |
| 阶段 2C-A | 真实 AI 摘要后端最小闭环 | 已完成 |
| 阶段 2C-A-R1 | Provider/env/prompt_hash/provider_key 硬化 | 已完成 |
| 阶段 2C-B | 前端真实 AI 状态验收与运行时联调 | 未开始 |
| 阶段 2C | 真实 DeepSeek AI 摘要生成 | 未开始 |

> **阶段 2B-R3 实施记录** `[2026-05-18]`
>
> 任务：运行摘要来源文案收口 + 文档回填
>
> 提交哈希：`2f35394`（完整：`2f35394d84375df298f49924d31d74e805c3f924`）
>
> Build 结果：通过（tsc + vite build）
>
> 当前状态：
> - 阶段 2A/2B 当前完成的是"可保存摘要接口 + 前端展示"
> - 当前 source=rule_fallback，不真实调用 DeepSeek/OpenAI
> - source=ai 仅为后续阶段预留，真实 AI 摘要生成仍未接入
> - 阶段 2C 才允许接真实模型生成摘要
> - 前端文案已调整：主卡片标题"运行摘要"，按钮"生成运行摘要"/"重新生成摘要"，状态条"摘要来源：规则回退 · 尚未调用真实 AI"
> - 不再出现"AI 摘要已保存""生成 AI 摘要""AI 摘要生成失败"等误导文案
> - 不修改后端、不调用 AI、不进入阶段 2C
>
> **阶段 2B-R5 实施记录** `[2026-05-18]`
>
> 任务：运行摘要正文技术噪音收口
>
> 提交哈希：`ba8b005`（完整：`ba8b005c8d434739faa5df40649be99f5451f360`）
>
> Build / 测试结果：后端 16 测试通过，前端 build 通过
>
> 修改范围：
> - `runtime/orchestrator/app/services/run_ai_summary_service.py` — `_build_summary_markdown()` 移除完整 source_fingerprint / prompt_hash
>
> 已完成：
> - 默认摘要正文不再展示完整 source_fingerprint / prompt_hash
> - 技术依据章节改为用户化说明："摘要依据：运行状态、结果摘要、验证摘要、质量检查、模型服务记录"
> - 调试指纹指向状态条或技术日志
> - Markdown 五标题结构不变
> - 当前仍为 rule_fallback，不真实调用 AI
> - source=ai 仍为后续阶段预留
>
> **阶段 2C-A 实施记录** `[2026-05-18]`
>
> 任务：真实 AI 运行摘要后端最小闭环
>
> 提交哈希：`bdfd6ed`（完整：`bdfd6edde8f1ba591e57724d25e7c71887ca14a4`）
>
> Build / 测试结果：后端 28 测试通过，前端 build 通过
>
> 修改范围：
> - `runtime/orchestrator/app/services/openai_provider_executor_service.py` — 新增 generate_text() 纯文本生成
> - `runtime/orchestrator/app/services/run_ai_summary_service.py` — AI 优先 + rule_fallback + Markdown 校验
> - `runtime/orchestrator/app/api/routes/runs.py` — DI 注入 ProviderConfigService
> - `runtime/orchestrator/tests/test_run_ai_summaries.py` — 新增 12 个测试
>
> 已完成：
> - Provider 配置存在时优先尝试真实 AI 生成
> - AI 成功时 source=ai，含 model_provider / model_name / provider_receipt_id
> - AI 失败/超时/格式不合格/未配置时 source=rule_fallback
> - GET /ai-summary 不触发 AI
> - 前端无需改动，现有 source 展示可区分 AI / 规则回退
> - 不改 worker/provider 主执行流程
>
> **阶段 2C-A-R1 实施记录** `[2026-05-18]`
>
> 任务：真实 AI 运行摘要后端硬化返工
>
> 提交哈希：`915f0a9`
>
> Build / 测试结果：后端 35 测试通过，前端 build 通过
>
> 已完成：
> - ProviderConfigService 始终注入，env-only api_key 也能触发 AI
> - source=ai 的 prompt_hash 来自实际 AI prompt
> - source=rule_fallback 的 prompt_hash 保持稳定
> - generate_text 传递正确的 provider_key
> - 前端 UI 仍无需改动

### 7.1 当前阶段不做的

- 不真实调用 DeepSeek / OpenAI
- 不改 worker
- 不改 provider 执行主流程
- 不改 deliverable / approval / release gate / apply-local / git write
- 不改前端 UI
- 不改 runs.result_summary 含义

---

## 8. 验收标准

| 验收项 | 标准 |
|---|---|
| GET /{run_id}/ai-summary 无摘要 | 返回 200，active_summary=null |
| POST /{run_id}/ai-summary/generate | 返回 200，创建 rule_fallback 摘要 |
| POST /{run_id}/ai-summary/generate 重复调用 | 复用同一 active summary |
| POST /{run_id}/ai-summary/regenerate | 返回 201，旧摘要 stale，新摘要 active |
| DTO 含 created_at/updated_at/error_summary | 三个字段均在响应中 |
| Markdown 标题 | 仅含 5 个指定标题，不含旧标题 |
| 技术依据 | 含 run 元数据，缺失字段写"未记录" |
| mark_failed | error_summary 正确持久化 |
| 404 | 不存在的 run_id 返回 404 |
| 不覆盖 runs.result_summary | 不修改 runs 表 |
