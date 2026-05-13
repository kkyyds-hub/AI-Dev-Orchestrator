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
    <section aria-label="搜索控制条">
      <form onSubmit={props.onSubmit}>
        <div className="grid gap-3 rounded-sm border border-[#333333] p-3 xl:grid-cols-[minmax(0,1fr)_220px_auto] xl:items-end">
          <label className="block text-sm text-zinc-300">
            <span className="mb-2 block text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
              关键词
            </span>
            <input
              value={props.draftQuery}
              onChange={(event) => props.onDraftQueryChange(event.target.value)}
              placeholder="输入审批意见、失败模式、交付摘要或验证结论"
              className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-700 focus:border-zinc-500"
            />
          </label>

          <label className="block text-sm text-zinc-300">
            <span className="mb-2 block text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
              类型
            </span>
            <select
              value={props.selectedType}
              onChange={(event) => {
                if (isMemorySearchType(event.target.value)) {
                  props.onSelectedTypeChange(event.target.value);
                }
              }}
              className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
            >
              {MEMORY_SEARCH_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value} className="bg-[#1f1f1f] text-zinc-100">
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <button
            type="submit"
            className="rounded border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-white"
          >
            执行检索
          </button>
        </div>
        <p className="mt-2 text-xs leading-5 text-zinc-600">
          控制条仅限定关键词和类型；检索范围始终保持在当前项目记忆内。
        </p>
      </form>
    </section>
  );
}
