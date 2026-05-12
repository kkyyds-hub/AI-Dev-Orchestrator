import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ProjectRetrospectiveFailureCluster } from "../../approvals/types";
import { ProjectRetrospectiveTagList } from "./ProjectRetrospectiveShared";

export function ProjectRetrospectiveFailureClusters(props: {
  failureClusters: ProjectRetrospectiveFailureCluster[];
}) {
  return (
    <section className="border-b border-[#333333] pb-5 xl:border-b-0 xl:pb-0">
      <div className="text-lg font-semibold text-zinc-50">失败复盘聚类</div>
      <div className="mt-1 text-sm leading-6 text-zinc-500">
        结合 V2 的失败复盘记录，快速看到当前项目最常见的失败类别与样例任务。
      </div>

      {props.failureClusters.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
          {props.failureClusters.map((cluster) => (
            <article key={cluster.cluster_key} className="px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge label={cluster.failure_category} tone="danger" />
                  <StatusBadge label={`${cluster.count} 次`} tone="warning" />
                </div>
                <div className="text-xs text-zinc-500">
                  最新时间：{formatDateTime(cluster.latest_run_created_at)}
                </div>
              </div>
              {cluster.route_reason_excerpt ? (
                <p className="mt-3 text-sm leading-6 text-zinc-300">
                  {cluster.route_reason_excerpt}
                </p>
              ) : null}
              {cluster.sample_task_titles.length > 0 ? (
                <ProjectRetrospectiveTagList
                  title="样例任务"
                  items={cluster.sample_task_titles}
                  tone="neutral"
                />
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前项目还没有落盘的失败复盘记录。
        </div>
      )}
    </section>
  );
}
