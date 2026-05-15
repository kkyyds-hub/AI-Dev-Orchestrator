import type { TaskDetailSurfaceVariant } from "./TaskDetailField";

export function TaskDetailEmptyState(props: { surfaceVariant?: TaskDetailSurfaceVariant }) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div
      className={
        isLine
          ? "mt-4 border-y border-dashed border-[#333333] py-6 text-sm text-zinc-500"
          : "mt-4 rounded-xl border border-dashed border-[#333333] bg-transparent p-4 text-sm text-zinc-400"
      }
    >
      从左侧任务列表中选择一条任务，这里会展示任务基础信息、最新运行、质量闸门结果和结构化日志事件。
    </div>
  );
}
