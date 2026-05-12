import { StatusBadge } from "../../../components/StatusBadge";
import { buildRunRoute } from "../../../lib/run-route";
import type { RunListItem } from "../types";
import { RunListItemButton } from "./RunListItemButton";
import { RunsListQueryState } from "./RunsListQueryState";

type RunsListPanelProps = {
  isLoading: boolean;
  isError: boolean;
  latestRuns: RunListItem[];
  runId: string | undefined;
  onNavigateToRun: (route: string) => void;
};

export function RunsListPanel(props: RunsListPanelProps) {
  return (
    <section className="min-w-0" data-testid="runs-list-panel">
      <div className="mb-4 flex flex-col gap-2 border-b border-[#333333] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">最新运行列表</h2>
          <p className="mt-1 text-sm leading-6 text-zinc-500">
            基于任务总览聚合最近运行，可直接进入运行详情。
          </p>
        </div>
        <StatusBadge
          label={
            props.isLoading
              ? "加载中"
              : props.isError
                ? "加载失败"
                : "数据已就绪"
          }
          tone={props.isLoading ? "warning" : props.isError ? "danger" : "success"}
        />
      </div>

      {props.isError || !props.latestRuns.length ? (
        <RunsListQueryState
          isError={props.isError}
          hasRuns={props.latestRuns.length > 0}
        />
      ) : (
        <div className="divide-y divide-[#333333] border-y border-[#333333]">
          {props.latestRuns.map((item) => (
            <RunListItemButton
              key={item.run.id}
              item={item}
              selected={item.run.id === props.runId}
              onSelect={() =>
                props.onNavigateToRun(
                  buildRunRoute({
                    runId: item.run.id,
                    taskId: item.task.id,
                    from: "runs",
                  }),
                )
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}
