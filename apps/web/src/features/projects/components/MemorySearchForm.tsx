import type { FormEvent } from "react";

import type { ProjectMemoryKind } from "../types";
import { PROJECT_MEMORY_KIND_LABELS } from "../types";

export const MEMORY_SEARCH_TYPE_OPTIONS: Array<{
  value: "all" | ProjectMemoryKind;
  label: string;
}> = [
  { value: "all", label: "全部类型" },
  { value: "conclusion", label: PROJECT_MEMORY_KIND_LABELS.conclusion },
  { value: "failure_pattern", label: PROJECT_MEMORY_KIND_LABELS.failure_pattern },
  { value: "approval_feedback", label: PROJECT_MEMORY_KIND_LABELS.approval_feedback },
  { value: "deliverable_summary", label: PROJECT_MEMORY_KIND_LABELS.deliverable_summary },
];

export function isMemorySearchType(
  value: string,
): value is "all" | ProjectMemoryKind {
  return MEMORY_SEARCH_TYPE_OPTIONS.some((option) => option.value === value);
}

export function MemorySearchForm(props: {
  draftQuery: string;
  selectedType: "all" | ProjectMemoryKind;
  onDraftQueryChange: (value: string) => void;
  onSelectedTypeChange: (value: "all" | ProjectMemoryKind) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <form className="space-y-4" onSubmit={props.onSubmit}>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_240px_auto]">
          <label className="block text-sm text-slate-300">
            <div className="mb-2 font-medium text-slate-100">关键词</div>
            <input
              value={props.draftQuery}
              onChange={(event) => props.onDraftQueryChange(event.target.value)}
              placeholder="例如：审批意见、失败模式、PRD 摘要、验证结论"
              className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
            />
          </label>

          <label className="block text-sm text-slate-300">
            <div className="mb-2 font-medium text-slate-100">类型过滤</div>
            <select
              value={props.selectedType}
              onChange={(event) => {
                if (isMemorySearchType(event.target.value)) {
                  props.onSelectedTypeChange(event.target.value);
                }
              }}
              className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
            >
              {MEMORY_SEARCH_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end">
            <button
              type="submit"
              className="w-full rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20"
            >
              搜索项目记忆
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}
