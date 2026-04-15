# V5 前端控制面表面图

## 1. 目的

把 `write-v5-web-control-surface` 绑定到仓库里真实存在的 `apps/web` 入口，避免线程一上来就脱离现实发明前端结构。

这个参考文件回答五个问题：

1. 当前前端控制面主要落在哪些 feature
2. 哪些页面已经有 V5 控制台基础
3. 哪些能力还只是“局部观察面”，还不是完整控制中心
4. 一个前端线程应该先从哪里切进去
5. 什么时候当前线程应暂停并让位给 `govern-v5-web-structure`

## 2. 当前已确认的真实前端基础

### 技术栈

- `apps/web/package.json` 已表明当前前端是 `React + Vite + TypeScript`
- 已使用 `@tanstack/react-query`
- 请求封装位于 `apps/web/src/lib/http.ts`

### 老板与项目总览入口

- `apps/web/src/features/projects/ProjectOverviewPage.tsx`

当前已确认：

- 这是当前最接近“老板控制台总入口”的页面。
- 页面已经聚合了项目、角色、策略、技能、记忆、仓库等多个子视角。
- 因此很多 V5 控制面扩展，优先考虑挂在 `projects` 体系或由该页进入。
- 但它已经是高风险聚合页，新增控制面时只能增加**最小入口挂载**；如果要继续塞大块实现，应先让位给 `govern-v5-web-structure`。

### 角色与策略基础

- `apps/web/src/features/roles/RoleCatalogPage.tsx`
- `apps/web/src/features/roles/RoleEditorDrawer.tsx`
- `apps/web/src/features/strategy/StrategyDecisionPanel.tsx`
- `apps/web/src/features/strategy/StrategyRuleEditor.tsx`

当前已确认：

- 已经存在角色配置与策略观察 / 编辑基础。
- 这为 `role model policy`、角色预算、角色启停与老板策略控制提供了天然起点。
- 但它们还不等于完整的 `team control center`。

### Skill 与绑定基础

- `apps/web/src/features/skills/SkillRegistryPage.tsx`
- `apps/web/src/features/skills/RoleSkillBindingPanel.tsx`

当前已确认：

- 已经有 Skill 注册中心与项目内角色 Skill 绑定面。
- 它们适合作为 prompt / skill / policy 资产管理控制面的起点。
- 但不能把“已有 registry 页面”误写成“V5 prompt registry 全部完成”。

### 记忆与运行观察基础

- `apps/web/src/features/projects/ProjectMemoryPanel.tsx`
- `apps/web/src/features/projects/MemorySearchPanel.tsx`
- `apps/web/src/features/run-log/`
- `apps/web/src/features/console/`
- `apps/web/src/features/console-metrics/`

当前已确认：

- 已有 project memory 查看和搜索基础。
- 已有运行日志、控制台、指标观察面。
- 这为 V5 的 memory governance、checkpoint timeline、token usage、evidence replay 提供了入口基础。

## 3. 推荐优先切面

按 V5 母本，前端控制面线程优先从下面几个切面切入：

1. **角色 / 模型策略控制**
   - 入口：`roles`、`strategy`、`projects`
   - 目标：让 role model policy 与老板策略干预可见、可改、可反馈

2. **团队控制中心**
   - 入口：先从 `projects / roles / strategy` 组合扩展，再判断是否新增 `agent-teams`
   - 目标：角色启停、预算、模型强度、审批阈值、参与策略

3. **成本与 token 可视化**
   - 入口：`budget`、`console-metrics`、`projects`
   - 目标：usage、成本、预算压力、按角色 / 任务 / 线程拆账

4. **记忆治理与线程观察**
   - 入口：`projects`、`run-log`、`console`
   - 目标：memory recall、checkpoint、bad context、rehydrate 的观察与操作入口

## 4. 新增 feature 的安全边界

只有在现有目录明显装不下时，才考虑新增：

- `apps/web/src/features/agent-teams/`
- `apps/web/src/features/agents/`
- `apps/web/src/features/prompts/`
- `apps/web/src/features/costs/`
- `apps/web/src/features/memory-governance/`

新增前先回答：

1. 为什么现有 `projects / roles / strategy / skills / budget / console` 装不下
2. 新 feature 是短期容器还是长期 owner 面
3. 它和 `ProjectOverviewPage` 的入口关系是什么
4. 是否已经需要 `govern-v5-web-structure` 先来确定结构落位

如果第 4 问答不清楚，就不要直接新增 feature。

## 5. 触发让位给 `govern-v5-web-structure` 的典型信号

出现下面任一情况，本线程应先停在结构治理，而不是继续堆控制面：

- 需要把大段控制面实现继续塞进 `ProjectOverviewPage.tsx` 或 `App.tsx`
- 需要先抽 `sections/`、`components/`、`hooks.ts`、`types.ts`、`api.ts`
- 新增 feature 的 owner 归属不清，可能让边界变碎
- 关键目标其实是补稳定锚点、保护 smoke、减少联调脆弱性
- 当前页面已经不是“挂入口”，而是在承担多个 feature 的具体实现

## 6. 一个典型前端线程的切入顺序

建议顺序：

1. 找到用户要推进的 V5 工作包
2. 在本图里确认对应 feature
3. 先判断这是不是控制面交付，而不是结构治理
4. 只读最小页面、hooks、types、api
5. 先想清楚“入口 -> 状态 -> 动作 -> 反馈 -> 验证”
6. 再动代码

如果第 3 步答不清楚，就先交给 `govern-v5-web-structure` 收口结构边界。
