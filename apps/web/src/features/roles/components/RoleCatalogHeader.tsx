import { StatusBadge } from "../../../components/StatusBadge";
import { navigateToProjectOverviewHash } from "../../projects/lib/overviewNavigation";

type RoleCatalogHeaderProps = {
  selectedProjectName: string | null;
  projectRoleConnected: boolean;
};

export function RoleCatalogHeader(props: RoleCatalogHeaderProps) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day05 Role Catalog
        </p>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-50">
          角色目录与身份配置模型
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          Day05 把“谁负责什么”变成正式配置对象：系统提供最小角色目录，项目可以选择启用哪些角色，并查看/编辑职责边界、输入输出边界和默认 Skill 占位。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <StatusBadge
          label={
            props.selectedProjectName
              ? `当前项目：${props.selectedProjectName}`
              : "当前未选项目"
          }
          tone={props.selectedProjectName ? "info" : "neutral"}
        />
        <StatusBadge
          label={
            props.projectRoleConnected ? "项目角色配置已接入" : "系统目录只读模式"
          }
          tone={props.projectRoleConnected ? "success" : "warning"}
        />
        <button
          type="button"
          data-testid="goto-agent-thread-from-role-catalog"
          onClick={scrollToAgentThreadControlSurface}
          className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
        >
          Open Agent Thread
        </button>
        <button
          type="button"
          data-testid="goto-team-control-center-from-role-catalog"
          onClick={scrollToTeamControlCenterSurface}
          className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-100 transition hover:bg-emerald-500/20"
        >
          Open Team Control
        </button>
      </div>
    </header>
  );
}

function scrollToAgentThreadControlSurface() {
  navigateToProjectOverviewHash({
    view: "collaboration-control",
    targetId: "agent-thread-control-surface",
  });
}

function scrollToTeamControlCenterSurface() {
  navigateToProjectOverviewHash({
    view: "collaboration-control",
    targetId: "team-control-center-surface",
  });
}
