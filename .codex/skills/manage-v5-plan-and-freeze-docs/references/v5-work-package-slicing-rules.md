# V5 工作包切片规则

## 1. 目的

把 V5 母本中的能力主题，切成后续线程可直接执行的工作包，而不是继续停留在抽象规划层。

## 2. 切片的基本单位

一个合格的 V5 工作包切片，至少回答下面问题：

- 它属于哪个 Phase
- 它对应母本的哪个能力主题
- 它为什么现在做，而不是以后做
- 它主要动后端、前端，还是跨层
- 它应该由哪个 owner skill 接手
- 它的完成定义是什么
- 它的非完成定义是什么
- 它的最低验证证据是什么
- 它做完后下一线程应该接什么

## 3. Phase 优先级基线

V5 母本已经给出推荐实施顺序：

### Phase 1：先做可落地的最小闭环

- Provider 抽象层
- Prompt registry v1
- Token accounting v1
- Role model policy v1
- Worker 默认接入 project memory recall

### Phase 2：把记忆和上下文治理做起来

- thread checkpoint
- rolling summary
- bad context detection
- thread reset / rehydrate
- memory compaction

### Phase 3：把多 Agent 协作做起来

- agent session
- agent message
- review/rework thread
- boss intervention

### Phase 4：把老板控制与成本优化做起来

- team assembly
- team control center
- prompt cache
- response cache
- cost dashboard

### Phase 5：打磨产品化体验

- prompt versions
- prompt diff
- optimization recommendations
- project templates
- e2e acceptance

如果没有很强证据，不要随意打乱 Phase 级顺序。

## 4. 常用切片方法

### 方法 A：按实现面切

适用：同一工作包天然分为后端 / 前端 / 验证。

示例：

- provider-gateway-backend
- provider-gateway-web-panel
- provider-gateway-verification

### 方法 B：按主链先后切

适用：某能力必须先打通主链，再补增强。

示例：

- project-memory-worker-recall
- project-memory-observability
- project-memory-tuning

### 方法 C：按“最小闭环”切

适用：目标太大，需要先做可交付的第一轮。

示例：

- token-accounting-v1-receipt-persistence
- token-accounting-v1-project-run-aggregation
- token-accounting-v1-dashboard

## 5. 推荐的 owner skill 映射

### 文档与切片

- `manage-v5-plan-and-freeze-docs`

### 后端实现

- `write-v5-runtime-backend`

### 前端控制面

- `write-v5-web-control-surface`

### 跨层交付

- `drive-v5-orchestrator-delivery`

### 运行验证

- `verify-v5-runtime-and-regression`

### 风险审查

- `review-v5-code-and-risk`

### 阶段裁定

- `accept-v5-milestone-gate`

## 6. 切片时必须落到真实改动面

每个工作包都至少写出以下之一：

- 主要后端目录/文件
- 主要前端目录/文件
- 主要文档目录/文件
- 主要验证入口/命令/页面/API

不允许只写：

- “提升多 Agent 协作体验”
- “增强老板控制能力”
- “优化记忆效果”

这种描述不是工作包，只是目标口号。

## 7. 完成定义模板

建议至少包含：

- 主链能力已接上
- 必要的数据结构或接口已落地
- 最小 UI/观察面已具备（如该包涉及前端）
- 最低验证已完成
- 文档已回填

## 8. 非完成定义模板

遇到下列情况，一律不能写成完成：

- 只有 schema / domain 草案，没有主链接线
- 只有 API 草案，没有实际 route/service 落地
- 只有前端静态页面，没有接真实接口或状态
- 只有本地推演，没有构建/接口/运行证据
- 只有一个侧面完成，但跨层包被写成整体完成

## 9. 最低验证要求模板

按工作包类型选最小验证：

### 后端包

- 单测 / 集成测 / 路由 smoke test 至少其一
- 能证明主链实际调用

### 前端包

- build 通过
- 关键页面或关键交互最小可见

### 跨层包

- 至少 1 条端到端链路被验证
- 文档、实现、验证三者口径一致

### 文档治理包

- 目录位置正确
- 状态词诚实
- owner skill 明确
- 交接说明明确

## 10. 推荐输出模板

```md
## 本轮推进切片
- Phase：
- 工作包：
- owner skill：
- 主要改动面：
- 前置依赖：
- 完成定义：
- 非完成定义：
- 最低验证：
- 下一线程建议：
```

## 11. 红线

1. 不要把一个超大主题直接当成单线程可完成工作包。
2. 不要让 implementer 自己再决定“到底改哪些目录”。
3. 不要把验证完全留白。
4. 不要把跨层任务伪装成单侧任务。
5. 不要在未核对当前代码现状前随意宣布某 Phase 已完成。
