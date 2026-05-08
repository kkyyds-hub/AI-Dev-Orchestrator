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
    <section className="rounded-2xl border border-[#333333] bg-[#242424] p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">最新运行列表</h2>
          <p className="text-sm text-zinc-500">
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
        <div className="space-y-3">
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
