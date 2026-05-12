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
    <section className="border-b border-[#333333] pb-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
            角色交接
          </div>
          <h3 className="mt-2 text-base font-semibold text-zinc-50">最近角色交接</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            按统一的任务和运行口径展示角色之间的接力过程，便于查看最近协作流转。
          </p>
        </div>
        <div className="text-xs text-zinc-500">最近交接 {props.handoffs.length}</div>
      </div>

      {props.handoffs.length ? (
        <div className="mt-3 divide-y divide-[#333333] border-y border-[#333333]">
          {props.handoffs.map((handoff) => {
            const isSelected = handoff.id === props.selectedHandoffId;
            return (
              <button
                key={handoff.id}
                type="button"
                onClick={() => props.onSelectHandoff(handoff)}
                className={`w-full px-3 py-4 text-left transition ${isSelected ? "bg-white/[0.035]" : "hover:bg-white/[0.02]"}`}
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium text-zinc-100">{handoff.task_title}</div>
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
                    <div className="mt-2 text-sm text-zinc-300">{formatRoleChain(handoff)}</div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">{handoff.message}</p>
                  </div>
                  <div className="text-xs text-zinc-500 lg:text-right">
                    <div>{formatDateTime(handoff.timestamp)}</div>
                    <div className="mt-1">{handoff.project_name ?? "未归属项目"}</div>
                  </div>
                </div>
                {handoff.handoff_reason ? (
                  <div className="mt-3 border-l border-[#333333] pl-3 text-xs leading-6 text-zinc-500">
                    {handoff.handoff_reason}
                  </div>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-7 text-sm leading-6 text-zinc-500">
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
