# V5 前端控制面交付 playbook

## 1. 目的

把一次 V5 前端工作包，收敛成 **feature owner 清楚、字段契约清楚、状态反馈完整、最小验证可复述** 的控制面交付切片。

这个 playbook 只服务于前端控制面功能落地，不负责前端结构治理、后端实现、运行验证或阶段裁定。

## 2. 进入前先判断什么

开始前先回答：

1. 这次主目标是新增 / 补完控制能力，还是先治理结构风险？
2. 现有 feature owner 是否已经明确？
3. 若直接动手，是否会把 `App.tsx`、`ProjectOverviewPage.tsx` 或其他聚合页继续做胖？
4. 当前问题是控制面 feature 缺口，还是其实已经变成结构落位和边界治理问题？

如果主问题偏向页面 owner、拆分边界、大文件瘦身或稳定锚点，先让位给 `govern-v5-web-structure`。

## 3. 最小执行步骤

### 步骤 1：把请求翻译成一个控制面切片

至少写清：

- 属于哪个 V5 Phase / 工作包
- 对应哪个 feature
- 本轮只做哪个页面 / 面板 / 抽屉 / 表单 / 观察区
- 依赖哪些后端字段 / 接口 / 动作
- 本轮明确不做什么

### 步骤 2：先决定安全落位

优先复用现有 feature 边界，例如：

- `projects`
- `roles`
- `strategy`
- `skills`
- `budget`
- `console`
- `console-metrics`
- `run-log`

只有在现有 feature 明显装不下、且 owner 归属仍清楚时，才新增落位。

### 步骤 3：先做 contract 与状态面检查

动手前至少核对：

- hooks / api / types / page 是否同步
- loading / empty / error / disabled / submit feedback 是否有落点
- 文案是否夸大“已接入 / 已完成 / 可用 / 推荐”
- 是否已有明确的后端字段与接口合同

### 步骤 4：实现控制面切片

实现时遵守：

- 优先沿现有 feature 边界扩展
- 不把复杂状态逻辑继续塞回聚合页
- 不用静态假数据伪装“真实接入”
- 对依赖前提和缺口做诚实说明

### 步骤 5：做最小验证

最低要求至少说明：

- 是否运行 `npm run build`
- 推荐的手工验证路径
- 未验证项与原因
- 是否需要后续 `verify-v5-runtime-and-regression` 接棒

## 4. 执行时重点检查什么

- feature owner 是否清楚，是否落在正确页面 / feature
- 字段名、枚举值、状态文案是否与后端合同一致
- loading / empty / error / disabled / submit pending / success feedback 是否完整
- 是否把结构问题伪装成控制面实现继续硬做
- 是否已经出现需要 `govern-v5-web-structure` 先接手的结构信号

## 5. 完成后怎么输出

结束时至少输出：

- 本轮控制面切片归属：Phase / 工作包 / feature
- 本轮改了哪些页面、hooks、types、api 或组件
- 合同与状态反馈是否已覆盖
- 已做的最小验证、未做的验证与原因
- 当前切片已完成什么、明确没完成什么
- 下一线程建议 skill

## 6. 什么时候应该让位给兄弟 skill

- 页面 owner、落位、拆分边界、大文件瘦身、稳定锚点问题更突出 → `govern-v5-web-structure`
- 后端字段、接口、动作缺口阻断当前切片 → `write-v5-runtime-backend`
- 需要 build / 页面打开 / 联调 / 回归证据 → `verify-v5-runtime-and-regression`
- 需要前后端字段契约、边界或风险审查 → `review-v5-code-and-risk`
- 线程已经自然跨 backend / web / docs / verify 多面推进 → `drive-v5-orchestrator-delivery`
- 需要阶段通过 / 部分通过 / 阻塞裁定 → `accept-v5-milestone-gate`
