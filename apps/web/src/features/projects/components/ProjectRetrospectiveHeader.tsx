import type { ProjectRetrospectiveSummary } from "../../approvals/types";
import { ProjectRetrospectiveStat } from "./ProjectRetrospectiveShared";

export function ProjectRetrospectiveHeader(props: {
  projectName: string | null;
  summary: ProjectRetrospectiveSummary | null;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          项目复盘
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50">
          审批回退重做与项目复盘收口
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          汇总项目内的关键审批失败、返工状态与失败运行复盘，帮助你确认“提交 - 审批 - 驳回/通过 - 重做”闭环是否已经真正打通。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ProjectRetrospectiveStat
          label="当前项目"
          value={props.projectName ?? "未选择"}
        />
        <ProjectRetrospectiveStat
          label="审批返工回路"
          value={String(props.summary?.negative_approval_cycles ?? 0)}
        />
        <ProjectRetrospectiveStat
          label="待收口返工"
          value={String(props.summary?.open_rework_cycles ?? 0)}
        />
        <ProjectRetrospectiveStat
          label="失败复盘"
          value={String(props.summary?.total_failure_reviews ?? 0)}
        />
      </div>
    </header>
  );
}
