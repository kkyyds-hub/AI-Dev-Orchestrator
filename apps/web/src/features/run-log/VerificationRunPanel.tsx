import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useProjectVerificationRuns } from "./hooks";
import type {
  VerificationRun,
  VerificationRunFailureCategory,
  VerificationRunStatus,
} from "./types";

type VerificationRunPanelProps = {
  projectId: string | null;
  changeBatchId?: string | null;
  limit?: number;
};

const STATUS_LABELS: Record<VerificationRunStatus, string> = {
  passed: "已通过",
  failed: "已失败",
  skipped: "已跳过",
};

const FAILURE_CATEGORY_LABELS: Record<VerificationRunFailureCategory, string> = {
  command_failed: "命令失败",
  command_timeout: "命令超时",
  configuration_error: "配置错误",
  precheck_blocked: "预检阻断",
  manually_skipped: "人工跳过",
  workspace_unavailable: "工作区不可用",
};

const TEMPLATE_CATEGORY_LABELS: Record<
  NonNullable<VerificationRun["verification_template_category"]>,
  string
> = {
  build: "Build",
  test: "Test",
  lint: "Lint",
  typecheck: "Typecheck",
};

export function VerificationRunPanel(props: VerificationRunPanelProps) {
  const verificationRunsQuery = useProjectVerificationRuns(
    props.projectId,
    props.changeBatchId ?? null,
    props.limit ?? 10,
  );
  const verificationRuns = verificationRunsQuery.data?.runs ?? [];
  const latestRun = verificationRunsQuery.data?.latest_run ?? null;
  const statusCounts = verificationRunsQuery.data?.status_counts ?? {
    passed: 0,
    failed: 0,
    skipped: 0,
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Day10 验证运行记录
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            将仓库级验证结果沉淀为结构化 <code>VerificationRun</code>，明确关联仓库、
            ChangePlan、ChangeBatch 与命令模板，并只展示最近一次验证结果；本面板不提前进入
            Day11 的差异视图或证据包。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge label={`通过 ${statusCounts.passed}`} tone="success" />
          <StatusBadge label={`失败 ${statusCounts.failed}`} tone="danger" />
          <StatusBadge label={`跳过 ${statusCounts.skipped}`} tone="warning" />
        </div>
      </div>

      {!props.projectId ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          当前还没有绑定可查询验证运行记录的项目仓库。
        </div>
      ) : verificationRunsQuery.isLoading && !verificationRunsQuery.data ? (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4 text-sm text-slate-300">
          正在加载验证运行记录...
        </div>
      ) : verificationRunsQuery.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-4 text-sm text-rose-100">
          验证运行记录加载失败：{verificationRunsQuery.error.message}
        </div>
      ) : verificationRunsQuery.data ? (
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 lg:grid-cols-4">
            <MetricCard
              label="仓库"
              value={
                verificationRunsQuery.data.repository_display_name ??
                verificationRunsQuery.data.repository_root_path
              }
            />
            <MetricCard
              label="记录总数"
              value={String(verificationRunsQuery.data.total_runs)}
            />
            <MetricCard
              label="最近一次批次"
              value={latestRun?.change_batch_title ?? "暂无记录"}
            />
            <MetricCard
              label="最近完成时间"
              value={latestRun ? formatDateTime(latestRun.finished_at) : "暂无记录"}
            />
          </div>

          {latestRun ? (
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-slate-50">
                      最新验证结果
                    </div>
                    <StatusBadge
                      label={STATUS_LABELS[latestRun.status]}
                      tone={mapStatusTone(latestRun.status)}
                    />
                    {latestRun.failure_category ? (
                      <StatusBadge
                        label={FAILURE_CATEGORY_LABELS[latestRun.failure_category]}
                        tone={latestRun.status === "failed" ? "danger" : "warning"}
                      />
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {latestRun.output_summary}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <StatusBadge label={latestRun.change_batch_title} tone="info" />
                  <StatusBadge label={latestRun.change_plan_title} tone="neutral" />
                  {latestRun.verification_template_name ? (
                    <StatusBadge
                      label={latestRun.verification_template_name}
                      tone="warning"
                    />
                  ) : (
                    <StatusBadge label="手动命令" tone="neutral" />
                  )}
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <InfoCard label="任务" value={latestRun.task_title ?? "未记录"} />
                <InfoCard
                  label="命令来源"
                  value={latestRun.command_source === "template" ? "模板命令" : "手动命令"}
                />
                <InfoCard
                  label="模板类别"
                  value={
                    latestRun.verification_template_category
                      ? TEMPLATE_CATEGORY_LABELS[latestRun.verification_template_category]
                      : "未使用模板"
                  }
                />
                <InfoCard
                  label="耗时"
                  value={formatDuration(latestRun.duration_seconds)}
                />
              </div>

              <div className="mt-4 space-y-3 text-sm">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    验证命令
                  </div>
                  <code className="mt-1 block break-all rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-2 text-xs text-cyan-200">
                    {latestRun.command}
                  </code>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    工作目录
                  </div>
                  <p className="mt-1 text-slate-300">{latestRun.working_directory}</p>
                </div>
              </div>
            </div>
          ) : null}

          {verificationRuns.length > 0 ? (
            <div className="space-y-3">
              {verificationRuns.map((run) => (
                <VerificationRunCard key={run.id} run={run} />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
              当前仓库还没有结构化验证运行记录。Day10 只补齐记录与展示，不提前生成差异摘要、
              证据包、回退重做或任何真实 Git 写操作。
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}

function VerificationRunCard(props: { run: VerificationRun }) {
  const templateLabel = props.run.verification_template_name
    ? `${props.run.verification_template_name}${
        props.run.verification_template_category
          ? ` · ${TEMPLATE_CATEGORY_LABELS[props.run.verification_template_category]}`
          : ""
      }`
    : "手动命令";

  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium text-slate-50">
              {props.run.change_batch_title}
            </div>
            <StatusBadge
              label={STATUS_LABELS[props.run.status]}
              tone={mapStatusTone(props.run.status)}
            />
            <StatusBadge label={props.run.change_plan_title} tone="neutral" />
            <StatusBadge label={templateLabel} tone="info" />
            {props.run.failure_category ? (
              <StatusBadge
                label={FAILURE_CATEGORY_LABELS[props.run.failure_category]}
                tone={props.run.status === "failed" ? "danger" : "warning"}
              />
            ) : null}
          </div>

          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.run.output_summary}
          </p>
        </div>

        <div className="text-xs leading-6 text-slate-500">
          <div>完成时间：{formatDateTime(props.run.finished_at)}</div>
          <div>耗时：{formatDuration(props.run.duration_seconds)}</div>
          <div>任务：{props.run.task_title ?? "未记录"}</div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <InfoCard label="仓库" value={props.run.repository_display_name ?? props.run.repository_root_path} />
        <InfoCard label="工作目录" value={props.run.working_directory} />
        <InfoCard
          label="命令来源"
          value={props.run.command_source === "template" ? "模板命令" : "手动命令"}
        />
      </div>

      <div className="mt-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">验证命令</div>
        <code className="mt-1 block break-all rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-cyan-200">
          {props.run.command}
        </code>
      </div>
    </article>
  );
}

function MetricCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}

function InfoCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm text-slate-100">{props.value}</div>
    </div>
  );
}

function mapStatusTone(status: VerificationRunStatus) {
  switch (status) {
    case "passed":
      return "success" as const;
    case "failed":
      return "danger" as const;
    case "skipped":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}

function formatDuration(durationSeconds: number) {
  if (durationSeconds < 1) {
    return `${Math.round(durationSeconds * 1000)} ms`;
  }

  if (durationSeconds < 60) {
    return `${durationSeconds.toFixed(1)} s`;
  }

  const minutes = Math.floor(durationSeconds / 60);
  const seconds = durationSeconds % 60;
  return `${minutes}m ${seconds.toFixed(1)}s`;
}
