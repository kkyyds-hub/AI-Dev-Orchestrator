import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { DeliverableVersionList } from "./DeliverableVersionList";
import { useDeliverableDetail, useProjectDeliverableSnapshot } from "./hooks";
import {
  DELIVERABLE_TYPE_LABELS,
  type DeliverableSummary,
} from "./types";

type DeliverableCenterPageProps = {
  projectId: string | null;
  projectName: string | null;
  requestedDeliverableId?: string | null;
  onRequestedDeliverableHandled?: () => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableCenterPage(props: DeliverableCenterPageProps) {
  const snapshotQuery = useProjectDeliverableSnapshot(props.projectId);
  const deliverables = snapshotQuery.data?.deliverables ?? [];
  const [selectedDeliverableId, setSelectedDeliverableId] = useState<string | null>(null);

  useEffect(() => {
    if (!deliverables.length) {
      setSelectedDeliverableId(null);
      return;
    }

    const requestedStillExists = Boolean(
      props.requestedDeliverableId &&
        deliverables.some(
          (deliverable) => deliverable.id === props.requestedDeliverableId,
        ),
    );
    const selectedStillExists = deliverables.some(
      (deliverable) => deliverable.id === selectedDeliverableId,
    );

    if (requestedStillExists) {
      setSelectedDeliverableId(props.requestedDeliverableId ?? null);
      props.onRequestedDeliverableHandled?.();
      return;
    }

    if (!selectedDeliverableId || !selectedStillExists) {
      setSelectedDeliverableId(deliverables[0].id);
    }
  }, [
    deliverables,
    props.onRequestedDeliverableHandled,
    props.requestedDeliverableId,
    selectedDeliverableId,
  ]);

  const selectedDeliverable = useMemo<DeliverableSummary | null>(
    () =>
      deliverables.find((deliverable) => deliverable.id === selectedDeliverableId) ??
      null,
    [deliverables, selectedDeliverableId],
  );
  const detailQuery = useDeliverableDetail(selectedDeliverable?.id ?? null);

  return (
    <section
      id="deliverable-center"
      data-testid="deliverable-center-section"
      className="scroll-mt-24 space-y-6 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/40"
    >
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day09 Deliverable Repository
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
            交付件仓库与版本快照
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            把 PRD、设计稿、任务拆分、代码计划、验收结论等项目产物纳入统一仓库；同一交付件按版本持续提交，并保留完整快照、来源任务与运行关联。
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <MiniStat label="当前项目" value={props.projectName ?? "未选择项目"} />
          <MiniStat
            label="交付件数量"
            value={String(snapshotQuery.data?.total_deliverables ?? 0)}
          />
          <MiniStat
            label="版本快照数"
            value={String(snapshotQuery.data?.total_versions ?? 0)}
          />
        </div>
      </header>

      {!props.projectId ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          先在老板首页选择一个项目，再查看该项目的交付件仓库与版本快照。
        </div>
      ) : snapshotQuery.isLoading && !snapshotQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
          正在加载交付件仓库...
        </div>
      ) : snapshotQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          交付件仓库加载失败：{snapshotQuery.error.message}
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)]">
          <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-50">交付件清单</h3>
                <p className="mt-1 text-sm text-slate-400">
                  项目当前阶段产生的正式产物与最新版本摘要。
                </p>
              </div>
              <StatusBadge
                label={
                  snapshotQuery.data?.generated_at
                    ? `生成于 ${formatDateTime(snapshotQuery.data.generated_at)}`
                    : "尚未生成"
                }
                tone="neutral"
              />
            </div>

            {deliverables.length > 0 ? (
              <div className="mt-4 space-y-3">
                {deliverables.map((deliverable) => {
                  const isSelected = deliverable.id === selectedDeliverableId;
                  return (
                    <button
                      key={deliverable.id}
                      type="button"
                      onClick={() => setSelectedDeliverableId(deliverable.id)}
                      className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                        isSelected
                          ? "border-cyan-400/60 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-900/70 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-medium text-slate-50">
                          {deliverable.title}
                        </div>
                        <StatusBadge
                          label={DELIVERABLE_TYPE_LABELS[deliverable.type]}
                          tone="info"
                        />
                        <StatusBadge
                          label={
                            PROJECT_STAGE_LABELS[deliverable.stage] ?? deliverable.stage
                          }
                          tone="neutral"
                        />
                      </div>

                      <p className="mt-3 text-sm leading-6 text-slate-300">
                        {deliverable.latest_version.summary}
                      </p>

                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>
                          提交者{" "}
                          {ROLE_CODE_LABELS[deliverable.latest_version.author_role_code] ??
                            deliverable.latest_version.author_role_code}
                        </span>
                        <span>v{deliverable.current_version_number}</span>
                        <span>{deliverable.total_versions} 个快照</span>
                        <span>
                          更新于 {formatDateTime(deliverable.updated_at)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 px-4 py-8 text-sm leading-6 text-slate-400">
                当前项目还没有交付件。可以先通过 Day09 后端接口创建 PRD、设计稿、任务拆分或验收结论等正式产物。
              </div>
            )}
          </section>

          <DeliverableVersionList
            deliverable={selectedDeliverable}
            detail={detailQuery.data ?? null}
            isLoading={detailQuery.isLoading && !detailQuery.data}
            errorMessage={detailQuery.isError ? detailQuery.error.message : null}
            onNavigateToTask={props.onNavigateToTask}
          />
        </div>
      )}
    </section>
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
