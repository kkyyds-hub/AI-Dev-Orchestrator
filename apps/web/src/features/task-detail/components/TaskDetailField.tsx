import type { ReactNode } from "react";

export function DetailField(props: { label: string; value: ReactNode; testId?: string }) {
  return (
    <div
      data-testid={props.testId}
      className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3"
    >
      <div data-slot="label" className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div data-slot="value" className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
