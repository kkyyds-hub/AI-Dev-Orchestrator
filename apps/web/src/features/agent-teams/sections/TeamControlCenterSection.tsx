import { useEffect, useMemo, useState } from "react";

import { RoleModelPolicyEditor } from "../components/RoleModelPolicyEditor";
import { TeamAssemblyEditor } from "../components/TeamAssemblyEditor";
import { TeamControlCenterEmptyState } from "../components/TeamControlCenterEmptyState";
import { TeamControlCenterHeader } from "../components/TeamControlCenterHeader";
import {
  TeamControlCenterErrorState,
  TeamControlCenterFeedback,
  TeamControlCenterLoadingState,
} from "../components/TeamControlCenterQueryState";
import { TeamControlDay14Prerequisites } from "../components/TeamControlDay14Prerequisites";
import { TeamPolicyBudgetGrid } from "../components/TeamPolicyBudgetGrid";
import {
  useTeamControlCenterSnapshot,
  useUpdateTeamControlCenterSnapshot,
} from "../hooks";
import type { TeamControlCenterUpdateRequest } from "../types";

type TeamControlCenterSectionProps = {
  projectId: string | null;
  projectName: string | null;
};

export function TeamControlCenterSection(props: TeamControlCenterSectionProps) {
  const snapshotQuery = useTeamControlCenterSnapshot(props.projectId);
  const saveMutation = useUpdateTeamControlCenterSnapshot(props.projectId);
  const [draft, setDraft] = useState<TeamControlCenterUpdateRequest | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!snapshotQuery.data) {
      return;
    }
    const seededAssembly =
      snapshotQuery.data.assembly.length > 0
        ? snapshotQuery.data.assembly
        : snapshotQuery.data.role_model_policy.role_preferences.map((item) => ({
            role_code: item.role_code,
            enabled: true,
            display_name: item.role_code,
            allocation_percent: 100,
            notes: null,
          }));
    setDraft({
      team_name: snapshotQuery.data.team_name,
      team_mission: snapshotQuery.data.team_mission,
      assembly: seededAssembly,
      team_policy: snapshotQuery.data.team_policy,
      budget_policy: snapshotQuery.data.budget_policy,
      role_model_policy: snapshotQuery.data.role_model_policy,
    });
  }, [snapshotQuery.data]);

  const enabledRoleCount = useMemo(
    () => draft?.assembly.filter((member) => member.enabled).length ?? 0,
    [draft],
  );

  async function handleSave() {
    if (!draft) {
      return;
    }
    try {
      await saveMutation.mutateAsync(draft);
      setFeedback("团队配置已保存。");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "保存失败。");
    }
  }

  if (!props.projectId) {
    return <TeamControlCenterEmptyState />;
  }

  return (
    <section
      id="team-control-center-surface"
      data-testid="team-control-center-surface"
      className="space-y-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-5 shadow-xl shadow-slate-950/30"
    >
      <TeamControlCenterHeader
        projectLabel={props.projectName ?? props.projectId}
        teamSize={draft?.assembly.length ?? 0}
        enabledRoleCount={enabledRoleCount}
        isSaving={saveMutation.isPending}
        canSave={Boolean(draft)}
        onSave={() => void handleSave()}
      />

      {snapshotQuery.isLoading && !snapshotQuery.data ? (
        <TeamControlCenterLoadingState />
      ) : null}

      {snapshotQuery.isError ? (
        <TeamControlCenterErrorState message={snapshotQuery.error.message} />
      ) : null}

      {feedback ? <TeamControlCenterFeedback text={feedback} /> : null}

      {draft ? (
        <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="min-h-0 min-w-0 space-y-4 xl:sticky xl:top-24 xl:max-h-[calc(100vh-10rem)] xl:overflow-y-auto">
            <section className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
              <h3 className="text-sm font-semibold text-slate-100">团队摘要</h3>
              <dl className="mt-3 space-y-3 text-xs">
                <div>
                  <dt className="text-slate-500">团队名称</dt>
                  <dd className="mt-1 max-h-16 overflow-y-auto break-words pr-2 text-sm text-slate-200">{draft.team_name}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">团队使命</dt>
                  <dd className="mt-1 max-h-28 overflow-y-auto break-words pr-2 leading-5 text-slate-300">{draft.team_mission || "未填写"}</dd>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-slate-500">角色</dt>
                    <dd className="mt-1 text-slate-200">{draft.assembly.length}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">已启用</dt>
                    <dd className="mt-1 text-slate-200">{enabledRoleCount}</dd>
                  </div>
                </div>
                <div>
                  <dt className="text-slate-500">单次运行预算</dt>
                  <dd className="mt-1 text-slate-200">
                    ${draft.budget_policy.per_run_budget_usd}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">每日预算</dt>
                  <dd className="mt-1 text-slate-200">
                    ${draft.budget_policy.daily_budget_usd}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">协作模式</dt>
                  <dd className="mt-1 max-h-16 overflow-y-auto break-words pr-2 text-slate-200">
                    {draft.team_policy.collaboration_mode || "未设置"}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">介入模式</dt>
                  <dd className="mt-1 max-h-16 overflow-y-auto break-words pr-2 text-slate-200">
                    {draft.team_policy.intervention_mode || "未设置"}
                  </dd>
                </div>
              </dl>
            </section>

            <nav className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4" aria-label="团队配置目录">
              <h3 className="text-sm font-semibold text-slate-100">配置目录</h3>
              <div className="mt-3 space-y-2 text-xs">
                <a className="block rounded-lg px-2 py-1.5 text-slate-400 transition hover:bg-slate-900/70 hover:text-slate-100" href="#team-basic-settings">
                  基础信息
                </a>
                <a className="block rounded-lg px-2 py-1.5 text-slate-400 transition hover:bg-slate-900/70 hover:text-slate-100" href="#team-role-settings">
                  角色分工
                </a>
                <a className="block rounded-lg px-2 py-1.5 text-slate-400 transition hover:bg-slate-900/70 hover:text-slate-100" href="#team-collaboration-settings">
                  协作策略
                </a>
                <a className="block rounded-lg px-2 py-1.5 text-slate-400 transition hover:bg-slate-900/70 hover:text-slate-100" href="#team-budget-settings">
                  预算策略
                </a>
                <a className="block rounded-lg px-2 py-1.5 text-slate-400 transition hover:bg-slate-900/70 hover:text-slate-100" href="#team-model-settings">
                  模型策略
                </a>
              </div>
            </nav>

            {snapshotQuery.data ? (
              <TeamControlDay14Prerequisites snapshot={snapshotQuery.data} />
            ) : null}
          </aside>

          <div className="min-w-0 space-y-5">
            <section id="team-basic-settings" className="scroll-mt-24 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">基础信息</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  编辑团队名称和使命说明。
                </p>
              </div>
              <div className="mt-4 divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-950/30">
                <label className="grid gap-3 px-4 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
                  <span className="text-slate-300">团队名称</span>
                  <input
                    value={draft.team_name}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        team_name: event.target.value,
                      })
                    }
                    className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
                  />
                </label>
                <label className="grid gap-3 px-4 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
                  <span className="text-slate-300">团队使命</span>
                  <textarea
                    value={draft.team_mission}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        team_mission: event.target.value,
                      })
                    }
                    rows={3}
                    className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-slate-500"
                  />
                </label>
              </div>
            </section>

            <TeamAssemblyEditor
              members={draft.assembly}
              onChange={(assembly) =>
                setDraft({
                  ...draft,
                  assembly,
                })
              }
            />

            <TeamPolicyBudgetGrid
              teamPolicy={draft.team_policy}
              budgetPolicy={draft.budget_policy}
              onChangeTeamPolicy={(team_policy) =>
                setDraft({
                  ...draft,
                  team_policy,
                })
              }
              onChangeBudgetPolicy={(budget_policy) =>
                setDraft({
                  ...draft,
                  budget_policy,
                })
              }
            />

            <RoleModelPolicyEditor
              rolePreferences={draft.role_model_policy.role_preferences}
              stageOverrides={draft.role_model_policy.stage_overrides}
              onChangeRolePreferences={(role_preferences) =>
                setDraft({
                  ...draft,
                  role_model_policy: {
                    ...draft.role_model_policy,
                    role_preferences,
                  },
                })
              }
              onChangeStageOverrides={(stage_overrides) =>
                setDraft({
                  ...draft,
                  role_model_policy: {
                    ...draft.role_model_policy,
                    stage_overrides,
                  },
                })
              }
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}
