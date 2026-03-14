# Day10 失败复盘模板（冻结）

> 用途：统一记录一次失败/阻断运行的事实、处置动作和结论，便于后续聚类与回放。

---

## 1. 基本信息

- review_id：
- task_id：
- task_title：
- run_id：
- run_status：`failed / cancelled`
- created_at：

---

## 2. 失败事实

- failure_category：
- quality_gate_passed：
- route_reason（原始）：
- result_summary（原始）：
- log_path：

---

## 3. 证据与过程

- evidence_events（按时间顺序）：
  1.
  2.
  3.
- 关键证据截图/片段（可选）：
  - 

---

## 4. 处置动作

- action_summary（系统已执行动作）：
- 人工补充动作（可选）：
  1.
  2.

---

## 5. 复盘结论

- conclusion（最终结论）：
- 是否可自动修复：`yes / no / partial`
- 下一步建议：
  1.
  2.

---

## 6. 归档与关联

- storage_path：
- 关联决策回放：`GET /runs/{run_id}/decision-trace`
- 关联复盘查询：`GET /runs/{run_id}/failure-review`
