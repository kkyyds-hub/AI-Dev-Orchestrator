import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type { ReviewCluster } from "./types";

type ReviewClustersPanelProps = {
  clusters: ReviewCluster[];
  isLoading: boolean;
  errorMessage?: string | null;
  onSelectCluster?: (cluster: ReviewCluster) => void;
};

export function ReviewClustersPanel({
  clusters,
  isLoading,
  errorMessage,
  onSelectCluster,
}: ReviewClustersPanelProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">失败聚类</h3>
          <p className="mt-1 text-sm text-slate-400">
            按失败类别汇总，快速识别高频问题。
          </p>
        </div>
        {clusters.length > 0 ? (
          <StatusBadge label={`${clusters.length} 个类别`} tone="info" />
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-300">
          正在加载失败聚类…
        </div>
      ) : errorMessage ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载失败聚类：{errorMessage}
        </div>
      ) : clusters.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
          当前还没有失败记录。
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {clusters.map((cluster) => (
            <div
              key={cluster.cluster_key}
              className="cursor-pointer rounded-xl border border-slate-800 bg-slate-900/70 p-4 transition-colors hover:border-slate-700 hover:bg-slate-900"
              onClick={() => onSelectCluster?.(cluster)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="text-sm font-semibold text-slate-100">
                    {cluster.failure_category}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    最近：{formatDateTime(cluster.latest_run_created_at)}
                  </div>
                </div>
                <StatusBadge label={`${cluster.count} 次`} tone="warning" />
              </div>

              {cluster.route_reason_excerpt ? (
                <p className="mt-3 text-xs leading-5 text-slate-400">
                  {cluster.route_reason_excerpt}
                </p>
              ) : null}

              {cluster.sample_task_titles.length > 0 ? (
                <div className="mt-3 space-y-1">
                  {cluster.sample_task_titles.slice(0, 3).map((title, index) => (
                    <div
                      key={`${title}-${index}`}
                      className="truncate text-xs text-slate-500"
                    >
                      • {title}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
