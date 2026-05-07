import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapTaskStatusTone } from "../../../lib/status";
import type { TaskDetail } from "../types";
import { DetailField } from "./TaskDetailField";

export function TaskDetailBaseInfoCard(props: { detail: TaskDetail }) {
  const { detail } = props;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-slate-50">{detail.title}</h3>
          <p className="text-xs text-slate-500">Task ID：{detail.id}</p>
        </div>
        <StatusBadge label={detail.status} tone={mapTaskStatusTone(detail.status)} />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField label="优先级" value={detail.priority} />
        <DetailField label="风险等级" value={detail.risk_level} />
        <DetailField label="人工状态" value={detail.human_status} />
        <DetailField label="验收项数量" value={String(detail.acceptance_criteria.length)} />
        <DetailField label="依赖数量" value={String(detail.depends_on_task_ids.length)} />
        <DetailField label="创建时间" value={formatDateTime(detail.created_at)} />
        <DetailField label="更新时间" value={formatDateTime(detail.updated_at)} />
        <DetailField label="运行次数" value={String(detail.runs.length)} />
      </div>

      <div className="mt-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">输入摘要</div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
          {detail.input_summary}
        </p>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">验收标准</div>
          {detail.acceptance_criteria.length > 0 ? (
            <ul className="mt-2 space-y-2 text-sm text-slate-300">
              {detail.acceptance_criteria.map((criterion, index) => (
                <li
                  key={`${detail.id}-criterion-${index}`}
                  className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2"
                >
                  {criterion}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-500">暂无显式验收标准</p>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">依赖任务</div>
            {detail.depends_on_task_ids.length > 0 ? (
              <div className="mt-2 space-y-2">
                {detail.depends_on_task_ids.map((dependencyId) => (
                  <code
                    key={dependencyId}
                    className="block break-all rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-xs text-cyan-200"
                  >
                    {dependencyId}
                  </code>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">无前置依赖</p>
            )}
          </div>

          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">暂停说明</div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
              {detail.paused_reason ?? "未设置暂停说明"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
