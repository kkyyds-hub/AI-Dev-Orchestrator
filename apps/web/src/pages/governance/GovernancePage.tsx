import { useEffect, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useBossProjectOverview } from "../../features/projects/hooks";
import { ProjectMemoryRoleGovernancePage } from "../../features/projects/pages/ProjectMemoryRoleGovernancePage";
import {
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
} from "../../features/projects/types";
import { buildApprovalsRoute } from "../../lib/approval-route";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import {
  buildGovernanceRoute,
  type GovernanceRouteSection,
} from "../../lib/governance-route";
import { buildTaskRoute } from "../../lib/task-route";

const GOVERNANCE_SECTION_TARGETS: Readonly<Record<GovernanceRouteSection, string>> = {
  memory: "governance-memory-panel",
  governance: "governance-policy-panel",
  search: "governance-memory-search",
  roles: "governance-roles",
  skills: "governance-skills",
  workbench: "governance-role-workbench",
};

const GOVERNANCE_SECTION_NAV: ReadonlyArray<{
  id: GovernanceRouteSection;
  label: string;
  description: string;
}> = [
  { id: "memory", label: "记忆", description: "项目沉淀与最新摘要" },
  { id: "governance", label: "治理", description: "记忆治理动作与状态" },
  { id: "search", label: "检索", description: "按关键词查找上下文" },
  { id: "roles", label: "角色", description: "角色目录与项目覆盖" },
  { id: "skills", label: "技能", description: "技能注册与绑定" },
  { id: "workbench", label: "工作台", description: "角色协作与交接" },
];

export function GovernancePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const overviewQuery = useBossProjectOverview();
  const projectId = searchParams.get("projectId");
  const section = normalizeGovernanceSection(searchParams.get("section"));

  const projects = overviewQuery.data?.projects ?? [];
  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId) ?? null,
    [projectId, projects],
  );
  const hasNoProjects =
    !overviewQuery.isLoading && !overviewQuery.isError && projects.length === 0;

  useEffect(() => {
    if (!section) {
      return;
    }

    let cancelled = false;
    let retryTimer: number | null = null;
    const targetId = GOVERNANCE_SECTION_TARGETS[section];

    const tryScroll = (retriesLeft: number) => {
      if (cancelled) {
        return;
      }

      const element = document.getElementById(targetId);
      if (element) {
        element.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        return;
      }

      if (retriesLeft <= 0) {
        return;
      }

      retryTimer = window.setTimeout(() => {
        tryScroll(retriesLeft - 1);
      }, 120);
    };

    requestAnimationFrame(() => {
      tryScroll(12);
    });

    return () => {
      cancelled = true;
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [projectId, section]);

  return (
    <div className="space-y-7">
      <header className="border-b border-[#333333] pb-6" data-testid="governance-page-header">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
              治理中心
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-100">
              页面治理
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-500">
              以项目为边界统一查看记忆、检索、角色、技能与角色工作台；先选项目，再进入对应治理模块操作。
            </p>
          </div>

          <div className="w-full min-w-0 xl:w-[420px]">
            <label htmlFor="governance-project-select" className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-600">
              当前项目
            </label>
            <select
              id="governance-project-select"
              data-testid="governance-project-select"
              value={projectId ?? ""}
              onChange={(event) => {
                const nextProjectId = event.target.value;
                navigate(
                  buildGovernanceRoute({
                    projectId: nextProjectId || null,
                    section,
                  }),
                );
              }}
              className="mt-2 w-full rounded-md border border-[#333333] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500 disabled:cursor-not-allowed disabled:text-zinc-600"
              disabled={overviewQuery.isLoading && !projects.length}
            >
              <option value="" className="bg-[#1f1f1f] text-zinc-100">
                {overviewQuery.isLoading ? "项目加载中..." : "请选择项目"}
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id} className="bg-[#1f1f1f] text-zinc-100">
                  {project.name}（{PROJECT_STAGE_LABELS[project.stage] ?? "未识别阶段"} /{" "}
                  {PROJECT_STATUS_LABELS[project.status] ?? "未识别状态"}）
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs leading-5 text-zinc-600">
              选择项目后，下方会切换到对应项目的记忆、角色、技能与治理工作台。
            </p>
          </div>
        </div>

        <nav
          aria-label="治理模块导航"
          className="mt-6 grid gap-3 border-t border-[#333333] pt-4 sm:grid-cols-2 xl:grid-cols-5"
        >
          {GOVERNANCE_SECTION_NAV.map((item) => {
            const isActive = (section ?? "memory") === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() =>
                  navigate(
                    buildGovernanceRoute({
                      projectId,
                      section: item.id,
                    }),
                  )
                }
                className={`min-w-0 border-l px-3 py-2 text-left transition ${
                  isActive
                    ? "border-zinc-100 text-zinc-100"
                    : "border-[#333333] text-zinc-500 hover:border-zinc-500 hover:text-zinc-200"
                }`}
              >
                <span className="block text-sm font-medium">{item.label}</span>
                <span className="mt-1 block text-xs leading-5 text-zinc-600">
                  {item.description}
                </span>
              </button>
            );
          })}
        </nav>
      </header>

      {!projectId ? (
        <section className="border-y border-dashed border-[#333333] py-6">
          <h2 className="text-base font-semibold text-zinc-100">选择项目后开始治理</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-500">
            当前治理能力需要先选定一个项目。请使用右上角项目选择器，然后进入对应治理模块。
          </p>
          {hasNoProjects ? (
            <Link
              to="/projects"
              className="mt-4 inline-flex border-b border-zinc-500 pb-0.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-200 hover:text-white"
            >
              去项目中心创建项目
            </Link>
          ) : null}
        </section>
      ) : null}

      {projectId && !selectedProject && !overviewQuery.isLoading ? (
        <section className="border-l border-amber-700/70 py-2 pl-4 text-sm leading-6 text-amber-200">
          当前打开的项目不可用。请在右上角重新选择一个可处理项目。
          {hasNoProjects ? (
            <div className="mt-3">
              <Link
                to="/projects"
                className="inline-flex border-b border-amber-300/70 pb-0.5 text-sm font-medium text-amber-100 transition hover:border-amber-100 hover:text-white"
              >
                去项目中心创建项目
              </Link>
            </div>
          ) : null}
        </section>
      ) : null}

      <ProjectMemoryRoleGovernancePage
        selectedProjectId={projectId}
        selectedProjectName={selectedProject?.name ?? null}
        projects={projects}
        defaultTabId={section ?? "memory"}
        onSelectProject={(nextProjectId) =>
          navigate(
            buildGovernanceRoute({
              projectId: nextProjectId,
              section,
            }),
          )
        }
        onNavigateToTask={(taskId, options) =>
          navigate(
            buildTaskRoute({
              taskId,
              runId: options?.runId ?? null,
              from: "project",
              projectId,
            }),
          )
        }
        onNavigateToDeliverable={(input) =>
          navigate(
            buildDeliverablesRoute({
              projectId: input.projectId,
              deliverableId: input.deliverableId,
            }),
          )
        }
        onNavigateToApproval={(input) =>
          navigate(
            buildApprovalsRoute({
              projectId: input.projectId,
              approvalId: input.approvalId,
            }),
          )
        }
      />
    </div>
  );
}

function normalizeGovernanceSection(
  value: string | null,
): GovernanceRouteSection | null {
  if (
    value === "memory" ||
    value === "governance" ||
    value === "search" ||
    value === "roles" ||
    value === "skills" ||
    value === "workbench"
  ) {
    return value;
  }

  return null;
}
