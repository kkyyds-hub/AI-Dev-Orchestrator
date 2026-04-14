# V5 后端迁移与兼容性检查清单

## 1. 目的

V5 后端线程最容易出问题的地方，不是“不会写代码”，而是：

- 字段加了但迁移没想清楚
- DTO 改了但前端没法读
- worker 新链路接了但旧链路直接断
- 文件快照、日志和数据库出现三套口径

本清单用于在动手前和交付前快速自检。

## 2. schema / domain 检查

如果你要新增或修改字段，至少确认：

- `app/domain/` 是否需要同步字段
- `app/core/db_tables.py` 是否需要补列
- `app/repositories/` 的读写映射是否需要同步
- `app/api/routes/*.py` 的响应 DTO 是否需要同步
- 老数据是否允许为 `NULL`
- 新字段是否需要默认值
- 回放旧记录时是否会因为缺字段报错

### 当前已知要特别小心的点

- `RunTable` 已有 `model_name`，但不代表已有 `provider_name`、`model_tier`、真实 usage 字段。
- `prompt_tokens / completion_tokens / estimated_cost` 已存在，但当前来源主要还是启发式估算。
- 如果把真实 provider usage 接进来，要同时判断：旧 run 记录、旧 API、旧页面能否兼容。

## 3. worker / service 主链检查

如果你要改 worker 或执行链，至少确认：

- 改动是否真的被 `TaskWorker` 走到
- 失败时是否还能保留 `simulate` 或旧链路回退
- 运行日志是否还能正常落盘
- 验证链是否仍能执行
- 异常时会不会导致任务永久停在 `running`

### 当前已知要特别小心的点

- `TaskWorker` 当前是完整的主调度链，改动不要绕开它平行造新入口。
- `ExecutorService` 当前以 `shell` / `simulate` 为基础，真实 provider 模式最好与旧模式并存，而不是一次性替换掉。

## 4. memory / 文件持久化检查

如果你要改 memory、checkpoint 或回放能力，至少确认：

- 数据究竟落数据库、JSON 文件还是两者并存
- 文件路径是否稳定
- 路径是否依赖 `settings.runtime_data_dir`
- 新逻辑是否会与旧快照格式冲突
- 旧快照读不出来时是否有降级或忽略逻辑

### 当前已知要特别小心的点

- `ProjectMemoryService` 当前把快照写到 `runtime_data_dir/project-memories/...`
- 如果新增 checkpoint / thread recovery，不要直接假设它应该跟 memory 一样存；要先明确读写场景与回放责任

## 5. route / API 合同检查

如果你要改 route，至少确认：

- DTO 是否与 domain / repository 一致
- 字段命名是否延续现有风格
- 是否会让现有前端页面报错
- 是否需要为新字段提供默认值或兼容填充
- 是否需要在 `runs.py`、`strategy.py`、`skills.py` 等现有观察面同步展示

## 6. 验证与回滚检查

交付前至少回答：

- 我做了什么最小验证
- 哪些没有验证
- 失败后如何回滚
- 旧数据和旧页面会不会直接坏掉
- 下一线程该先接 `review`、`verify` 还是 `web`

如果这些问题答不上来，就不要把状态写成“已完成”。
