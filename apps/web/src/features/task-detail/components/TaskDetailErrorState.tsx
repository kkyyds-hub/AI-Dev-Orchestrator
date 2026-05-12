import type { TaskDetailSurfaceVariant } from "./TaskDetailField";

export function TaskDetailErrorState(props: {
  message: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div
      className={
        isLine
          ? "mt-4 border-l border-rose-700/70 py-2 pl-4 text-sm text-rose-200"
          : "mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100"
      }
    >
      无法加载任务详情：{props.message}
    </div>
  );
}
