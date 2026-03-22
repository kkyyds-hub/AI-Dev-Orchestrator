import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapRunStatusTone } from "../../../lib/status";
import type { RoleWorkbenchHandoffItem } from "../types";
import { ROLE_CODE_LABELS } from "../types";

type HandoffTimelineProps = {
  handoffs: RoleWorkbenchHandoffItem[];
  selectedHandoffId: string | null;
  onSelectHandoff: (handoff: RoleWorkbenchHandoffItem) => void;
};

export function HandoffTimeline(props: HandoffTimelineProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">
            Handoff Timeline
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">最近角色交接时间线</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            这里直接读取最近运行日志中的 `role_handoff` 结构化事件，用统一的任务 / 运行口径展示“任务是如何在角色之间接力”的。
          </p>
        </div>
        <StatusBadge label={`最近交接 ${props.handoffs.length}`} tone="info" />
      </div>

      {props.handoffs.length ? (
        <div className="mt-4 space-y-3">
          {props.handoffs.map((handoff) => {
            const isSelected = handoff.id === props.selectedHandoffId;
            return (
              <button
                key={handoff.id}
                type="button"
                onClick={() => props.onSelectHandoff(handoff)}
                className={`w-full rounded-2xl border p-4 text-left transition ${
                  isSelected
                    ? "border-cyan-500/40 bg-cyan-500/10"
                    : "border-slate-800 bg-slate-900/70 hover:border-cyan-400/20"
                }`}
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium text-slate-100">{handoff.task_title}</div>
                      {handoff.run_status ? (
                        <StatusBadge
                          label={`运行：${handoff.run_status}`}
                          tone={mapRunStatusTone(handoff.run_status)}
                        />
                      ) : null}
                      {handoff.dispatch_status ? (
                        <StatusBadge label={handoff.dispatch_status} tone="neutral" />
                      ) : null}
                    </div>
                    <div className="mt-2 text-sm text-slate-300">{formatRoleChain(handoff)}</div>
                    <p className="mt-2 text-sm leading-6 text-slate-400">{handoff.message}</p>
                  </div>
                  <div className="text-xs text-slate-500 lg:text-right">
                    <div>{formatDateTime(handoff.timestamp)}</div>
                    <div className="mt-1">{handoff.project_name ?? "未归属项目"}</div>
                  </div>
                </div>
                {handoff.handoff_reason ? (
                  <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-3 text-xs leading-6 text-slate-400">
                    {handoff.handoff_reason}
                  </div>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-800 bg-slate-900/60 px-4 py-8 text-sm text-slate-500">
          当前还没有可展示的角色交接事件。可以先执行一轮带角色分派的任务，再回到这里观察实时接力。
        </div>
      )}
    </section>
  );
}

function formatRoleChain(handoff: RoleWorkbenchHandoffItem): string {
  const chain = [
    handoff.upstream_role_code,
    handoff.owner_role_code,
    handoff.downstream_role_code,
  ].filter((roleCode, index, items): roleCode is string => {
    return Boolean(roleCode) && items.indexOf(roleCode) === index;
  });

  if (!chain.length) {
    return "未识别角色链路";
  }

  return chain.map((roleCode) => ROLE_CODE_LABELS[roleCode] ?? roleCode).join(" → ");
}
