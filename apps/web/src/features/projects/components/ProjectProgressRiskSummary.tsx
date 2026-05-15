import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapProjectRiskTone } from "../../../lib/status";
import type { BossProjectItem } from "../types";
import { PROJECT_RISK_LABELS } from "../types";

export function ProjectProgressRiskSummary(props: {
  project: BossProjectItem | null;
}) {
  if (!props.project) {
    return (
      <section className="border border-[#333333] bg-transparent/60 p-4 text-sm leading-6 text-zinc-400">
        该项目刚创建完成，汇总数据还在刷新；你可以先查看阶段状态、角色协作、任务树和草案来源。
      </section>
    );
  }

  return (
    <>
      <section className="border border-[#333333] bg-transparent/60 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
          最新进度
        </div>
        <p className="mt-3 text-sm leading-6 text-zinc-200">
          {props.project.latest_progress_summary}
        </p>
        <div className="mt-3 text-xs text-zinc-500">
          最近进度时间：{formatDateTime(props.project.latest_progress_at)}
        </div>
      </section>

      <section className="border border-[#333333] bg-transparent/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
            关键风险
          </div>
          <StatusBadge
            label={
              PROJECT_RISK_LABELS[props.project.risk_level] ??
              props.project.risk_level
            }
            tone={mapProjectRiskTone(props.project.risk_level)}
          />
        </div>
        <p className="mt-3 text-sm leading-6 text-zinc-200">
          {props.project.key_risk_summary}
        </p>
        <div className="mt-3 text-xs text-zinc-500">
          重点关注任务 {props.project.attention_task_count} 个，高风险任务{" "}
          {props.project.high_risk_task_count} 个。
        </div>
      </section>
    </>
  );
}
