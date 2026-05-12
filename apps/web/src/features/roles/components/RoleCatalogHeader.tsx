import { StatusBadge } from "../../../components/StatusBadge";
import { navigateToProjectOverviewHash } from "../../projects/lib/overviewNavigation";

type RoleCatalogHeaderProps = {
  selectedProjectName: string | null;
  projectRoleConnected: boolean;
};

export function RoleCatalogHeader(props: RoleCatalogHeaderProps) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
            角色目录
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
            角色职责与边界配置
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            把“谁负责什么”沉淀为可维护的角色配置：系统提供最小角色目录，项目可以选择启用哪些角色，并查看/编辑职责边界、输入输出边界和默认 Skill 占位。
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            当前项目：
            <span className="text-zinc-200">
              {props.selectedProjectName ?? "未选择项目"}
            </span>
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
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
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            查看智能体线程
          </button>
          <button
            type="button"
            data-testid="goto-team-control-center-from-role-catalog"
            onClick={scrollToTeamControlCenterSurface}
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            查看团队控制中心
          </button>
        </div>
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
