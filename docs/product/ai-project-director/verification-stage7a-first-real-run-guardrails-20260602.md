# Stage 7-A1：首次真实运行前安全护栏验证

> 文档类型：evidence / 事实验证
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 基准 commit：`f863b52adb714040feb3071f843549dde809d0be`
> 状态：完成
> Codex 已执行 Stage 7-A1 安全护栏（Provider 状态标签 + run-once 禁用条件 + 安全声明 + 二次确认），本阶段为事实验证。

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `f863b52adb714040feb3071f843549dde809d0be` |
| 提交信息 | `fix(web): clarify provider readiness badge wording` |
| 验证时间 | 2026-06-02 |

---

## 2. 验证范围

仅验证 `DirectorChatEntry.tsx` 的新增安全护栏。不改后端、不改 Worker、不改 Provider 配置逻辑。

覆盖：
- Provider 状态读取与展示
- `canRunWorkerOnce` 安全条件
- 二次确认 (`window.confirm`)
- 页面安全声明
- data-testid
- 构建验证

---

## 3. Provider Readiness Badge 验证

**读取方式**：`useQuery` → `fetchOpenAIProviderSettings()` → `requestJson("/provider-settings/openai")`（`:117-120, :41-43`）。

**状态决议**：`resolveProviderStatus()`（`:45-79`）。

| # | Provider 状态 | 预期 label | 预期 tone | 代码位置 | 状态 |
|---|---|---|---|---|---|
| 1 | `query.isLoading` | "检查 Provider 配置中" | `info` | `:50-56` | **Pass** |
| 2 | `query.isError` | "Provider 状态未知" | `danger` | `:58-64` | **Pass** |
| 3 | `query.data?.configured === true` | "Provider 已配置" | `success` | `:66-72` | **Pass** |
| 4 | 未配置 | "未配置 Provider" | `warning` | `:74-78` | **Pass** |

**注意**：label 为 `"Provider 已配置"` 而非 `"真实执行"`。这是正确的——`WORKER_SIMULATE_EXECUTION_OVERRIDE` 状态未通过 API 暴露，前端无法区分"configured + simulate override"和"configured + real"。"Provider 已配置"准确描述了可读取的客观事实。

---

## 4. canRunWorkerOnce 安全条件验证

**代码位置**：`DirectorChatEntry.tsx:168-173`

```typescript
const canRunWorkerOnce =
  Boolean(taskCreation?.project_id) &&
  providerConfigured &&
  !providerSettingsQuery.isLoading &&
  !providerSettingsQuery.isError &&
  !runWorkerOnceMutation.isPending;
```

| # | 条件 | 作用 | 不满足时按钮行为 | 状态 |
|---|---|---|---|---|
| 1 | `Boolean(taskCreation?.project_id)` | 必须有已创建的正式项目 | `disabled`（灰色，不可点击） | **Pass** |
| 2 | `providerConfigured` | Provider 必须已配置（`configured === true`） | `disabled` | **Pass** |
| 3 | `!providerSettingsQuery.isLoading` | Provider 状态查询未完成 | `disabled` | **Pass** |
| 4 | `!providerSettingsQuery.isError` | Provider 状态查询未失败 | `disabled` | **Pass** |
| 5 | `!runWorkerOnceMutation.isPending` | 没有正在进行的 run-once 请求 | `disabled` | **Pass** |

**结论**：按钮在 provider 未配置、loading、error、已有任务运行、或无正式项目时均禁用。所有 5 个条件必须同时满足。

---

## 5. 运行前二次确认验证

### 5.1 window.confirm 调用

**代码位置**：`DirectorChatEntry.tsx:372-383`

```typescript
const handleRunWorkerOnce = async () => {
  if (!taskCreation?.project_id || !canRunWorkerOnce) {
    return;
  }

  const confirmed = window.confirm(
    "即将启动一次执行：Provider 已配置，启动后可能调用真实 AI provider 并产生费用。" +
    "本次仅产生 Run / 日志 / 摘要 / 交付物 / 审批，不会执行 git commit / git push / apply-local。" +
    "是否继续？",
  );

  if (!confirmed) {
    return;
  }

  try {
    await runWorkerOnceMutation.mutateAsync(taskCreation.project_id);
  } catch { ... }
};
```

| # | 验证项 | 代码位置 | 状态 |
|---|---|---|---|
| 1 | 点击按钮前检查 `canRunWorkerOnce` | `:373` | **Pass** |
| 2 | 调用 `window.confirm(...)` | `:377-379` | **Pass** |
| 3 | 用户取消 → 提前 return，不调用 run-once | `:381-383` | **Pass** |
| 4 | 用户确认 → 调用 `runWorkerOnceMutation.mutateAsync` | `:386` | **Pass** |

### 5.2 Confirm 文案内容

| # | 必需内容 | 确认文案中的对应文字 | 状态 |
|---|---|---|---|
| 1 | 可能调用真实 AI provider | "启动后可能调用真实 AI provider" | **Pass** |
| 2 | 可能产生费用 | "并产生费用" | **Pass** |
| 3 | 不会 git commit | "不会执行 git commit" | **Pass** |
| 4 | 不会 git push | "git push" | **Pass** |
| 5 | 不会 apply-local | "apply-local" | **Pass** |
| 6 | 仅产生 Run / 日志 / 摘要 / 交付物 / 审批 | "本次仅产生 Run / 日志 / 摘要 / 交付物 / 审批" | **Pass** |
| 7 | 是否继续？ | "是否继续？" | **Pass** |

---

## 6. 页面安全声明验证

### 6.1 运行前确认文案（`:678-680`）

```tsx
<p data-testid="director-chat-real-run-confirmation-copy">
  运行前确认：点击"启动一次执行"后会再次确认；Provider 已配置时，启动后可能调用真实 AI provider 并产生费用。
</p>
```

### 6.2 预算提示（`:682-686`，仅 provider 已配置时显示）

```tsx
<p data-testid="director-chat-real-run-budget-copy">
  每日预算：{formatNullableCurrencyUsd(budgetHealth?.daily_budget_usd ?? null)}
  ，会话预算：{formatNullableCurrencyUsd(budgetHealth?.session_budget_usd ?? null)}
  ；本次可能产生费用。
</p>
```

### 6.3 安全声明（`:688-690`）

```tsx
<p data-testid="director-chat-real-run-safety-copy">
  安全声明：本次仅产生 Run / 日志 / 摘要 / 交付物 / 审批，不会执行 git commit / git push / apply-local。
</p>
```

| # | 验证项 | 结果 |
|---|---|---|
| 1 | 运行前确认声明存在，说明会二次确认 | **Pass** |
| 2 | 安全声明明确"不会 git commit / git push / apply-local" | **Pass** |
| 3 | 安全声明明确"仅产生 Run / 日志 / 摘要 / 交付物 / 审批" | **Pass** |
| 4 | 预算提示仅在 provider 已配置时显示 | **Pass**（`:682` `providerConfigured` 条件） |
| 5 | 三块声明用 amber-500 色调边框包裹 | **Pass**（`:677` `border-amber-500/30 bg-amber-500/10`） |

---

## 7. data-testid 验证表

| # | data-testid | 预期位置 | 实际文件:行号 | 状态 |
|---|---|---|---|---|
| 1 | `director-chat-provider-status` | Provider 状态 badge 容器 | `DirectorChatEntry.tsx:645` | **Pass** |
| 2 | `director-chat-run-worker-once` | "启动一次执行" 按钮 | `DirectorChatEntry.tsx:654` | **Pass** |
| 3 | `director-chat-real-run-confirmation-copy` | 运行前确认文案 | `DirectorChatEntry.tsx:678` | **Pass** |
| 4 | `director-chat-real-run-budget-copy` | 预算提示文案 | `DirectorChatEntry.tsx:682` | **Pass** |
| 5 | `director-chat-real-run-safety-copy` | 安全声明文案 | `DirectorChatEntry.tsx:688` | **Pass** |

---

## 8. 未改动项确认

| # | 区域 | 确认方式 | 结论 |
|---|---|---|---|
| 1 | 后端 `/provider-settings/openai` | `provider_settings.py` 无变更 | **未改动** |
| 2 | Worker (`task_worker.py`) | 无变更 | **未改动** |
| 3 | Provider 配置后端逻辑 (`provider_config_service.py`) | 无变更 | **未改动** |
| 4 | API 路径 | 无新增/修改路由 | **未改动** |
| 5 | 数据库 | 无 schema 变更 | **未改动** |
| 6 | 真实 provider 调用逻辑 (`executor_service.py`) | 无变更 | **未改动** |
| 7 | `http.ts` | 标准 `requestJson`，无修改 | **未改动** |
| 8 | `SettingsPage.tsx` | 无变更 | **未改动** |

---

## 9. 构建验证

```bash
cd apps/web && npm.cmd run build
```

**结果**：`tsc -b && vite build` 成功，498 modules transformed，built in 4.56s，无 TypeScript 错误。

---

## 10. Warnings

### Warning 1: WORKER_SIMULATE_EXECUTION_OVERRIDE 状态未通过 API 暴露

前端 `providerConfigured` 仅反映 Provider 是否已配置 API Key，不反映 `WORKER_SIMULATE_EXECUTION_OVERRIDE` 环境变量状态。如果用户通过环境变量设置了 `WORKER_SIMULATE_EXECUTION_OVERRIDE=true`，前端标签仍显示 "Provider 已配置"（success），不会提示"当前为 simulate 模式"。

**影响**：低。用户本人亲自运行时会设置自己的环境变量，且 Run 详情页（`RunUserSummaryCard`）会在运行后展示 `executionModeLabel`（"模拟模型执行（不可作为真实交付依据）"）。建议后续 Stage 在 `/provider-settings/openai` 响应中增加 `simulate_override` 布尔字段。

### Warning 2: confirm 对话框的移动端体验

`window.confirm()` 是浏览器原生弹窗，在移动端/webview 中体验不一致。当前不构成 blocker——真实运行首次由用户在桌面环境执行。

---

## 11. Gate 结论

### 11.1 Stage 7-A1 frontend code-level: **Pass**

全部 5 组验证通过：
- Provider 状态标签：4 种状态（loading/error/configured/unconfigured）均有正确 label 和 tone
- `canRunWorkerOnce`：5 个条件全部到位，未配置/loading/error 时按钮正确禁用
- `window.confirm`：二次确认文案含 7 项必需内容，取消时正确阻断 run-once
- 安全声明：3 块文案（确认/预算/安全）全部存在，使用 amber-500 色调
- 5 个 data-testid 全部可定位

### 11.2 Stage 7-A evidence-level: **Pass**

所有验证项均有明确代码行号可追溯，TypeScript + Vite build 通过（4.56s），未改动区域全部确认。

### 11.3 First real run readiness: **Ready for user manual validation**

P0 安全护栏已到位：
- Provider 状态在按钮旁可见
- 未配置/loading/error 时按钮禁用
- 点击"启动一次执行"前有 `window.confirm` 二次确认
- 确认文案含"可能调用真实 AI provider、可能产生费用、不会 git commit/push/apply-local"
- 页面常驻安全声明 + 预算提示

用户现在可以安全地手动进行首次真实 Provider/Worker 运行验收。建议流程：
1. 打开设置页 → 配置 DeepSeek/OpenAI API Key + Base URL → 保存
2. 点击"测试连接"确认 auth_valid + model_usable
3. 回到工作台 → 确认 Provider 标签显示 "Provider 已配置"（success）
4. 确认项目已创建、任务队列已就绪
5. 点击"启动一次执行" → 阅读 `window.confirm` 文案 → 确认
6. 查看运行结果 → Run / 日志 / 摘要 / 交付物 / 审批

### 11.4 AI Project Director total closure: **Partial**（不变）

GAP-01（真实 Provider 运行态证据）和 GAP-05（成本台账）的解除必须等用户真实运行后。

### 11.5 CL-16: **不涉及**

---

## 12. 审查清单

- [x] origin/main commit 已核对：`f863b52adb714040feb3071f843549dde809d0be`（7-A1）
- [x] `DirectorChatEntry.tsx` 全文已审计（948 行）
- [x] `fetchOpenAIProviderSettings` 调用 `/provider-settings/openai` 已验证
- [x] Provider 状态 badge 4 种状态已验证（label + tone）
- [x] `canRunWorkerOnce` 5 个条件已验证
- [x] `window.confirm` 二次确认 + 取消阻断已验证
- [x] Confirm 文案 7 项必需内容已验证
- [x] 页面安全声明 3 块文案（确认/预算/安全）已验证
- [x] `director-chat-real-run-budget-copy` 仅在 provider 已配置时显示验证
- [x] 5 个 data-testid 全部可定位
- [x] `http.ts` 确认无修改
- [x] 未改后端/Worker/Provider 配置逻辑/API 路径/数据库
- [x] `tsc -b && vite build` 通过（4.56s，498 modules）
- [x] Warnings 已记录（2 条）
- [x] 未改任何业务代码（仅验证）
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass
