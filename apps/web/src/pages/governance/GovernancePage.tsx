import { useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useBossProjectOverview } from "../../features/projects/hooks";
import { ProjectMemoryRoleGovernancePage } from "../../features/projects/pages/ProjectMemoryRoleGovernancePage";
import { buildApprovalsRoute } from "../../lib/approval-route";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import {
  buildGovernanceRoute,
  type GovernanceRouteSection,
} from "../../lib/governance-route";
import { buildTaskRoute } from "../../lib/task-route";

const GOVERNANCE_SECTION_TARGETS: Readonly<Record<GovernanceRouteSection, string>> = {
  memory: "governance-memory-panel",
  search: "governance-memory-search",
  roles: "governance-roles",
  skills: "governance-skills",
  workbench: "governance-role-workbench",
};

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
    <div className="space-y-6">
      {!projectId ? (
        <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
          <div className="max-w-3xl">
            <div className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
              Governance
            </div>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">治理中心</h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              当前顶级 Governance 域已建立正式入口。由于现阶段治理能力仍依赖项目上下文，
              请先通过
              <code className="mx-1 rounded bg-slate-900 px-1.5 py-0.5">projectId</code>
              指定项目，例如：
              <code className="mx-1 rounded bg-slate-900 px-1.5 py-0.5">
                /governance?projectId=your-project-id
              </code>
              。
            </p>
          </div>
        </section>
      ) : null}

      {projectId && !selectedProject && !overviewQuery.isLoading ? (
        <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
          当前 URL 中的项目 ID
          <code className="mx-1 rounded bg-slate-950/40 px-1.5 py-0.5">{projectId}</code>
          未出现在当前项目列表中。你仍然可以继续访问该页面，但建议核对 projectId 是否正确。
        </section>
      ) : null}

      <ProjectMemoryRoleGovernancePage
        selectedProjectId={projectId}
        selectedProjectName={selectedProject?.name ?? null}
        projects={projects}
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
    value === "search" ||
    value === "roles" ||
    value === "skills" ||
    value === "workbench"
  ) {
    return value;
  }

  return null;
}
