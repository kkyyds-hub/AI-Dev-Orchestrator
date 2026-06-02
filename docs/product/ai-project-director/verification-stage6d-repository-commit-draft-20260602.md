# Stage 6-D1：仓库工作区 commit_draft 可达性验证

> 文档类型：evidence / 事实验证
> 生成日期：2026-06-02
> 执行模型：DeepSeek（Claude Code CLI）
> 状态：完成
> Codex 已执行 Stage 6-D1 commit_draft 可达性修复 + 人工确认门控，本阶段为事实验证。

---

## 1. 基准 commit

| 项目 | 值 |
|---|---|
| origin/main HEAD | `0efb7fdeed5a3f29b9a6ed7856daff76e416cbd4` |
| 提交信息 | `fix(web): make repository commit draft step reachable` |
| 验证时间 | 2026-06-02 |

---

## 2. 验证范围

聚焦 Stage 6-D1 对 `ExecutionRepositoryTab.tsx` 的修复：
- `commit_draft` 步骤是否从不可达变为可达
- `release_judge` 步骤是否仍可通过人工确认到达
- `commitDraftAcknowledged` 状态重置逻辑
- 新增 data-testid
- 确认 6-C1 迁移成果未被回退

覆盖文件：
- `ExecutionRepositoryTab.tsx`（主要改动）
- `RepositoryPreflightPanel.tsx`（确认未改动）
- `RepositoryReleaseGatePanel.tsx`（确认未改动）
- `repositories/hooks.ts`（确认未改动）
- `repositories/types.ts`（确认未改动）

---

## 3. commit_draft 可达性验证

### 3.1 修复核心逻辑

**代码位置**：`ExecutionRepositoryTab.tsx:42-70`

6-C1 逻辑（修复前）：
```typescript
if (hasPreflight) {
  if (candidates.length > 0) return 8; // release_judge — 跳过 commit_draft
  return 6; // preflight
}
```

6-D1 逻辑（修复后）：
```typescript
if (hasPreflight) {
  if (candidates.length > 0) {
    return commitDraftAcknowledged ? 8 : 7; // commit_draft → release_judge
  }
  return 6; // preflight
}
```

| # | 验证项 | 代码位置 | 验证结果 |
|---|---|---|---|
| 1 | `candidateSignature` 派生 | `:42-45`，`candidates.map(c => c.id).sort().join("\|")` | **已新增** |
| 2 | `commitDraftAcknowledged` 状态初始化 `false` | `:46`，`useState(false)` | **已新增** |
| 3 | `selectedProjectId` 变化时重置 | `:48-50`，`useEffect` 依赖 `selectedProjectId` | **Pass** |
| 4 | `candidateSignature` 变化时重置 | `:48-50`，`useEffect` 依赖 `candidateSignature` | **Pass** |
| 5 | `activeStepIndex` 包含 `commitDraftAcknowledged` 依赖 | `:70`，useMemo 依赖数组 | **Pass** |
| 6 | 有 preflight + candidates + 未确认 → `commit_draft`（step 7） | `:62`，`commitDraftAcknowledged ? 8 : 7` | **Pass** |
| 7 | 有 preflight + candidates + 已确认 → `release_judge`（step 8） | `:62`，确认后返回 8 | **Pass** |
| 8 | 有 preflight + 无 candidates → `preflight`（step 6） | `:64`，逻辑不变 | **Pass** |

### 3.2 commit_draft 阶段 UI 面板

**代码位置**：`ExecutionRepositoryTab.tsx:177-196`

| # | 验证项 | 代码位置 | 验证结果 |
|---|---|---|---|
| 1 | `activeStep === "commit_draft"` 条件渲染 | `:177` | **Pass** |
| 2 | `data-testid="execution-repository-commit-draft-panel"` | `:180` | **Pass** |
| 3 | 提交草案确认标题："提交草案确认" | `:182` | **Pass** |
| 4 | 草案数量展示：`{candidates.length} 个提交草案` | `:184` | **Pass** |
| 5 | 明确提示：不是 git commit | `:184-185` | **Pass** |
| 6 | 明确提示：不会执行 git push | `:185` | **Pass** |
| 7 | 明确提示：仅记录候选版本与证据 | `:184` | **Pass** |
| 8 | "查看放行判断" 按钮 | `:188-194` | **Pass** |
| 9 | 按钮 `onClick` 调用 `setCommitDraftAcknowledged(true)` | `:189` | **Pass** |
| 10 | `data-testid="execution-repository-open-release-judge"` | `:191` | **Pass** |
| 11 | `CurrentStepPanel` 在 commit_draft 阶段显示"提交草案阶段"文案 | `:324-328`（`getStepMessage`） | **Pass** |

---

## 4. release_judge 可达性验证

| # | 验证项 | 代码位置 | 验证结果 |
|---|---|---|---|
| 1 | 点击"查看放行判断"后 `commitDraftAcknowledged = true` | `:189` | **Pass** |
| 2 | `activeStepIndex` 重新计算，返回 8（release_judge） | `:62`，`return commitDraftAcknowledged ? 8 : 7` | **Pass** |
| 3 | `activeStep === "release_judge"` 条件渲染 ReleaseGatePanel | `:198-205` | **Pass** |
| 4 | 切换项目后 `commitDraftAcknowledged` 重置为 `false` | `:48-50`，`useEffect` 依赖 `selectedProjectId` | **Pass** |
| 5 | 候选草案列表变化后重置 | `:48-50`，`useEffect` 依赖 `candidateSignature` | **Pass** |

**完整可达路径**：

```
hasProject && snapshot && session && batches && hasPreflight && candidates.length > 0
  → activeStepIndex = 7 (commit_draft)
  → 用户看到提交草案确认面板 + "查看放行判断" 按钮
  → 用户点击"查看放行判断"
  → commitDraftAcknowledged = true
  → activeStepIndex 重新计算 = 8 (release_judge)
  → ReleaseGatePanel 渲染
```

---

## 5. 6-C1 迁移成果完整性验证

确认 6-C1 的以下成果未被 6-D1 回退或破坏：

| # | 6-C1 成果 | 当前状态（6-D1） | 验证结果 |
|---|---|---|---|
| 1 | `RepositoryPreflightPanel` import | `ExecutionRepositoryTab.tsx:4` | **保留** |
| 2 | `RepositoryReleaseGatePanel` import | `ExecutionRepositoryTab.tsx:5` | **保留** |
| 3 | `activeStep === "preflight"` 渲染 PreflightPanel | `:168-175` | **保留** |
| 4 | `activeStep === "release_judge"` 渲染 ReleaseGatePanel | `:198-205` | **保留** |
| 5 | `execution-repository-tab` | `:96` | **保留** |
| 6 | `execution-repository-preflight-panel` | `:169` | **保留** |
| 7 | `execution-repository-release-gate-panel` | `:199` | **保留** |
| 8 | ApprovalInboxPage 无 preflight/release-gate 子页签 | 未改动 | **保留** |

---

## 6. data-testid 验证表

| # | data-testid | 类型 | 文件:行号 | 状态 |
|---|---|---|---|---|
| 1 | `execution-repository-tab` | 保留（6-C1） | `ExecutionRepositoryTab.tsx:96` | **Pass** |
| 2 | `execution-repository-preflight-panel` | 保留（6-C1） | `ExecutionRepositoryTab.tsx:169` | **Pass** |
| 3 | `execution-repository-release-gate-panel` | 保留（6-C1） | `ExecutionRepositoryTab.tsx:199` | **Pass** |
| 4 | `execution-repository-commit-draft-panel` | **新增（6-D1）** | `ExecutionRepositoryTab.tsx:180` | **Pass** |
| 5 | `execution-repository-open-release-judge` | **新增（6-D1）** | `ExecutionRepositoryTab.tsx:191` | **Pass** |

---

## 7. 未改动项确认

| # | 区域 | 确认方式 | 结论 |
|---|---|---|---|
| 1 | 后端 API 路径 | 无后端文件变更 | **未改动** |
| 2 | 数据库 | 无 schema 变更 | **未改动** |
| 3 | Worker | 无 worker 文件变更 | **未改动** |
| 4 | 成果中心 (`DeliveryCenterPage.tsx`) | 无变更 | **未改动** |
| 5 | 审批页 (`ApprovalInboxPage.tsx`) | 无变更 | **未改动** |
| 6 | `RepositoryPreflightPanel.tsx` | 内容与 6-C1 完全一致（376 行） | **未改动** |
| 7 | `RepositoryReleaseGatePanel.tsx` | 内容与 6-C1 完全一致（397 行） | **未改动** |
| 8 | `repositories/hooks.ts` | 19 个 hooks 定义不变 | **未改动** |
| 9 | `repositories/types.ts` | 全部类型定义不变 | **未改动** |
| 10 | `ExecutionCenterPage.tsx` | 三页签结构不变 | **未改动** |

---

## 8. 测试命令与结果

```bash
cd apps/web && npm.cmd run build
```

**结果**：`tsc -b && vite build` 成功，built in 3.52s，496 modules transformed，无 TypeScript 错误。

```bash
cd runtime/orchestrator && python -m compileall app tests
```

**结果**：全部编译通过，无语法错误。

---

## 9. Warnings

无新增 warning。Stage 6-C1 的三条 warning 中，Warning 2（commit_draft 无可达路径）已在 6-D1 中修复并关闭。

Stage 6-C1 Warning 状态：
- Warning 1（轻提示文案未单独落地）：仍开放，后续仓库工作区精修时处理。
- Warning 2（commit_draft 无可达路径）：**已关闭**，6-D1 修复。
- Warning 3（后端 API 仍挂 `/approvals`）：仍开放，Deferred。

---

## 10. Gate 结论

### 10.1 Stage 6-D1 frontend code-level: **Pass**

6-C1 审计中记录的 "commit_draft 步骤无路径可达" 问题已通过新增 `commitDraftAcknowledged` 状态门控修复：
- 有 preflight + candidates 时，初始步骤为 commit_draft（step 7），不再直接跳到 release_judge
- commit_draft 面板明确提示三条边界（不是 git commit / 不会 git push / 仅记录候选版本与证据）
- 用户点击"查看放行判断"后进入 release_judge
- `candidateSignature` / `selectedProjectId` 变化时重置确认状态
- TypeScript + Vite build 通过（3.52s）

### 10.2 Stage 6-D evidence-level: **Pass**

所有验证项均有明确的代码行号事实可追溯，前端 build + 后端 compileall 双通过，2 个新增 data-testid 可定位，6-C1 迁移成果全部保留。

### 10.3 Stage 6-C: **保持 Pass**（不降级）

6-C1 迁移成果完整保留，6-D1 仅在 ExecutionRepositoryTab 上增量修改，未破坏预检/发布门禁挂载。

### 10.4 AI Project Director total closure: **Partial**（不变）

不满足总闭环条件（SKILL.md 第 8.5 节）。

### 10.5 CL-16: **不涉及**

---

## 11. 审查清单

- [x] origin/main commit 已核对：`0efb7fdeed5a3f29b9a6ed7856daff76e416cbd4`（6-D1）
- [x] `candidateSignature` 派生逻辑已验证
- [x] `commitDraftAcknowledged` 状态 + 重置 useEffect 已验证
- [x] `activeStepIndex` 三态分支（commit_draft / release_judge / preflight）已验证
- [x] commit_draft UI 面板已验证（11 项）
- [x] release_judge 可达性路径已验证
- [x] 6-C1 迁移成果完整保留
- [x] 5 个 data-testid（3 保留 + 2 新增）全部验证
- [x] 未改动区域全部确认（10 项）
- [x] `tsc -b && vite build` 通过（3.52s）
- [x] `python -m compileall app tests` 通过
- [x] 未改任何业务代码（仅验证）
- [x] 未改前端/后端/数据库/Worker
- [x] AI Project Director total closure 仍为 Partial
- [x] CL-16 不涉及，未写 Pass
