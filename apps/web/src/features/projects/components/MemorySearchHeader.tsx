import { StatusBadge } from "../../../components/StatusBadge";

export function MemorySearchHeader(props: {
  projectName: string | null;
  submittedQuery: string;
  resultCount: number;
  totalMatches: number;
}) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
            项目记忆检索
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
            轻量检索工作区
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            在当前项目内快速查找结论、失败模式、审批意见与交付摘要；输入关键词后，下方只展示本次检索的关键结果。
          </p>
          <p className="mt-2 text-xs text-zinc-500">
            当前项目：{props.projectName ?? "未命名项目"}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={props.submittedQuery ? "已有检索" : "等待输入"}
            tone={props.submittedQuery ? "info" : "neutral"}
          />
          <StatusBadge
            label={props.submittedQuery ? String(props.resultCount) + "/" + String(props.totalMatches) + " 条" : "未展示结果"}
            tone="neutral"
          />
        </div>
      </div>
    </header>
  );
}
