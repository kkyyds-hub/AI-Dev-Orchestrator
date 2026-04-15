# V5 skill pack 维护检查清单

## 一、可读性与基础完整性

- [ ] 文件为 UTF-8 可读，无乱码、无连续问号占位乱码、无语义断裂
- [ ] front matter 正常，`name` 与 `description` 可读
- [ ] 标题层级完整，不存在明显缺章或空章节
- [ ] 配套文件名、目录名与正文引用一致

## 二、owner 与边界

- [ ] 能一句话说清当前 skill 负责什么
- [ ] 能一句话说清当前 skill 不负责什么
- [ ] 已写清什么时候使用 / 不要使用
- [ ] 已明确与最容易冲突的兄弟 skill 的分界

## 三、开始入口与工作流

- [ ] 已写出最小必读材料
- [ ] 已写出标准工作流，而不是抽象宣言
- [ ] 已写出交接规则、下一棒建议或推荐输出骨架
- [ ] 新线程拿到此 skill 后能直接知道先做什么

## 四、packaging 同步

- [ ] `SKILL.md` 与 `agents/openai.yaml` 描述同一个 owner
- [ ] `references/*` 真能支撑边界判断、路由判断或维护动作
- [ ] 如有 `playbooks/*`、`templates/*`，内容可直接复用
- [ ] 配套文件之间不存在明显口径冲突

## 五、与 4 个关键兄弟 skill 的路由

- [ ] 已明确何时应转 `write-v5-web-control-surface`
- [ ] 已明确何时应转 `govern-v5-web-structure`
- [ ] 已明确何时应转 `drive-v5-orchestrator-delivery`
- [ ] 已明确何时应转 `verify-v5-runtime-and-regression`
- [ ] 已明确什么时候应该先调用 `build-v5-skill-pack`

## 六、越权防线

- [ ] 未借修 skill 之名改 `apps/web`
- [ ] 未借修 skill 之名改 `runtime/orchestrator`
- [ ] 未借修 skill 之名替 verify / accept / docs 下结论
- [ ] 未在范围外静默改写其他兄弟 skill 本体

## 七、可接力性

- [ ] 本轮维护对象、维护类型、损坏点已写清
- [ ] 本轮修复和补强点已能被后续线程复述
- [ ] 后续线程知道什么时候先调 `build-v5-skill-pack`
- [ ] 如果下一步应切回业务 owner，已写清目标 skill
