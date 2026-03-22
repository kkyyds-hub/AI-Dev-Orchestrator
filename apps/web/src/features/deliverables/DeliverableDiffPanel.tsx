import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { useDeliverableVersionDiff } from "./hooks";
import { DeliverablePreviewPanel } from "./DeliverablePreviewPanel";
import type { DeliverableDetail, DeliverableSummary } from "./types";

type DeliverableDiffPanelProps = {
  deliverable: DeliverableSummary;
  detail: DeliverableDetail;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableDiffPanel(props: DeliverableDiffPanelProps) {
  const versions = props.detail.versions;
  const [baseVersionNumber, setBaseVersionNumber] = useState<number | null>(null);
  const [targetVersionNumber, setTargetVersionNumber] = useState<number | null>(null);

  useEffect(() => {
    if (!versions.length) {
      setBaseVersionNumber(null);
      setTargetVersionNumber(null);
      return;
    }

    const latest = versions[0]?.version_number ?? null;
    const previous = versions[1]?.version_number ?? latest;
    setTargetVersionNumber(latest);
    setBaseVersionNumber(previous);
  }, [props.detail.id, versions]);

  const baseVersion = useMemo(
    () =>
      versions.find((version) => version.version_number === baseVersionNumber) ?? null,
    [baseVersionNumber, versions],
  );
  const targetVersion = useMemo(
    () =>
      versions.find((version) => version.version_number === targetVersionNumber) ?? null,
    [targetVersionNumber, versions],
  );

  const diffQuery = useDeliverableVersionDiff({
    deliverableId: props.deliverable.id,
    baseVersion: baseVersion?.version_number ?? null,
    targetVersion: targetVersion?.version_number ?? null,
  });

  if (versions.length < 2) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 p-5 text-sm leading-6 text-slate-400">
        当前交付件只有一个版本，至少需要两个版本后才能进行对比。
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-50">版本对比视图</h3>
            <StatusBadge
              label={PROJECT_STAGE_LABELS[props.deliverable.stage] ?? props.deliverable.stage}
              tone="neutral"
            />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            选择同一交付件的两个版本，查看摘要、原文预览和最小行级变更。
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setBaseVersionNumber(targetVersion?.version_number ?? null);
            setTargetVersionNumber(baseVersion?.version_number ?? null);
          }}
          className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:text-slate-50"
        >
          交换基线 / 目标版本
        </button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <label className="block">
          <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">
            Base Version
          </div>
          <select
            value={baseVersionNumber ?? ""}
            onChange={(event) => setBaseVersionNumber(Number(event.target.value))}
            className="w-full rounded-2xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
          >
            {versions.map((version) => (
              <option key={version.id} value={version.version_number}>
                v{version.version_number} · {version.summary}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">
            Target Version
          </div>
          <select
            value={targetVersionNumber ?? ""}
            onChange={(event) => setTargetVersionNumber(Number(event.target.value))}
            className="w-full rounded-2xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
          >
            {versions.map((version) => (
              <option key={version.id} value={version.version_number}>
                v{version.version_number} · {version.summary}
              </option>
            ))}
          </select>
        </label>
      </div>

      {baseVersion && targetVersion ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <DeliverablePreviewPanel
            title={`基线版本 v${baseVersion.version_number}`}
            version={baseVersion}
            tone="warning"
            onNavigateToTask={props.onNavigateToTask}
          />
          <DeliverablePreviewPanel
            title={`目标版本 v${targetVersion.version_number}`}
            version={targetVersion}
            tone="success"
            onNavigateToTask={props.onNavigateToTask}
          />
        </div>
      ) : null}

      {diffQuery.isLoading && !diffQuery.data ? (
        <p className="mt-5 text-sm leading-6 text-slate-400">正在生成版本差异…</p>
      ) : diffQuery.isError ? (
        <p className="mt-5 text-sm leading-6 text-rose-200">
          版本对比加载失败：{diffQuery.error.message}
        </p>
      ) : diffQuery.data ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MiniStat label="新增行" value={String(diffQuery.data.added_line_count)} />
            <MiniStat label="删除行" value={String(diffQuery.data.removed_line_count)} />
            <MiniStat label="未变更行" value={String(diffQuery.data.unchanged_line_count)} />
            <MiniStat
              label="变更块"
              value={String(diffQuery.data.changed_block_count)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <StatusBadge label={`base v${diffQuery.data.base_version.version_number}`} tone="warning" />
            <StatusBadge
              label={`target v${diffQuery.data.target_version.version_number}`}
              tone="success"
            />
            {diffQuery.data.format_changed ? (
              <StatusBadge label="格式已变化" tone="warning" />
            ) : null}
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/80">
            <div className="grid grid-cols-[72px_72px_36px_minmax(0,1fr)] gap-3 border-b border-slate-800 px-4 py-3 text-xs uppercase tracking-[0.18em] text-slate-500">
              <span>Base</span>
              <span>Target</span>
              <span>Diff</span>
              <span>Content</span>
            </div>

            <div className="max-h-[28rem] overflow-auto">
              {diffQuery.data.diff_lines.length ? (
                diffQuery.data.diff_lines.map((line, index) => (
                  <div
                    key={`${line.kind}-${index}-${line.base_line_number ?? "x"}-${line.target_line_number ?? "y"}`}
                    className={`grid grid-cols-[72px_72px_36px_minmax(0,1fr)] gap-3 px-4 py-2 font-mono text-sm ${
                      line.kind === "added"
                        ? "bg-emerald-500/10 text-emerald-100"
                        : line.kind === "removed"
                          ? "bg-rose-500/10 text-rose-100"
                          : "bg-slate-950/20 text-slate-300"
                    }`}
                  >
                    <span className="text-slate-500">
                      {line.base_line_number ?? ""}
                    </span>
                    <span className="text-slate-500">
                      {line.target_line_number ?? ""}
                    </span>
                    <span>
                      {line.kind === "added"
                        ? "+"
                        : line.kind === "removed"
                          ? "-"
                          : "·"}
                    </span>
                    <span className="whitespace-pre-wrap break-words">
                      {line.content || " "}
                    </span>
                  </div>
                ))
              ) : (
                <div className="px-4 py-6 text-sm text-slate-400">
                  两个版本内容一致，没有检测到差异。
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-50">{props.value}</div>
    </div>
  );
}
