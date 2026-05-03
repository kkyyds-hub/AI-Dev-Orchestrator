import { ProjectTimelineMiniStat } from "./ProjectTimelineMiniStat";

export function ProjectTimelineHeader(props: {
  projectName: string | null;
  totalEvents: number;
  visibleEventCount: number;
}) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V4 Day12 Timeline & Rework Closure
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          项目时间线与回退重做链路
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          以项目为单位汇总计划、验证、审批、失败与重做路径，支持从“时间线事件”反查到 Day12 的回退重做收口视图。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <ProjectTimelineMiniStat
          label="当前项目"
          value={props.projectName ?? "未选择"}
        />
        <ProjectTimelineMiniStat
          label="时间线事件"
          value={String(props.totalEvents)}
        />
        <ProjectTimelineMiniStat
          label="当前筛选结果"
          value={String(props.visibleEventCount)}
        />
      </div>
    </header>
  );
}
