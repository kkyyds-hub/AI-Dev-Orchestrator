import {
  formatCurrencyUsd,
  formatTokenCount,
} from "../../../lib/format";
import type { BossProjectItem, ProjectDetail } from "../types";
import { ProjectMiniStat } from "./ProjectMiniStat";

export function ProjectDetailStatsGrid(props: {
  project: BossProjectItem | null;
  taskStats: BossProjectItem["task_stats"] | ProjectDetail["task_stats"] | null;
}) {
  const completionRatio =
    props.taskStats && props.taskStats.total_tasks > 0
      ? Math.round(
          (props.taskStats.completed_tasks / props.taskStats.total_tasks) * 100,
        )
      : 0;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <ProjectMiniStat label="完成度" value={`${completionRatio}%`} />
      <ProjectMiniStat
        label="总任务数"
        value={String(props.taskStats?.total_tasks ?? 0)}
      />
      <ProjectMiniStat
        label="执行中 / 待处理"
        value={`${props.taskStats?.running_tasks ?? 0} / ${props.taskStats?.pending_tasks ?? 0}`}
      />
      <ProjectMiniStat
        label="阻塞 / 待人工"
        value={`${props.taskStats?.blocked_tasks ?? 0} / ${props.taskStats?.waiting_human_tasks ?? 0}`}
      />
      <ProjectMiniStat
        label="Prompt Tokens"
        value={
          props.project
            ? formatTokenCount(props.project.prompt_tokens)
            : "需在项目汇总页查看"
        }
      />
      <ProjectMiniStat
        label="预估成本"
        value={
          props.project
            ? formatCurrencyUsd(props.project.estimated_cost)
            : "需在项目汇总页查看"
        }
      />
    </div>
  );
}
