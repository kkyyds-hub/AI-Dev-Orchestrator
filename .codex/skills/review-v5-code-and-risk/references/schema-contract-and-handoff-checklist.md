# V5 schema / 合同 / 交接检查清单

## 1. 目的

很多 V5 风险并不是“代码会不会跑”，而是：

- schema 以为有，其实没有
- migration 该做没做
- 默认值 / 空值没处理
- 前后端字段漂移
- verify 只覆盖了一部分，却被文档写成全量通过

本清单用于快速检查这些高频坑。

## 2. schema 与兼容性

如果这次改动涉及后端结构，至少确认：

- `domain` 是否同步
- `db_tables.py` 是否同步
- `repository` 映射是否同步
- route DTO 是否同步
- 老数据是否允许空值
- 新字段是否有默认值
- 是否需要 migration

## 3. 主链接线

至少确认：

- 能力是否真的被 worker / route / page 主链消费
- 是否只有字段或 DTO，没有真实调用
- 失败时是否有降级或回退
- 旧链路是否还能共存

## 4. 前后端合同

至少确认：

- 前端 `types.ts / hooks.ts / api.ts / page` 是否一致
- 页面文案是否夸大真实状态
- 缺失后端合同时，前端是否诚实标识依赖前提

## 5. 文档与 verify 口径

至少确认：

- 文档写的“已完成”是否真的有 verify 支撑
- verify 的范围是否匹配实现声明
- 如果 verify 只做了部分验证，文档是否也诚实写成部分完成

## 6. 交接建议

如果发现问题，尽量明确交给谁：

- 后端实现缺口 → `write-v5-runtime-backend`
- 前端实现缺口 → `write-v5-web-control-surface`
- 缺运行事实 → `verify-v5-runtime-and-regression`
- 缺文档回填 → `manage-v5-plan-and-freeze-docs`
- 已具备裁定条件 → `accept-v5-milestone-gate`

如果线程本质已经跨层，就不要硬塞给单一实现 skill，直接建议升级 `drive-v5-orchestrator-delivery`。
