import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useProjectChangeEvidence } from "../deliverables/hooks";

type DiffSummaryPageProps = {
  projectId: string | null;
};

export function DiffSummaryPage(props: DiffSummaryPageProps) {
  const evidenceQuery = useProjectChangeEvidence(props.projectId);
  const evidence = evidenceQuery.data ?? null;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">
            V4 Day11 Diff Summary
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">
            代码差异视图
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            按文件维度聚合当前仓库差异，展示增删改统计、关键文件列表，并把 ChangeBatch 上下文映射到老板可读的验收视图。
          </p>
        </div>

        {evidence ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="变更文件"
              value={String(evidence.diff_summary.metrics.changed_file_count)}
            />
            <MetricCard
              label="新增行数"
              value={String(evidence.diff_summary.metrics.total_added_line_count)}
            />
            <MetricCard
              label="删除行数"
              value={String(evidence.diff_summary.metrics.total_deleted_line_count)}
            />
            <MetricCard
              label="关键文件"
              value={String(evidence.diff_summary.metrics.key_file_count)}
            />
          </div>
        ) : null}
      </header>

      {!props.projectId ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
          先在老板首页选择一个项目，再查看 Day11 代码差异视图。
        </div>
      ) : evidenceQuery.isLoading && !evidence ? (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
          正在读取仓库差异摘要...
        </div>
      ) : evidenceQuery.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          代码差异视图加载失败：{evidenceQuery.error.message}
        </div>
      ) : evidence ? (
        <>
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-400">
            <span>基线：{evidence.diff_summary.baseline_label}</span>
            <span>目标：{evidence.diff_summary.target_label}</span>
            <span>生成时间：{formatDateTime(evidence.diff_summary.generated_at)}</span>
            {evidence.selected_change_batch_title ? (
              <span>批次：{evidence.selected_change_batch_title}</span>
            ) : null}
          </div>

          {evidence.diff_summary.note ? (
            <div className="mt-4 rounded-2xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
              {evidence.diff_summary.note}
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge
              label={`新增 ${evidence.diff_summary.metrics.added_file_count}`}
              tone="success"
            />
            <StatusBadge
              label={`修改 ${evidence.diff_summary.metrics.modified_file_count}`}
              tone="info"
            />
            <StatusBadge
              label={`删除 ${evidence.diff_summary.metrics.deleted_file_count}`}
              tone="danger"
            />
            <StatusBadge
              label={`未跟踪 ${evidence.diff_summary.metrics.untracked_file_count}`}
              tone="warning"
            />
            {evidence.diff_summary.dirty_workspace ? (
              <StatusBadge
                label={`工作区脏文件 ${evidence.diff_summary.dirty_file_count}`}
                tone="warning"
              />
            ) : (
              <StatusBadge label="工作区干净" tone="neutral" />
            )}
          </div>

          <section className="mt-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-slate-50">关键文件列表</h4>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  优先突出 ChangeBatch 覆盖文件，以及删除 / 未跟踪等高关注项。
                </p>
              </div>
              <StatusBadge
                label={`${evidence.diff_summary.key_files.length} 项`}
                tone="neutral"
              />
            </div>

            {evidence.diff_summary.key_files.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {evidence.diff_summary.key_files.map((file) => (
                  <StatusBadge
                    key={file.relative_path}
                    label={`${renderDiffKind(file.change_kind)} · ${file.relative_path}`}
                    tone={mapDiffTone(file.change_kind)}
                  />
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-slate-400">
                当前范围内没有可单独高亮的关键文件。
              </p>
            )}
          </section>

          <section className="mt-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-slate-50">按文件聚合的差异统计</h4>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  仅展示 Day11 范围内的差异摘要，不扩展到 Day12+ 的回退重做或提交候选。
                </p>
              </div>
              <StatusBadge
                label={`${evidence.diff_summary.files.length} 行`}
                tone="neutral"
              />
            </div>

            {evidence.diff_summary.files.length > 0 ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-800 text-sm">
                  <thead className="text-left text-xs uppercase tracking-[0.18em] text-slate-500">
                    <tr>
                      <th className="px-3 py-3">文件</th>
                      <th className="px-3 py-3">类型</th>
                      <th className="px-3 py-3 text-right">新增</th>
                      <th className="px-3 py-3 text-right">删除</th>
                      <th className="px-3 py-3 text-right">任务</th>
                      <th className="px-3 py-3">备注</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900/80 text-slate-300">
                    {evidence.diff_summary.files.map((file) => (
                      <tr key={file.relative_path}>
                        <td className="px-3 py-3 align-top">
                          <div className="font-mono text-xs text-slate-100">
                            {file.relative_path}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {file.in_change_batch ? (
                              <StatusBadge label="批次覆盖" tone="info" />
                            ) : null}
                            {file.in_dirty_workspace ? (
                              <StatusBadge label="工作区变更" tone="warning" />
                            ) : null}
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top">
                          <StatusBadge
                            label={renderDiffKind(file.change_kind)}
                            tone={mapDiffTone(file.change_kind)}
                          />
                        </td>
                        <td className="px-3 py-3 text-right align-top text-emerald-300">
                          +{file.added_line_count}
                        </td>
                        <td className="px-3 py-3 text-right align-top text-rose-300">
                          -{file.deleted_line_count}
                        </td>
                        <td className="px-3 py-3 text-right align-top">
                          {file.linked_task_ids.length}
                        </td>
                        <td className="px-3 py-3 align-top">
                          {file.notes.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {file.notes.map((note) => (
                                <StatusBadge key={note} label={note} tone="neutral" />
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-slate-400">
                当前项目还没有可展示的差异文件。
              </p>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}

function MetricCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function renderDiffKind(kind: string) {
  switch (kind) {
    case "added":
      return "新增";
    case "deleted":
      return "删除";
    case "untracked":
      return "未跟踪";
    default:
      return "修改";
  }
}

function mapDiffTone(kind: string): "success" | "danger" | "warning" | "info" {
  switch (kind) {
    case "added":
      return "success";
    case "deleted":
      return "danger";
    case "untracked":
      return "warning";
    default:
      return "info";
  }
}
