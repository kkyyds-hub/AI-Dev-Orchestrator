import { useQuery } from "@tanstack/react-query";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { requestJson } from "../../lib/http";
import { useProjectChangeEvidence } from "../deliverables/hooks";

type DiffSummaryPageProps = {
  projectId: string | null;
};

type RepositoryDay15FlowStep = {
  key: string;
  title: string;
  status: "completed" | "pending" | "blocked";
  summary: string;
  evidence_key: string | null;
};

type RepositoryDay15Flow = {
  overall_status: "in_progress" | "blocked" | "ready_for_review";
  completed_step_count: number;
  total_step_count: number;
  blocked_step_count: number;
  selected_change_batch_title: string | null;
  steps: RepositoryDay15FlowStep[];
};

function useRepositoryDay15Flow(projectId: string | null) {
  return useQuery({
    queryKey: ["repository-day15-flow", projectId],
    queryFn: () =>
      requestJson<RepositoryDay15Flow>(`/repositories/projects/${projectId}/day15-flow`),
    enabled: Boolean(projectId),
  });
}

export function DiffSummaryPage(props: DiffSummaryPageProps) {
  const evidenceQuery = useProjectChangeEvidence(props.projectId);
  const flowQuery = useRepositoryDay15Flow(props.projectId);
  const evidence = evidenceQuery.data ?? null;
  const flow = flowQuery.data ?? null;
  const evidenceStep = flow?.steps.find((item) => item.key === "diff_evidence") ?? null;

  return (
    <section className="space-y-4 border-y border-[#333333] py-5">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            代码差异
          </div>
          <h3 className="mt-2 text-lg font-semibold text-zinc-100">
            代码差异
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            按文件维度汇总当前仓库差异，展示增删改统计、关键文件和提交前确认信息。
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

      {flow ? (
        <div className="border-l border-[#333333] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={`提交前状态：${renderDay15FlowLabel(flow.overall_status)}`}
              tone={mapDay15FlowTone(flow.overall_status)}
            />
            <StatusBadge
              label={`完成 ${flow.completed_step_count}/${flow.total_step_count}`}
              tone="info"
            />
            <StatusBadge
              label={`阻断 ${flow.blocked_step_count}`}
              tone={flow.blocked_step_count > 0 ? "danger" : "success"}
            />
            {flow.selected_change_batch_title ? (
              <StatusBadge label={`批次 ${flow.selected_change_batch_title}`} tone="neutral" />
            ) : null}
          </div>
          {evidenceStep ? (
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              证据包状态：{renderStepLabel(evidenceStep.status)}；{evidenceStep.summary}
            </p>
          ) : null}
        </div>
      ) : flowQuery.isLoading && props.projectId ? (
        <div className="text-sm text-zinc-500">正在读取提交前状态...</div>
      ) : flowQuery.isError ? (
        <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          提交前状态读取失败：{flowQuery.error.message}
        </div>
      ) : null}

      {!props.projectId ? (
        <div className="border-l border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-500">
          先选择一个项目，再查看代码差异。
        </div>
      ) : evidenceQuery.isLoading && !evidence ? (
        <div className="border-l border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-500">
          正在读取仓库差异摘要...
        </div>
      ) : evidenceQuery.isError ? (
        <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          代码差异加载失败：{evidenceQuery.error.message}
        </div>
      ) : evidence ? (
        <>
          <div className="flex flex-wrap gap-3 text-xs text-zinc-400">
            <span>基线：{evidence.diff_summary.baseline_label}</span>
            <span>目标：{evidence.diff_summary.target_label}</span>
            <span>生成时间：{formatDateTime(evidence.diff_summary.generated_at)}</span>
            {evidence.selected_change_batch_title ? (
              <span>批次：{evidence.selected_change_batch_title}</span>
            ) : null}
          </div>

          {evidence.diff_summary.note ? (
            <div className="border-l border-amber-500/50 px-4 py-3 text-sm leading-6 text-amber-100">
              {evidence.diff_summary.note}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
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

          <section className="border-y border-[#333333] py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-zinc-100">关键文件列表</h4>
                <p className="mt-1 text-sm leading-6 text-zinc-400">
                  优先展示变更批次覆盖文件，以及删除、未跟踪等需要关注的文件。
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
                    label={`${renderDiffKind(file.change_kind)} \u00b7 ${file.relative_path}`}
                    tone={mapDiffTone(file.change_kind)}
                  />
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-zinc-400">
                当前范围内没有可单独高亮的关键文件。
              </p>
            )}
          </section>

          <section className="border-y border-[#333333] py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-zinc-100">按文件聚合的差异统计</h4>
                <p className="mt-1 text-sm leading-6 text-zinc-400">
                  展示当前范围内的差异摘要，便于提交前确认文件影响。
                </p>
              </div>
              <StatusBadge
                label={`${evidence.diff_summary.files.length} 行`}
                tone="neutral"
              />
            </div>

            {evidence.diff_summary.files.length > 0 ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full divide-y divide-[#333333] text-sm">
                  <thead className="text-left text-xs uppercase tracking-[0.18em] text-zinc-600">
                    <tr>
                      <th className="px-3 py-3">文件</th>
                      <th className="px-3 py-3">类型</th>
                      <th className="px-3 py-3 text-right">新增</th>
                      <th className="px-3 py-3 text-right">删除</th>
                      <th className="px-3 py-3 text-right">任务</th>
                      <th className="px-3 py-3">备注</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#333333] text-zinc-400">
                    {evidence.diff_summary.files.map((file) => (
                      <tr key={file.relative_path}>
                        <td className="px-3 py-3 align-top">
                          <div className="font-mono text-xs text-zinc-100">
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
                            <span className="text-zinc-500">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-zinc-400">
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
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.18em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
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

function mapDay15FlowTone(
  status: RepositoryDay15Flow["overall_status"],
): "success" | "warning" | "danger" {
  if (status === "ready_for_review") {
    return "success";
  }
  if (status === "blocked") {
    return "danger";
  }
  return "warning";
}

function renderDay15FlowLabel(status: RepositoryDay15Flow["overall_status"]) {
  switch (status) {
    case "ready_for_review":
      return "闭环可审阅";
    case "blocked":
      return "闭环阻断";
    default:
      return "闭环进行中";
  }
}

function renderStepLabel(status: RepositoryDay15FlowStep["status"]) {
  if (status === "completed") {
    return "已完成";
  }
  if (status === "blocked") {
    return "阻断";
  }
  return "待补齐";
}
