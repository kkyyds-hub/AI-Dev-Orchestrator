export function TeamControlCenterHeader(props: {
  projectLabel: string;
  teamSize: number;
  enabledRoleCount: number;
  isSaving: boolean;
  canSave: boolean;
  onSave: () => void;
}) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
            团队设置
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
            团队配置与运行策略
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            维护团队角色、协作规则、预算边界和模型档位。
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            当前项目：<span className="text-zinc-200">{props.projectLabel}</span>
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
          <span className="text-xs text-zinc-500">
            {props.teamSize} 个角色 · {props.enabledRoleCount} 个启用
          </span>
          <button
            type="button"
            data-testid="team-control-center-save-btn"
            onClick={props.onSave}
            disabled={props.isSaving || !props.canSave}
            className="rounded border border-[#3a3a3a] bg-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.isSaving ? "保存中..." : "保存设置"}
          </button>
        </div>
      </div>
    </header>
  );
}
