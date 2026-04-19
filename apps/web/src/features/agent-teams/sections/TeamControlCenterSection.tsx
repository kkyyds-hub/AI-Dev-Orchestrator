import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { RoleModelPolicyEditor } from "../components/RoleModelPolicyEditor";
import { TeamAssemblyEditor } from "../components/TeamAssemblyEditor";
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
      setFeedback("Day13 team assembly / team policy 已保存并回显。");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Save failed.");
    }
  }

  if (!props.projectId) {
    return (
      <section
        id="team-control-center-surface"
        data-testid="team-control-center-surface"
        className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6"
      >
        <h2 className="text-2xl font-semibold text-slate-50">Day13 Team Control Center</h2>
        <p className="mt-2 text-sm text-slate-400">
          先选择项目，再编辑 team assembly / team policy / budget policy。
        </p>
      </section>
    );
  }

  return (
    <section
      id="team-control-center-surface"
      data-testid="team-control-center-surface"
      className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <header className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Day13 Team Assembly</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">
              Team Control Center (Minimum Cross-Layer Slice)
            </h2>
            <p className="mt-2 text-sm text-slate-300">project: {props.projectName ?? props.projectId}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={`team ${draft?.assembly.length ?? 0}`} tone="info" />
            <StatusBadge label={`enabled ${enabledRoleCount}`} tone="success" />
            <StatusBadge
              label={`day14 fields ${snapshotQuery.data?.day14_prerequisites.budget_policy_keys.length ?? 0}`}
              tone="warning"
            />
            <button
              type="button"
              data-testid="team-control-center-save-btn"
              onClick={() => void handleSave()}
              disabled={saveMutation.isPending || !draft}
              className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saveMutation.isPending ? "Saving..." : "Save Team Policy"}
            </button>
          </div>
        </div>
      </header>

      {snapshotQuery.isLoading && !snapshotQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
          Loading team control center snapshot...
        </div>
      ) : null}

      {snapshotQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
          Failed to load team control center: {snapshotQuery.error.message}
        </div>
      ) : null}

      {feedback ? (
        <div
          data-testid="team-control-center-feedback"
          className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100"
        >
          {feedback}
        </div>
      ) : null}

      {draft ? (
        <>
          <TeamAssemblyEditor
            members={draft.assembly}
            onChange={(assembly) =>
              setDraft({
                ...draft,
                assembly,
              })
            }
          />

          <section className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Team Policy</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-slate-400">
                  <span>collaboration_mode</span>
                  <input
                    value={draft.team_policy.collaboration_mode}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        team_policy: {
                          ...draft.team_policy,
                          collaboration_mode: event.target.value,
                        },
                      })
                    }
                    className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-400">
                  <span>intervention_mode</span>
                  <input
                    value={draft.team_policy.intervention_mode}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        team_policy: {
                          ...draft.team_policy,
                          intervention_mode: event.target.value,
                        },
                      })
                    }
                    className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
                  />
                </label>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Budget Policy</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-slate-400">
                  <span>daily_budget_usd</span>
                  <input
                    type="number"
                    value={draft.budget_policy.daily_budget_usd}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        budget_policy: {
                          ...draft.budget_policy,
                          daily_budget_usd: Number(event.target.value || 0),
                        },
                      })
                    }
                    className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-400">
                  <span>per_run_budget_usd</span>
                  <input
                    type="number"
                    value={draft.budget_policy.per_run_budget_usd}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        budget_policy: {
                          ...draft.budget_policy,
                          per_run_budget_usd: Number(event.target.value || 0),
                        },
                      })
                    }
                    className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
                  />
                </label>
              </div>
            </section>
          </section>

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

          {snapshotQuery.data ? (
            <section
              data-testid="team-control-day14-prerequisites"
              className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-300"
            >
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                Day14 Prerequisites
              </div>
              <div className="mt-2">enabled_role_codes: {snapshotQuery.data.day14_prerequisites.enabled_role_codes.join(", ") || "none"}</div>
              <div className="mt-1">budget_policy_keys: {snapshotQuery.data.day14_prerequisites.budget_policy_keys.join(", ") || "none"}</div>
              <div className="mt-1">
                runtime paths: {snapshotQuery.data.runtime_consumption_boundary.role_model_policy_paths.join(" ; ")}
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
