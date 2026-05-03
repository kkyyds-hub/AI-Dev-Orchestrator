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
      setFeedback("Day13 团队组装 / 团队策略已保存并回显。");
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
      className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <TeamControlCenterHeader
        projectLabel={props.projectName ?? props.projectId}
        teamSize={draft?.assembly.length ?? 0}
        enabledRoleCount={enabledRoleCount}
        day14FieldCount={
          snapshotQuery.data?.day14_prerequisites.budget_policy_keys.length ?? 0
        }
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

          {snapshotQuery.data ? (
            <TeamControlDay14Prerequisites snapshot={snapshotQuery.data} />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
