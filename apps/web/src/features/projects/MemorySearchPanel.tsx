import { type FormEvent, useEffect, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useProjectMemorySearch } from "./hooks";
import {
  PROJECT_MEMORY_KIND_LABELS,
  PROJECT_MEMORY_SOURCE_KIND_LABELS,
  PROJECT_STAGE_LABELS,
  type ProjectMemoryItem,
  type ProjectMemoryKind,
} from "./types";
import { ROLE_CODE_LABELS } from "../roles/types";

type MemorySearchPanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
};

const MEMORY_TYPE_OPTIONS: Array<{
  value: "all" | ProjectMemoryKind;
  label: string;
}> = [
  { value: "all", label: "全部类型" },
  { value: "conclusion", label: PROJECT_MEMORY_KIND_LABELS.conclusion },
  { value: "failure_pattern", label: PROJECT_MEMORY_KIND_LABELS.failure_pattern },
  { value: "approval_feedback", label: PROJECT_MEMORY_KIND_LABELS.approval_feedback },
  { value: "deliverable_summary", label: PROJECT_MEMORY_KIND_LABELS.deliverable_summary },
];

export function MemorySearchPanel(props: MemorySearchPanelProps) {
  const [draftQuery, setDraftQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selectedType, setSelectedType] = useState<"all" | ProjectMemoryKind>("all");

  useEffect(() => {
    setDraftQuery("");
    setSubmittedQuery("");
    setSelectedType("all");
  }, [props.projectId]);

  const searchQuery = useProjectMemorySearch({
    projectId: props.projectId,
    query: submittedQuery,
    memoryType: selectedType === "all" ? null : selectedType,
    limit: 8,
    enabled: submittedQuery.trim().length > 0,
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmittedQuery(draftQuery.trim());
  };

  if (!props.projectId) {
    return (
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">项目记忆检索</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          选择项目后，可按关键词检索沉淀下来的结论、失败模式、审批意见和交付件摘要。
        </p>
      </section>
    );
  }

  const projectId = props.projectId;

  return (
    <section className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <header className="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day14 Memory Search
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          可检索经验搜索
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          面向当前项目执行最小关键词检索，避免引入更重的长期记忆或复杂向量检索体系。
        </p>
      </header>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_240px_auto]">
            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">关键词</div>
              <input
                value={draftQuery}
                onChange={(event) => setDraftQuery(event.target.value)}
                placeholder="例如：审批意见、失败模式、PRD 摘要、验证结论"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">类型过滤</div>
              <select
                value={selectedType}
                onChange={(event) =>
                  setSelectedType(event.target.value as "all" | ProjectMemoryKind)
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              >
                {MEMORY_TYPE_OPTIONS.map((option) => (
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

      {!submittedQuery ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
          当前项目为 <span className="text-slate-200">{props.projectName ?? "未命名项目"}</span>。
          输入关键词后，将在本项目沉淀的 Day14 记忆中执行最小检索。
        </div>
      ) : searchQuery.isLoading && !searchQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          正在检索项目记忆…
        </div>
      ) : searchQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          项目记忆搜索失败：{searchQuery.error.message}
        </div>
      ) : (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-50">搜索结果</h3>
              <p className="mt-1 text-sm text-slate-400">
                查询 “{submittedQuery}” ，共命中 {searchQuery.data?.total_matches ?? 0} 条项目记忆。
              </p>
            </div>
            <StatusBadge
              label={`${searchQuery.data?.hits.length ?? 0} 条展示`}
              tone="neutral"
            />
          </div>

          {(searchQuery.data?.hits.length ?? 0) > 0 ? (
            <div className="mt-4 space-y-3">
              {searchQuery.data?.hits.map((hit) => (
                <article
                  key={`${hit.item.memory_id}-${hit.score}`}
                  className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge
                        label={PROJECT_MEMORY_KIND_LABELS[hit.item.memory_type]}
                        tone={mapMemoryTone(hit.item.memory_type)}
                      />
                      <StatusBadge
                        label={
                          PROJECT_MEMORY_SOURCE_KIND_LABELS[hit.item.source_kind] ??
                          hit.item.source_kind
                        }
                        tone="neutral"
                      />
                    </div>
                    <div className="text-xs text-slate-500">
                      相关度 {hit.score.toFixed(1)} · {formatDateTime(hit.item.created_at)}
                    </div>
                  </div>

                  <div className="mt-3 text-base font-semibold text-slate-50">
                    {hit.item.title}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {hit.item.summary}
                  </p>

                  {hit.item.detail ? (
                    <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-900/60 px-3 py-3 text-sm leading-6 text-slate-300">
                      {hit.item.detail}
                    </div>
                  ) : null}

                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                    {hit.item.stage ? (
                      <span>
                        阶段 {PROJECT_STAGE_LABELS[hit.item.stage] ?? hit.item.stage}
                      </span>
                    ) : null}
                    {hit.item.role_code ? (
                      <span>
                        角色{" "}
                        {ROLE_CODE_LABELS[hit.item.role_code] ?? hit.item.role_code}
                      </span>
                    ) : null}
                    {hit.item.actor_name ? <span>参与者 {hit.item.actor_name}</span> : null}
                    <span>来源 {hit.item.source_label}</span>
                  </div>

                  {hit.matched_terms.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {hit.matched_terms.map((term) => (
                        <StatusBadge
                          key={`${hit.item.memory_id}-${term}`}
                          label={`命中 ${term}`}
                          tone="info"
                        />
                      ))}
                    </div>
                  ) : null}

                  <div className="mt-4 flex flex-wrap gap-3">
                    {hit.item.task_id ? (
                      <button
                        type="button"
                        onClick={() =>
                          props.onNavigateToTask?.(hit.item.task_id as string, {
                            runId: hit.item.run_id,
                          })
                        }
                        className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
                      >
                        查看任务 / 运行
                      </button>
                    ) : null}
                    {hit.item.deliverable_id ? (
                      <button
                        type="button"
                        onClick={() =>
                          props.onNavigateToDeliverable?.({
                            projectId,
                            deliverableId: hit.item.deliverable_id as string,
                          })
                        }
                        className="rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-600"
                      >
                        查看交付件
                      </button>
                    ) : null}
                    {hit.item.approval_id ? (
                      <button
                        type="button"
                        onClick={() =>
                          props.onNavigateToApproval?.({
                            projectId,
                            approvalId: hit.item.approval_id as string,
                          })
                        }
                        className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-500/20"
                      >
                        查看审批
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
              当前查询没有命中项目记忆。可以换一个更接近交付件、审批意见、失败模式或运行结论的关键词。
            </div>
          )}
        </section>
      )}
    </section>
  );
}

function mapMemoryTone(memoryType: ProjectMemoryItem["memory_type"]) {
  switch (memoryType) {
    case "conclusion":
      return "success" as const;
    case "failure_pattern":
      return "danger" as const;
    case "approval_feedback":
      return "warning" as const;
    case "deliverable_summary":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}
