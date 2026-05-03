import { StatusBadge } from "../../../components/StatusBadge";

export function TeamControlCenterHeader(props: {
  projectLabel: string;
  teamSize: number;
  enabledRoleCount: number;
  day14FieldCount: number;
  isSaving: boolean;
  canSave: boolean;
  onSave: () => void;
}) {
  return (
    <header className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Day13 团队组装</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-50">
            团队控制中心（最小跨层切片）
          </h2>
          <p className="mt-2 text-sm text-slate-300">项目：{props.projectLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label={`团队 ${props.teamSize}`} tone="info" />
          <StatusBadge label={`已启用 ${props.enabledRoleCount}`} tone="success" />
          <StatusBadge label={`Day14 字段 ${props.day14FieldCount}`} tone="warning" />
          <button
            type="button"
            data-testid="team-control-center-save-btn"
            onClick={props.onSave}
            disabled={props.isSaving || !props.canSave}
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.isSaving ? "保存中..." : "保存团队策略"}
          </button>
        </div>
      </div>
    </header>
  );
}
