import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapRunStatusTone, mapTaskStatusTone } from "../../../lib/status";
import { TASK_PRIORITY_LABELS, TASK_RISK_LABELS, TASK_STATUS_LABELS } from "../../projects/types";
import type {
  RoleWorkbenchHandoffItem,
  RoleWorkbenchLane,
  RoleWorkbenchTaskItem,
} from "../types";

type RoleWorkbenchInspectorProps = {
  selectedRole: RoleWorkbenchLane | null;
  selectedTask: RoleWorkbenchTaskItem | null;
  selectedHandoff: RoleWorkbenchHandoffItem | null;
  onNavigateToProject?: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function RoleWorkbenchInspector(props: RoleWorkbenchInspectorProps) {
  return (
    <aside className="space-y-5 border-b border-[#333333] pb-5">
      <RoleWorkbenchInspectorIntro />

      {props.selectedRole ? <SelectedRoleSummary selectedRole={props.selectedRole} /> : null}

      {props.selectedTask ? (
        <SelectedTaskDetail
          selectedTask={props.selectedTask}
          onNavigateToProject={props.onNavigateToProject}
          onNavigateToTask={props.onNavigateToTask}
        />
      ) : (
        <RoleWorkbenchTaskPlaceholder />
      )}

      {props.selectedHandoff ? (
        <SelectedHandoffDetail selectedHandoff={props.selectedHandoff} />
      ) : null}
    </aside>
  );
}

function RoleWorkbenchInspectorIntro() {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">详情面板</div>
      <h3 className="mt-2 text-lg font-semibold text-zinc-50">角色 / 任务 / 运行跳转</h3>
      <p className="mt-2 text-sm leading-6 text-zinc-400">
        从角色视角选中任务后，可以直接跳到项目详情、任务详情和运行详情；未选中对象时，会展示角色列的聚合摘要。
      </p>
    </div>
  );
}

function SelectedRoleSummary(props: { selectedRole: RoleWorkbenchLane }) {
  const { selectedRole } = props;

  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-zinc-50">当前角色</div>
        <StatusBadge
          label={selectedRole.enabled ? "已启用" : "未启用"}
          tone={selectedRole.enabled ? "success" : "neutral"}
        />
      </div>
      <div className="mt-3 text-lg font-semibold text-zinc-100">{selectedRole.role_name}</div>
      <p className="mt-2 text-sm leading-6 text-zinc-300">{selectedRole.role_summary}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="当前任务" value={String(selectedRole.current_task_count)} />
        <MiniInfo label="运行中项" value={String(selectedRole.running_task_count)} />
        <MiniInfo label="阻塞项" value={String(selectedRole.blocked_task_count)} />
        <MiniInfo label="最近交接" value={String(selectedRole.recent_handoff_count)} />
      </div>
    </section>
  );
}

function SelectedTaskDetail(props: {
  selectedTask: RoleWorkbenchTaskItem;
  onNavigateToProject?: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  const { selectedTask } = props;

  return (
    <section className="border-b border-[#333333] pb-5" id="role-workbench-task-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-zinc-50">当前任务</div>
          <div className="mt-2 text-lg font-semibold text-zinc-100">{selectedTask.title}</div>
        </div>
        <StatusBadge
          label={TASK_STATUS_LABELS[selectedTask.status] ?? selectedTask.status}
          tone={mapTaskStatusTone(selectedTask.status)}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {selectedTask.project_name ? <StatusBadge label={selectedTask.project_name} tone="info" /> : null}
        <StatusBadge
          label={`优先级：${TASK_PRIORITY_LABELS[selectedTask.priority] ?? selectedTask.priority}`}
          tone="neutral"
        />
        <StatusBadge
          label={`风险：${TASK_RISK_LABELS[selectedTask.risk_level] ?? selectedTask.risk_level}`}
          tone={selectedTask.risk_level === "high" ? "warning" : "neutral"}
        />
        {selectedTask.latest_run_status ? (
          <StatusBadge
            label={`运行：${selectedTask.latest_run_status}`}
            tone={mapRunStatusTone(selectedTask.latest_run_status)}
          />
        ) : null}
      </div>
      <p className="mt-4 text-sm leading-6 text-zinc-300">{selectedTask.input_summary}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="创建时间" value={formatDateTime(selectedTask.created_at)} />
        <MiniInfo label="更新时间" value={formatDateTime(selectedTask.updated_at)} />
      </div>
      {selectedTask.latest_run_summary ? (
        <div className="mt-4 border-l border-[#333333] pl-3 text-sm leading-6 text-zinc-300">
          {selectedTask.latest_run_summary}
        </div>
      ) : null}
      <SelectedTaskActions
        selectedTask={selectedTask}
        onNavigateToProject={props.onNavigateToProject}
        onNavigateToTask={props.onNavigateToTask}
      />
    </section>
  );
}

function SelectedTaskActions(props: {
  selectedTask: RoleWorkbenchTaskItem;
  onNavigateToProject?: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  const { selectedTask } = props;
  const projectId = selectedTask.project_id;
  const latestRunId = selectedTask.latest_run_id;

  return (
    <div className="mt-4 flex flex-wrap gap-3">
      {projectId && props.onNavigateToProject ? (
        <button
          type="button"
          onClick={() => props.onNavigateToProject?.(projectId)}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
        >
          跳到项目详情
        </button>
      ) : null}
      {props.onNavigateToTask ? (
        <button
          type="button"
          onClick={() => props.onNavigateToTask?.(selectedTask.task_id)}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
        >
          跳到任务详情
        </button>
      ) : null}
      {latestRunId && props.onNavigateToTask ? (
        <button
          type="button"
          onClick={() =>
            props.onNavigateToTask?.(selectedTask.task_id, {
              runId: latestRunId,
            })
          }
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
        >
          跳到运行详情
        </button>
      ) : null}
    </div>
  );
}

function RoleWorkbenchTaskPlaceholder() {
  return (
    <section className="border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
      先从左侧角色列或交接列表里选择一个任务，再查看更细的任务与运行信息。
    </section>
  );
}

function SelectedHandoffDetail(props: { selectedHandoff: RoleWorkbenchHandoffItem }) {
  const { selectedHandoff } = props;

  return (
    <section className="border-b border-[#333333] pb-5" id="role-workbench-run-detail">
      <div className="text-sm font-medium text-zinc-50">当前交接</div>
      <div className="mt-2 text-sm text-zinc-300">{selectedHandoff.message}</div>
      <div className="mt-3 flex flex-wrap gap-2">
        {selectedHandoff.run_status ? (
          <StatusBadge
            label={`运行：${selectedHandoff.run_status}`}
            tone={mapRunStatusTone(selectedHandoff.run_status)}
          />
        ) : null}
        {selectedHandoff.dispatch_status ? (
          <StatusBadge label={selectedHandoff.dispatch_status} tone="neutral" />
        ) : null}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniInfo label="交接时间" value={formatDateTime(selectedHandoff.timestamp)} />
        <MiniInfo label="所属项目" value={selectedHandoff.project_name ?? "未归属项目"} />
      </div>
      {selectedHandoff.handoff_reason ? (
        <div className="mt-4 border-l border-[#333333] pl-3 text-sm leading-6 text-zinc-300">
          {selectedHandoff.handoff_reason}
        </div>
      ) : null}
    </section>
  );
}

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}