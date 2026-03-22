import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useProjectMemorySnapshot } from "./hooks";
import {
  PROJECT_MEMORY_KIND_LABELS,
  PROJECT_MEMORY_SOURCE_KIND_LABELS,
  PROJECT_STAGE_LABELS,
  type ProjectMemoryCount,
  type ProjectMemoryItem,
} from "./types";
import { ROLE_CODE_LABELS } from "../roles/types";

type ProjectMemoryPanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
};

export function ProjectMemoryPanel(props: ProjectMemoryPanelProps) {
  const snapshotQuery = useProjectMemorySnapshot(props.projectId);

  if (!props.projectId) {
    return (
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">项目记忆</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          先选择一个项目，再查看该项目的关键结论、失败模式、审批意见与交付件摘要沉淀。
        </p>
      </section>
    );
  }

  const projectId = props.projectId;

  return (
    <section className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day14 Project Memory
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
            项目记忆与可检索经验沉淀
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            把运行结论、失败复盘、审批意见与交付件摘要沉淀成结构化项目记忆，供后续检索、复盘和上下文构建继续消费。
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <MiniStat label="当前项目" value={props.projectName ?? "未选择"} />
          <MiniStat
            label="记忆总数"
            value={String(snapshotQuery.data?.total_memories ?? 0)}
          />
          <button
            type="button"
            onClick={() => void snapshotQuery.refetch()}
            className="rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            刷新沉淀
          </button>
        </div>
      </header>

      {snapshotQuery.isLoading && !snapshotQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          正在汇总项目记忆…
        </div>
      ) : snapshotQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          项目记忆加载失败：{snapshotQuery.error.message}
        </div>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-50">记忆概览</h3>
                <p className="mt-1 text-sm text-slate-400">
                  结构化统计当前项目已沉淀的四类经验。
                </p>
              </div>
              <div className="text-sm text-slate-400">
                生成时间：
                {snapshotQuery.data?.generated_at
                  ? formatDateTime(snapshotQuery.data.generated_at)
                  : "—"}
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {(snapshotQuery.data?.counts ?? []).map((count) => (
                <MemoryCountCard key={count.memory_type} item={count} />
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-50">最新沉淀</h3>
                <p className="mt-1 text-sm text-slate-400">
                  展示最近生成的项目记忆，帮助快速回看经验来源与上下游引用入口。
                </p>
              </div>
              <StatusBadge
                label={`${snapshotQuery.data?.latest_items.length ?? 0} 条`}
                tone="neutral"
              />
            </div>

            {(snapshotQuery.data?.latest_items.length ?? 0) > 0 ? (
              <div className="mt-4 space-y-3">
                {snapshotQuery.data?.latest_items.map((item) => (
                  <ProjectMemoryCard
                    key={item.memory_id}
                    item={item}
                    projectId={projectId}
                    onNavigateToTask={props.onNavigateToTask}
                    onNavigateToDeliverable={props.onNavigateToDeliverable}
                    onNavigateToApproval={props.onNavigateToApproval}
                  />
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
                当前项目还没有可展示的记忆记录。可先通过运行、审批或交付件版本形成可沉淀证据，再回来刷新本面板。
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}

function MemoryCountCard(props: { item: ProjectMemoryCount }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {PROJECT_MEMORY_KIND_LABELS[props.item.memory_type]}
      </div>
      <div className="mt-2 text-2xl font-semibold text-slate-50">{props.item.count}</div>
    </div>
  );
}

function ProjectMemoryCard(props: {
  item: ProjectMemoryItem;
  projectId: string;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
}) {
  const tone = mapMemoryTone(props.item.memory_type);

  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={PROJECT_MEMORY_KIND_LABELS[props.item.memory_type]}
            tone={tone}
          />
          <StatusBadge
            label={
              PROJECT_MEMORY_SOURCE_KIND_LABELS[props.item.source_kind] ??
              props.item.source_kind
            }
            tone="neutral"
          />
          {props.item.stage ? (
            <StatusBadge
              label={PROJECT_STAGE_LABELS[props.item.stage] ?? props.item.stage}
              tone="info"
            />
          ) : null}
        </div>

        <div className="text-xs text-slate-500">
          {formatDateTime(props.item.created_at)}
        </div>
      </div>

      <div className="mt-3 text-base font-semibold text-slate-50">
        {props.item.title}
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-300">{props.item.summary}</p>

      {props.item.detail ? (
        <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-900/60 px-3 py-3 text-sm leading-6 text-slate-300">
          {props.item.detail}
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
        {props.item.role_code ? (
          <span>
            角色 {ROLE_CODE_LABELS[props.item.role_code] ?? props.item.role_code}
          </span>
        ) : null}
        {props.item.actor_name ? <span>参与者 {props.item.actor_name}</span> : null}
        <span>来源 {props.item.source_label}</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {props.item.task_id ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(props.item.task_id as string, {
                runId: props.item.run_id,
              })
            }
            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            查看任务 / 运行
          </button>
        ) : null}
        {props.item.deliverable_id ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToDeliverable?.({
                projectId: props.projectId,
                deliverableId: props.item.deliverable_id as string,
              })
            }
            className="rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-600"
          >
            查看交付件
          </button>
        ) : null}
        {props.item.approval_id ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToApproval?.({
                projectId: props.projectId,
                approvalId: props.item.approval_id as string,
              })
            }
            className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-500/20"
          >
            查看审批
          </button>
        ) : null}
      </div>
    </article>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function mapMemoryTone(memoryType: ProjectMemoryItem["memory_type"]) {
  switch (memoryType) {
    case "conclusion":
      return "success" as const;
    case "failure_pattern":
      return "danger" as const;
    case "approval_feedback":
      return "warning" as const;
    case "deliverable_summary":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}
