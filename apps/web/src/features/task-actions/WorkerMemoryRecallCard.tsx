import type { WorkerRunOnceResponse } from "./types";

type WorkerMemoryRecallCardProps = Pick<
  WorkerRunOnceResponse,
  | "project_memory_enabled"
  | "project_memory_query_text"
  | "project_memory_item_count"
  | "project_memory_context_summary"
>;

export function WorkerMemoryRecallCard(props: WorkerMemoryRecallCardProps) {
  if (!props.project_memory_enabled) {
    return null;
  }

  return (
    <div className="mt-3 rounded-xl border border-violet-500/20 bg-violet-500/5 p-3">
      <div className="text-xs uppercase tracking-[0.2em] text-violet-200">
        Project Memory Recall
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <RecallInfo label="已接通" value={props.project_memory_enabled ? "是" : "否"} />
        <RecallInfo
          label="召回条数"
          value={String(props.project_memory_item_count ?? 0)}
        />
      </div>
      {props.project_memory_query_text ? (
        <p className="mt-3 text-sm leading-6 text-slate-300">
          查询：{props.project_memory_query_text}
        </p>
      ) : null}
      {props.project_memory_context_summary ? (
        <p className="mt-2 text-sm leading-6 text-slate-300">
          {props.project_memory_context_summary}
        </p>
      ) : null}
    </div>
  );
}

function RecallInfo(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
