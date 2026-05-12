import type { TaskDetailSurfaceVariant } from "./TaskDetailField";

export function TaskDetailLoadingState(props: {
  title: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div
      className={
        isLine
          ? "mt-4 border-y border-[#333333] py-4 text-sm text-zinc-500"
          : "mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300"
      }
    >
      正在加载{" "}
      <span className={`font-medium ${isLine ? "text-zinc-100" : "text-slate-100"}`}>
        {props.title}
      </span>{" "}
      的详情数据。
    </div>
  );
}
