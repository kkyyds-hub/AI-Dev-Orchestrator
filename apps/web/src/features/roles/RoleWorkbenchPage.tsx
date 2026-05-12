import { HandoffTimeline } from "./components/HandoffTimeline";
import { RoleLaneBoard } from "./components/RoleLaneBoard";
import { RoleWorkbenchHeader } from "./components/RoleWorkbenchHeader";
import { RoleWorkbenchInspector } from "./components/RoleWorkbenchInspector";
import { RoleWorkbenchMetricGrid } from "./components/RoleWorkbenchMetricGrid";
import { RoleWorkbenchQueryState } from "./components/RoleWorkbenchQueryState";
import {
  RoleWorkbenchScopeSelector,
  type RoleWorkbenchProjectOption,
} from "./components/RoleWorkbenchScopeSelector";
import { useRoleWorkbenchSnapshot } from "./hooks";
import { useRoleWorkbenchSelection } from "./hooks/useRoleWorkbenchSelection";
import type { RoleWorkbenchHandoffItem, RoleWorkbenchLane } from "./types";

type RoleWorkbenchPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
  projectOptions: RoleWorkbenchProjectOption[];
  onNavigateToProject?: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

const EMPTY_LANES: RoleWorkbenchLane[] = [];
const EMPTY_HANDOFFS: RoleWorkbenchHandoffItem[] = [];

export function RoleWorkbenchPage(props: RoleWorkbenchPageProps) {
  const workbenchQuery = useRoleWorkbenchSnapshot(props.selectedProjectId);
  const snapshot = workbenchQuery.data ?? null;
  const lanes = snapshot?.lanes ?? EMPTY_LANES;
  const handoffs = snapshot?.recent_handoffs ?? EMPTY_HANDOFFS;
  const selection = useRoleWorkbenchSelection(lanes, handoffs);

  return (
    <section className="space-y-5 border-b border-[#333333] pb-6">
      <RoleWorkbenchHeader
        selectedProjectName={props.selectedProjectName}
        scopeLabel={snapshot?.scope_label ?? null}
        budget={snapshot?.budget ?? null}
        generatedAt={snapshot?.generated_at ?? null}
      />

      <RoleWorkbenchScopeSelector
        selectedProjectId={props.selectedProjectId}
        selectedProjectName={props.selectedProjectName}
        projectOptions={props.projectOptions}
        onNavigateToProject={props.onNavigateToProject}
      />

      <RoleWorkbenchQueryState
        isLoading={workbenchQuery.isLoading && !snapshot}
        isError={workbenchQuery.isError}
        errorMessage={workbenchQuery.error?.message ?? null}
      />

      {snapshot ? (
        <>
          <RoleWorkbenchMetricGrid snapshot={snapshot} />

          <RoleLaneBoard
            lanes={lanes}
            selectedRoleCode={selection.selectedRoleCode}
            selectedTaskId={selection.selectedTaskId}
            onSelectRole={selection.setSelectedRoleCode}
            onSelectTask={selection.selectTask}
            onSelectHandoff={selection.selectHandoff}
          />

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.9fr)]">
            <HandoffTimeline
              handoffs={handoffs}
              selectedHandoffId={selection.selectedHandoffId}
              onSelectHandoff={selection.selectHandoff}
            />

            <RoleWorkbenchInspector
              selectedRole={selection.selectedRole}
              selectedTask={selection.selectedTask}
              selectedHandoff={selection.selectedHandoff}
              onNavigateToProject={props.onNavigateToProject}
              onNavigateToTask={props.onNavigateToTask}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}
