# P9-REL-H 人工 readback 验证指引与证据

> **文档类型**: manual validation guide / evidence ledger / no code change
> **生成日期**: 2026-06-10
> **远端基准**: `origin/main` = `e2eff8ebfed1d04c5a76576fa347f2c09a465b06`（docs: add P9 real executor readiness evidence）
> **前置阶段**: P9-PEG-A/B/C: Pass；P9-REL-A/B/C/D/E/F1/F2/F3: Pass；P9-REL-G: Pass / Ready for user manual validation
> **阶段**: P9-REL-H：Manual UI/backend readback validation
> **状态**: P9-REL-H: Ready for user manual validation；P9 real executor launch: Not started；P9-REL-Pilot: Not started；P9-RGWP-Pilot: Not started；产品运行时 Git 写操作: Not started；AI Project Director 总闭环: Partial
> **相关文档**: `P9-REL-G真实执行器试点前就绪证据-20260610.md`、`P9-REL真实执行器接入总账与阶段设计-20260610.md`

---

## 1. 结论

| 结论项 | 状态 |
|--------|------|
| **P9-REL-H** | **Ready for user manual validation** |
| P9 real executor launch | **Not started** |
| P9-REL-Pilot | **Not started** |
| P9-RGWP-Pilot | **Not started** |
| 产品运行时 Git 写操作 | **Not started** |
| AI Project Director 总闭环 | **Partial** |

**P9-REL-H 定位**: 本阶段是人工验证指引文档。不启动真实执行器，不修改代码，不新增产品能力。目标是指引用户在本地开发环境中手动验证后端 readback API 和前端 readback panel 的只读行为。

**Gate 结论**: P9-REL-H Gate = **Ready for user manual validation** — 验证指引已完整，等待用户在本地环境中执行人工验证并填写结果。

---

## 2. 当前 origin/main 状态

| 项目 | 值 |
|------|-----|
| P9-REL-G 前置基准 | `5660e15aed3a91181a430d8196e087d13d41a528`（refactor: slim real executor readback panel） |
| P9-REL-G 完成后 main | `e2eff8ebfed1d04c5a76576fa347f2c09a465b06`（docs: add P9 real executor readiness evidence） |
| P9-REL-H 本轮基准 | `e2eff8ebfed1d04c5a76576fa347f2c09a465b06` |
| 分支 | `main` |
| 工作树 | clean（无未提交变更） |

---

## 3. 验证前置条件

| # | 条件 | 说明 |
|---|------|------|
| 1 | 后端可启动 | `cd runtime/orchestrator && uvicorn app.main:app --reload` 或其他开发启动方式 |
| 2 | 前端可启动 | `cd apps/web && npm run dev` 或其他开发启动方式 |
| 3 | 后端端口可达 | 默认 `http://localhost:8000`（具体端口以实际配置为准） |
| 4 | 前端端口可达 | 默认 `http://localhost:5173`（具体端口以实际配置为准） |
| 5 | **不启动真实执行器** | 不启动 Codex / Claude Code / DeepSeek CLI 进程 |
| 6 | **不修改代码** | 本轮验证只使用已有 readback API 和前端 readback panel |

---

## 4. 后端 readback API 人工验证步骤

### 4.1 验证目标

验证 `POST /runtime/real-executor/launch-readback` 返回只读 response，所有字段均为 disabled / blocked / non-executable。

### 4.2 curl 示例

以下 curl 命令发送一个安全 demo payload，不包含任何真实 secret：

```bash
curl -s -X POST http://localhost:8000/runtime/real-executor/launch-readback \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "manual-validation-001",
    "executor_label": "disabled-real-executor",
    "command_summary": "read-only future launch summary",
    "workspace_hint": "registered worktree",
    "safety_boundary": {
      "feature_flag_enabled": false,
      "human_confirmation_present": false,
      "executor_readiness_available": false,
      "workspace_worktree_gate_passed": false,
      "budget_cost_gate_passed": false,
      "concurrency_gate_passed": false,
      "timeout_supported": false,
      "cancel_supported": false,
      "kill_supported": false,
      "audit_events_append_only": true,
      "credential_exposure_blocked": true,
      "environment_dump_blocked": true,
      "product_runtime_git_write_allowed": false
    }
  }' | python3 -m json.tool
```

**说明**: 
- `request_id` 使用 `manual-validation-001`，可替换为任意唯一标识。
- `safety_boundary` 全部使用保守 blocked 值。
- 不包含任何 `api_key`、`token`、`secret`、`password`、`bearer`、`sk-` 等敏感文本。
- 不包含 `raw_command`、`args`、`env`、`cli_path`、`process_handle` 等字段。

### 4.3 验证步骤

1. 确保后端正在运行。
2. 在终端执行上述 curl 命令。
3. 检查 HTTP 状态码。
4. 检查 response body 中的关键字段。

### 4.4 期望结果

#### HTTP 状态码

**期望**: `200`

#### Response body 关键字段

| 字段 | 期望值 | 说明 |
|------|--------|------|
| `api_mode` | `"read_only"` | 固定为只读模式 |
| `adapter_enabled` | `false` | adapter 默认关闭 |
| `adapter_launch_status` | `"blocked"` | adapter launch 被阻塞 |
| `preview_executable` | `false` | preview 不可执行 |
| `real_executor_launch_started` | `false` | 真实执行器未启动 |
| `product_runtime_git_write_allowed` | `false` | 产品运行时 Git 写被禁止 |
| `redaction_applied` | `true` | 脱敏已应用 |
| `preflight_ready` | `false` | preflight 未就绪（因为 safety boundary 全部 blocked） |
| `preview_ready` | `false` | preview 未就绪 |
| `blocking_reasons` | 包含 `"real_executor_disabled"` | 至少包含 disabled reason |
| `display_steps` | 说明性文本列表 | 不包含可执行命令（不以 `$`/`bash`/`sudo`/`curl` 等开头） |

#### 禁止出现的字段

| 禁止字段 | 说明 |
|----------|------|
| `raw_command` | 不生成原始命令 |
| `args` | 不生成命令参数 |
| `env` / `env_vars` | 不生成环境变量 |
| `token` / `token_value` | 不生成 token |
| `secret` / `api_key` | 不生成密钥 |
| `cli_path` | 不生成 CLI 路径 |
| `process_handle` | 不生成进程句柄 |

---

## 5. 前端 readback panel 人工验证步骤

### 5.1 验证目标

验证工作台右侧 `RuntimeReadbackPanel` 中的 `真实执行器启动前只读读回` 卡片可以点击 `生成只读读回` 按钮并展示结果。所有结果仍显示 disabled / blocked / non-executable / no Git write / no real launch。

### 5.2 验证步骤

1. 确保后端和前端都在运行。
2. 打开浏览器，访问工作台页面。
3. 在页面右侧找到 `P9 受控运行时只读观察` 面板（`RuntimeReadbackPanel`）。
4. 在面板内找到 `真实执行器启动前只读读回` 卡片（`RealExecutorLaunchReadbackCard`）。
5. 卡片标题应为 `真实执行器启动前只读读回`。
6. 卡片副标题应包含 `只读 readback；即使 preflight_ready=true，adapter 仍 disabled，且 real_executor_launch_started=false。`
7. 点击 `生成只读读回` 按钮。
8. 等待按钮文案变为 `读取中...` 然后恢复。
9. 检查卡片展示的各个字段。

### 5.3 期望展示字段

#### readback safety flags 区块

| 字段 | 期望值 |
|------|--------|
| `api_mode` | `read_only` |
| `adapter_enabled` | `false` |
| `adapter_launch_status` | `blocked` |
| `preview_executable` | `false` |
| `real_executor_launch_started` | `false` |
| `product_runtime_git_write_allowed` | `false` |

#### preflight / preview readback 区块

| 字段 | 期望值 |
|------|--------|
| `readback_id` | 以 `real-executor-readback-` 开头 |
| `executor_label` | `disabled-real-executor` |
| `preflight_ready` | `false` |
| `preflight_status` | `blocked` |
| `preview_ready` | `false` |
| `redaction_applied` | `true` |
| `created_at` | UTC 时间戳 |

#### blocking reasons 区块

- 应展示 blocking reasons 列表。
- 至少包含 `real_executor_disabled`。
- 每项为独立标签。

#### display steps 区块

- 应展示说明性步骤列表。
- 区块上方标注 `说明性步骤，不是可运行指令。`
- 步骤内容为说明性文本，不包含可执行命令。

#### safe_summary 区块

- 展示后端返回的 `safe_summary`。
- 不包含 raw command / args / env / token / secret。

### 5.4 禁止出现的控制项

| 控制项 | 说明 |
|--------|------|
| 启动 / launch 按钮 | 不应存在 |
| 执行 / execute 按钮 | 不应存在 |
| 确认 / confirm / approve 按钮 | 不应存在 |
| consume token 按钮 | 不应存在 |
| kill / cleanup 按钮 | 不应存在 |
| Git add / commit / push 按钮 | 不应存在 |
| raw command / args / env 展示 | 不应存在 |

### 5.5 错误态验证（可选）

如果后端不可达：
- 卡片应展示 `只读 readback 读取失败：{error message}` 错误提示。
- 不应自动重试。
- 不应触发任何控制动作。

---

## 6. 期望结果汇总

| 验证项 | 期望结果 |
|--------|---------|
| 后端 API HTTP 状态码 | `200` |
| `api_mode` | `read_only` |
| `adapter_enabled` | `false` |
| `adapter_launch_status` | `blocked` |
| `preview_executable` | `false` |
| `real_executor_launch_started` | `false` |
| `product_runtime_git_write_allowed` | `false` |
| `redaction_applied` | `true` |
| `blocking_reasons` 包含 `real_executor_disabled` | 是 |
| response 不出现 raw_command / args / env / token / secret / cli_path / process_handle | 是 |
| 前端卡片可见 | 是 |
| 前端按钮文案为 `生成只读读回` | 是 |
| 前端 display steps 标注 `说明性步骤，不是可运行指令` | 是 |
| 前端不出现启动/执行/确认/consume 控制 | 是 |

---

## 7. 禁止动作

本验证阶段**严禁**以下任何动作：

| # | 禁止动作 | 原因 |
|---|---------|------|
| 1 | 启动 Codex / Claude Code / DeepSeek 作为产品运行时执行器 | 产品运行时执行器仍未启动 |
| 2 | 使用 subprocess / shell / os.popen / pty / terminal / tmux | 产品运行时不允许执行系统进程 |
| 3 | 读取 env / secret / token / CLI config 真实值 | 安全边界 |
| 4 | 生成 raw command / args / env | 安全边界 |
| 5 | 新增 execute / launch / approve / confirm / consume / token endpoint | 产品能力边界 |
| 6 | 新增 execute / launch / approve / confirm / consume / token 按钮 | 产品能力边界 |
| 7 | 新增可启动真实 adapter | 产品能力边界 |
| 8 | 执行产品运行时 Git 写（add/commit/push/PR/merge） | 产品运行时 Git 写仍未开启 |
| 9 | 进入 P9-REL-Pilot | 需要用户未来单独显式确认 |
| 10 | 进入 P9-RGWP-Pilot | 需要用户未来单独显式确认 |
| 11 | 把 P9 real executor launch 判 Pass | 仍 Not started |
| 12 | 把产品运行时 Git 写判 Pass | 仍 Not started |
| 13 | 把 AI Project Director 总闭环判 Pass | 仍 Partial |

---

## 8. 用户填写区

> **用户请在本区填写实际验证结果。以下表格初始为空，请在完成人工验证后回填。**

### 8.1 验证基本信息

| 项目 | 用户填写 |
|------|---------|
| 验证时间 | |
| 验证人 | |
| 后端 URL | |
| 前端 URL | |
| 截图/日志保存位置 | |

### 8.2 后端 API 验证结果

| 验证项 | 期望 | 实际 | 符合预期？ |
|--------|------|------|-----------|
| HTTP 状态码 | `200` | | |
| `api_mode` | `"read_only"` | | |
| `adapter_enabled` | `false` | | |
| `adapter_launch_status` | `"blocked"` | | |
| `preview_executable` | `false` | | |
| `real_executor_launch_started` | `false` | | |
| `product_runtime_git_write_allowed` | `false` | | |
| `redaction_applied` | `true` | | |
| `blocking_reasons` 包含 `real_executor_disabled` | 是 | | |
| 不出现 raw_command / args / env / token / secret / cli_path / process_handle | 是 | | |

### 8.3 前端 readback panel 验证结果

| 验证项 | 期望 | 实际 | 符合预期？ |
|--------|------|------|-----------|
| `真实执行器启动前只读读回` 卡片可见 | 是 | | |
| 按钮文案为 `生成只读读回` | 是 | | |
| 点击后展示 `api_mode=read_only` | 是 | | |
| 点击后展示 `adapter_enabled=false` | 是 | | |
| 点击后展示 `adapter_launch_status=blocked` | 是 | | |
| 点击后展示 `preview_executable=false` | 是 | | |
| 点击后展示 `real_executor_launch_started=false` | 是 | | |
| 点击后展示 `product_runtime_git_write_allowed=false` | 是 | | |
| display steps 标注 `说明性步骤，不是可运行指令` | 是 | | |
| 无启动/执行/确认/consume 按钮 | 是 | | |
| 无 Git add/commit/push 按钮 | 是 | | |

### 8.4 发现的问题

| # | 问题描述 | 严重程度 | 建议 |
|---|---------|---------|------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

### 8.5 用户结论

| 结论项 | 用户填写 |
|--------|---------|
| 后端 readback API 验证 | ☐ Pass / ☐ Fail / ☐ 未执行 |
| 前端 readback panel 验证 | ☐ Pass / ☐ Fail / ☐ 未执行 |
| 是否发现启动/执行/确认/consume 控制 | ☐ 未发现 / ☐ 发现（请描述） |
| 是否发现安全边界被越过 | ☐ 未发现 / ☐ 发现（请描述） |
| **用户总体结论** | ☐ P9-REL-H Pass / ☐ P9-REL-H Fail / ☐ 需要进一步调查 |
| **是否同意进入 P9-REL-Pilot** | ☐ 同意 / ☐ 不同意 / ☐ 需要更多验证 |

---

## 9. 验证报告模板

完成验证后，用户可将本章节复制并填写后回复，或更新本文件用户填写区。

```markdown
## P9-REL-H 验证报告

**验证时间**: YYYY-MM-DD HH:MM UTC
**验证人**: [姓名]
**后端 URL**: http://localhost:8000
**前端 URL**: http://localhost:5173

### 后端 API 验证

- HTTP 状态码: 200
- api_mode: read_only ✅
- adapter_enabled: false ✅
- adapter_launch_status: blocked ✅
- preview_executable: false ✅
- real_executor_launch_started: false ✅
- product_runtime_git_write_allowed: false ✅
- 无不安全字段: ✅

### 前端 readback panel 验证

- 卡片可见: ✅
- 按钮只读语义: ✅
- 字段展示符合预期: ✅
- 无禁止控制: ✅

### 结论

P9-REL-H: [Pass / Fail]
是否同意进入 P9-REL-Pilot: [是 / 否]
```

---

## 10. Gate 结论

| # | Gate 条件 | 结论 |
|---|----------|------|
| 1 | origin/main HEAD 确认 | **Pass** — `e2eff8ebfed1d04c5a76576fa347f2c09a465b06` |
| 2 | 验证指引完整（后端 + 前端） | **Pass** — curl 示例、验证步骤、期望结果、用户填写区均已提供 |
| 3 | Safety boundary 默认保守 blocked | **Pass** — curl body 全部 gates = false，仅 audit/credential/env = true |
| 4 | 不包含真实 secret | **Pass** — curl body 无 api_key/token/secret/password/bearer/sk- |
| 5 | 不包含 raw command / args / env | **Pass** — curl body 无此类字段 |
| 6 | 禁止动作清单完整 | **Pass** — 13 项禁止动作均已列出 |
| 7 | 用户填写区已预留 | **Pass** — 包含基本信息、后端验证、前端验证、问题、结论表 |
| 8 | 验证报告模板已提供 | **Pass** — 第 9 章 |
| 9 | 未修改业务代码 | **Pass**（本轮仅新增文档） |
| 10 | 未新增产品能力 | **Pass** |
| 11 | 未修改 runtime/orchestrator | **Pass** |
| 12 | 未修改 apps/web | **Pass** |
| 13 | 未修改参考项目 | **Pass** |
| 14 | 未启动 Codex / Claude Code / DeepSeek | **Pass** |
| 15 | 未使用 subprocess / shell / os.popen / pty / terminal / tmux | **Pass** |
| 16 | 未读取 env / secret / token / CLI config | **Pass** |
| 17 | 未生成 raw command / args / env | **Pass** |
| 18 | 未新增 execute / launch / approve / confirm / consume / token endpoint 或按钮 | **Pass** |
| 19 | 未新增可启动真实 adapter | **Pass** |
| 20 | 未执行产品运行时 Git 写 | **Pass** |
| 21 | 未进入 P9-REL-Pilot / P9-RGWP-Pilot | **Pass** |
| 22 | P9 real executor launch 仍 Not started | **Pass** |
| 23 | P9-REL-Pilot 仍 Not started | **Pass** |
| 24 | P9-RGWP-Pilot 仍 Not started | **Pass** |
| 25 | 产品运行时 Git 写操作仍 Not started | **Pass** |
| 26 | AI Project Director 总闭环仍 Partial | **Pass** |
| **P9-REL-H Gate** | | **Ready for user manual validation** |

---

## 附录：本轮开发流程 Git 操作记录

| 操作 | 说明 |
|------|------|
| 新增文件 | `P9-REL-H人工readback验证指引与证据-20260610.md` |
| 修改文件 | `P9-REL真实执行器接入总账与阶段设计-20260610.md`（追加 P9-REL-H 状态段）、`AI项目主管文档索引.md`（追加 P9-REL-H 入口和状态行） |
| 禁止修改 | `runtime/orchestrator/app/**`、`runtime/orchestrator/tests/**`、`apps/web/**`、`migrations/**`、package/dependency/CI 配置、参考项目任何文件 |
| 禁止实现 | 可启动的 RealExecutorAdapter、subprocess/shell/os.popen、Codex/Claude Code/DeepSeek 启动、execute/launch/commit/push endpoint、approve/confirm/consume endpoint、token issue/consume、产品运行时 Git 写、真实执行器启动、新产品能力 |
| 开发流程 Git | `git add` → `git commit` → `git push origin main` |
