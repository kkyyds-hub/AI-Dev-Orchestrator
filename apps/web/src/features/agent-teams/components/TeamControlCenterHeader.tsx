export function TeamControlCenterHeader(props: {
  projectLabel: string;
  teamSize: number;
  enabledRoleCount: number;
  isSaving: boolean;
  canSave: boolean;
  onSave: () => void;
}) {
  return (
    <header className="border-b border-[#333333] pb-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-[0.18em] text-slate-500">
            团队设置
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-50">
            团队配置与运行策略
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            当前项目：<span className="text-slate-200">{props.projectLabel}</span>
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
          <span className="text-xs text-slate-500">
            {props.teamSize} 个角色 · {props.enabledRoleCount} 个启用
          </span>
          <button
            type="button"
            data-testid="team-control-center-save-btn"
            onClick={props.onSave}
            disabled={props.isSaving || !props.canSave}
            className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-100 transition hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.isSaving ? "保存中..." : "保存设置"}
          </button>
        </div>
      </div>
    </header>
  );
}
