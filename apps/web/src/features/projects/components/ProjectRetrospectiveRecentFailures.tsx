import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ProjectRetrospectiveFailureRun } from "../../approvals/types";
import { ProjectRetrospectiveTagList } from "./ProjectRetrospectiveShared";

export function ProjectRetrospectiveRecentFailures(props: {
  recentFailures: ProjectRetrospectiveFailureRun[];
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  return (
    <section className="border-b border-[#333333] pb-5 xl:border-b-0 xl:pb-0">
      <div className="text-lg font-semibold text-zinc-50">最近失败运行</div>
      <div className="mt-1 text-sm leading-6 text-zinc-500">
        这里保留项目内最近的失败 / 取消运行，用于把审批闭环与执行失败复盘串联起来。
      </div>

      {props.recentFailures.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
          {props.recentFailures.map((item) => (
            <article key={item.run_id} className="px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge label={item.run_status} tone="danger" />
                  {item.failure_category ? (
                    <StatusBadge label={item.failure_category} tone="warning" />
                  ) : null}
                </div>
                <div className="text-xs text-zinc-500">
                  {formatDateTime(item.created_at)}
                </div>
              </div>

              <div className="mt-3 text-base font-semibold text-zinc-50">
                {item.task_title ?? item.task_id}
              </div>
              <p className="mt-2 text-sm leading-6 text-zinc-300">{item.headline}</p>
              {item.review ? (
                <div className="mt-3 border-l border-[#333333] pl-3 text-sm leading-6 text-zinc-300">
                  <div className="font-medium text-zinc-100">{item.review.conclusion}</div>
                  <div className="mt-1 text-zinc-400">处置摘要：{item.review.action_summary}</div>
                </div>
              ) : null}
              {item.stages.length > 0 ? (
                <ProjectRetrospectiveTagList
                  title="涉及阶段"
                  items={item.stages}
                  tone="neutral"
                />
              ) : null}

              <div className="mt-4 flex flex-wrap gap-3">
                {props.onNavigateToTask ? (
                  <button
                    type="button"
                    onClick={() =>
                      props.onNavigateToTask?.(item.task_id, { runId: item.run_id })
                    }
                    className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
                  >
                    查看运行
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前项目还没有失败 / 取消运行记录。
        </div>
      )}
    </section>
  );
}
