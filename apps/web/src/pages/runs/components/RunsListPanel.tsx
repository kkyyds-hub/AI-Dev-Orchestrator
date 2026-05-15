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
    <section
      className="flex flex-col overflow-hidden border-r border-[#333333]"
      data-testid="runs-list-panel"
    >
      <div className="shrink-0 border-b border-[#333333] px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">运行列表</h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              {props.latestRuns.length} 条记录
            </p>
          </div>
          <StatusBadge
            label={
              props.isLoading
                ? "加载中"
                : props.isError
                  ? "加载失败"
                  : "就绪"
            }
            tone={props.isLoading ? "warning" : props.isError ? "danger" : "success"}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {props.isError || !props.latestRuns.length ? (
          <div className="px-4 py-6">
            <RunsListQueryState
              isError={props.isError}
              hasRuns={props.latestRuns.length > 0}
            />
          </div>
        ) : (
          <div className="divide-y divide-[#333333]">
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
      </div>
    </section>
  );
}
