# AI Project Director Session Phase1 — 验收文档

> 文档日期：2026-05-19
> 仓库：kkyyds-hub/AI-Dev-Orchestrator
> 阶段：BCG-01 Phase1 后端闭环补齐
> 性质：后端实现级验收
> 配套文档：
> - `backend-closure-gap-freeze-20260519-v2.md`
> - `execution-plan-backfill-ledger-20260519.md`

---

## 1. 实现范围

本阶段建立 AI 项目主管的第一层后端闭环：

```
用户提交大目标 → AI 项目主管生成澄清问题 → 用户提交回答 → 后端整理确认版目标摘要 → 用户确认目标
```

同时新增项目内 Skill 契约文件，规定 AI 项目主管以后必须按固定流程工作。

---

## 2. 新增 API

| 方法 | 路径 | 状态码 | 说明 |
|---|---|---|---|
| POST | `/project-director/sessions` | 201 | 创建会话，返回确定性澄清问题 |
| GET | `/project-director/sessions/{session_id}` | 200 | 读取会话详情（含输出契约字段） |
| POST | `/project-director/sessions/{session_id}/answers` | 200 | 提交澄清回答，状态转换 clarifying→ready_to_confirm |
| POST | `/project-director/sessions/{session_id}/confirm` | 200 | 确认目标摘要，状态转换 ready_to_confirm→confirmed |

### 输出契约字段

每个 GET/POST 响应包含：

| 字段 | 说明 |
|---|---|
| `next_action` | 当前阶段建议的下一步动作 |
| `missing_info` | 当前阶段缺失的信息 |
| `needs_user_confirmation` | 是否需要用户确认 |
| `forbidden_actions` | 当前阶段禁止的动作 |
| `gate_conclusion` | 当前 Gate 结论 |

---

## 3. 新增文件

| 文件 | 说明 |
|---|---|
| `.kkr/skills/ai-project-director/SKILL.md` | AI 项目主管 Skill 契约（职责、硬性规则、标准流程、输出契约） |
| `app/domain/project_director_session.py` | 领域模型（SessionStatus 枚举 + ProjectDirectorSession + ClarifyingQuestion + ClarifyingAnswer） |
| `app/repositories/project_director_session_repository.py` | 数据仓库（CRUD，JSON 序列化/反序列化） |
| `app/services/project_director_service.py` | 业务逻辑（确定性规则澄清问题生成、目标摘要生成、状态流转） |
| `app/api/routes/project_director.py` | API 路由（4 个端点 + 请求/响应 DTO + 契约字段计算） |
| `tests/test_project_director_sessions.py` | 后端测试（31 个用例） |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/core/db_tables.py` | 新增 ProjectDirectorSessionTable ORM 表 |
| `app/api/router.py` | 注册 project_director_router |

---

## 4. 测试命令

```bash
cd runtime/orchestrator
python -m pytest tests/test_project_director_sessions.py -v
```

---

## 5. 测试结果

```
============================= 31 passed, 1 warning =============================
```

### 测试覆盖

| 测试类 | 用例数 | 覆盖内容 |
|---|---|---|
| TestCreateSession | 7 | 创建会话、携带 project_id、约束、空目标拒绝、短目标触发补充问题、问题 ID/hint、契约字段 |
| TestGetSession | 2 | 读取存在/不存在会话 |
| TestSubmitAnswers | 6 | 提交答案转换状态、部分回答、404、无效 question_id、空数组拒绝、重复提交 409 |
| TestConfirmGoal | 5 | 确认转换状态、重复确认幂等、未回答前确认 409、404、确认后契约字段 |
| TestService | 7 | 完整流程、唯一 ID、404、状态前置检查、幂等确认 |
| TestContractFields | 3 | 各状态 forbidden_actions、missing_info、needs_user_confirmation |

---

## 7. 未覆盖范围

- 前端页面（本阶段未改前端）
- 真实 AI 调用（Phase1 使用确定性规则）
- Provider 集成
- Worker 调度
- 任务创建
- 计划生成（Plan Draft 阶段未实现）
- 仓库写入
- 运行证据（截图、E2E 联调）

---

## 8. Gate 结论

```text
Gate 结论：Partial
后端实现：Backend Pass
运行证据：Runtime Evidence Missing
总闭环：Partial（BCG-01 Phase1 仅覆盖目标澄清与确认，不代表 AI Project Director 总闭环 Pass）
```

### 理由

- 4 个 API 真实读写数据库，状态机完整
- 确定性澄清规则可生成 3-6 个结构化问题
- 输出契约字段覆盖全部端点
- 31 个测试全部通过，覆盖正常路径和错误路径
- 未改前端、未接 AI、未创建任务、未调度 Worker、未写仓库
