import type { ReactNode } from "react";

export type TaskDetailSurfaceVariant = "card" | "line";

export function DetailField(props: {
  label: string;
  value: ReactNode;
  testId?: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div
      data-testid={props.testId}
      className={
        isLine
          ? "min-w-0 border-l border-[#333333] bg-transparent px-3 py-2"
          : "rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3"
      }
    >
      <div
        data-slot="label"
        className={`text-xs uppercase tracking-[0.18em] ${
          isLine ? "text-zinc-600" : "text-slate-500"
        }`}
      >
        {props.label}
      </div>
      <div
        data-slot="value"
        className={`mt-2 break-words text-sm font-medium ${
          isLine ? "text-zinc-100" : "text-slate-100"
        }`}
      >
        {props.value}
      </div>
    </div>
  );
}
