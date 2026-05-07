import { StatusBadge } from "../../../components/StatusBadge";
import type { ConsoleTask } from "../../console/types";

export function TaskDetailPanelHeader(props: { selectedTask: ConsoleTask | null }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-50">任务详情</h2>
        <p className="text-sm text-slate-400">
          {props.selectedTask
            ? "查看单任务的结构化上下文、决策历史、质量闸门结果、最小操作入口和运行日志。"
            : "从左侧任务列表中选择一条任务，打开详情侧板。"}
        </p>
      </div>
      {props.selectedTask ? <StatusBadge label="详情已启用" tone="info" /> : null}
    </div>
  );
}
