import { useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { mapProjectStatusTone } from "../../lib/status";
import { ProjectDraftPanel } from "./components/ProjectDraftPanel";
import {
  useApplyProjectPlanDraft,
  useCreateProjectPlanDraft,
} from "./hooks";
import type {
  PlannerTaskDraft,
  ProjectDraft,
  ProjectPlanDraft,
} from "./types";
import { PROJECT_STAGE_LABELS, PROJECT_STATUS_LABELS } from "./types";

type ProjectCreateFlowProps = {
  onProjectCreated?: (projectId: string) => void;
};

type EditableProjectPlanDraft = {
  project: ProjectDraft;
  planning_notes: string[];
  tasks: PlannerTaskDraft[];
};

const DEFAULT_PROJECT_DRAFT: ProjectDraft = {
  name: "未命名项目草案",
  summary: "",
  status: "active",
  stage: "planning",
};

export function ProjectCreateFlow(props: ProjectCreateFlowProps) {
  const createDraftMutation = useCreateProjectPlanDraft();
  const applyDraftMutation = useApplyProjectPlanDraft();
  const [brief, setBrief] = useState("");
  const [maxTasks, setMaxTasks] = useState(6);
  const [draft, setDraft] = useState<EditableProjectPlanDraft | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const generateErrorMessage = createDraftMutation.isError
    ? createDraftMutation.error.message
    : null;
  const applyErrorMessage = applyDraftMutation.isError
    ? applyDraftMutation.error.message
    : null;

  const canGenerate = brief.trim().length > 0 && !createDraftMutation.isPending;

  const projectBadgeLabel = useMemo(() => {
    if (!draft?.project) {
      return null;
    }

    return PROJECT_STAGE_LABELS[draft.project.stage] ?? draft.project.stage;
  }, [draft?.project]);

  const handleGenerateDraft = async () => {
    const normalizedBrief = brief.trim();
    if (!normalizedBrief) {
      return;
    }

    try {
      const result = await createDraftMutation.mutateAsync({
        brief: normalizedBrief,
        max_tasks: maxTasks,
      });

      setDraft(toEditableDraft(result));
      setSuccessMessage(null);
    } catch {
      // Error state is exposed through the mutation object.
    }
  };

  const handleProjectChange = (patch: Partial<ProjectDraft>) => {
    setDraft((currentDraft) =>
      currentDraft
        ? {
            ...currentDraft,
            project: {
              ...currentDraft.project,
              ...patch,
            },
          }
        : currentDraft,
    );
  };

  const handleTaskChange = (
    draftId: string,
    patch: Partial<PlannerTaskDraft>,
  ) => {
    setDraft((currentDraft) =>
      currentDraft
        ? {
            ...currentDraft,
            tasks: currentDraft.tasks.map((task) =>
              task.draft_id === draftId ? { ...task, ...patch } : task,
            ),
          }
        : currentDraft,
    );
  };

  const handleResetDraft = () => {
    setDraft(null);
    setSuccessMessage(null);
    applyDraftMutation.reset();
  };

  const handleApplyDraft = async () => {
    if (!draft) {
      return;
    }

    try {
      const result = await applyDraftMutation.mutateAsync({
        project_summary: draft.project.summary,
        project: {
          name: draft.project.name.trim(),
          summary: draft.project.summary.trim(),
          status: draft.project.status,
          stage: draft.project.stage,
        },
        tasks: draft.tasks.map((task) => ({
          draft_id: task.draft_id,
          title: task.title.trim(),
          input_summary: task.input_summary.trim(),
          priority: task.priority,
          acceptance_criteria: task.acceptance_criteria,
          depends_on_draft_ids: task.depends_on_draft_ids,
          risk_level: task.risk_level,
          human_status: task.human_status,
          paused_reason: task.paused_reason,
        })),
      });

      if (result.project) {
        props.onProjectCreated?.(result.project.id);
        setSuccessMessage(
          `已创建项目“${result.project.name}”，并映射 ${result.created_count} 个任务。`,
        );
      } else {
        setSuccessMessage(`已应用草案，并创建 ${result.created_count} 个任务。`);
      }

      setDraft(null);
      setBrief("");
      createDraftMutation.reset();
      applyDraftMutation.reset();
    } catch {
      // Error state is exposed through the mutation object.
    }
  };

  return (
    <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day03 Planner Entry
          </p>
          <h2 className="text-xl font-semibold text-slate-50">
            从 brief 生成项目草案，再映射为项目内任务
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            这里直接复用现有 <code>/planning/drafts</code> 与{" "}
            <code>/planning/apply</code> 链路，只是在 Day03 中补齐项目草案与任务映射，不扩展到审批或阶段守卫。
          </p>
        </div>

        {draft?.project ? (
          <div className="flex flex-wrap gap-2">
            {projectBadgeLabel ? (
              <StatusBadge label={projectBadgeLabel} tone="info" />
            ) : null}
            <StatusBadge
              label={
                PROJECT_STATUS_LABELS[draft.project.status] ?? draft.project.status
              }
              tone={mapProjectStatusTone(draft.project.status)}
            />
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
            项目 brief
          </span>
          <textarea
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            rows={6}
            className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-500"
            placeholder="例如：做一个项目级规划入口，先根据 brief 生成项目草案，再把任务映射到该项目下，并在项目详情中可见任务树。"
          />
        </label>

        <aside className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
              最大任务数
            </span>
            <input
              type="number"
              min={3}
              max={10}
              value={maxTasks}
              onChange={(event) =>
                setMaxTasks(clampTaskCount(Number(event.target.value) || 6))
              }
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
            />
          </label>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm leading-6 text-slate-300">
            生成完成后仍需人工确认：项目名称、摘要、依赖关系和验收标准都可以改；应用后只创建项目/任务，不会一键自动执行。
          </div>

          {generateErrorMessage ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
              生成失败：{generateErrorMessage}
            </div>
          ) : null}

          {successMessage ? (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
              {successMessage}
            </div>
          ) : null}

          <button
            type="button"
            onClick={handleGenerateDraft}
            disabled={!canGenerate}
            className="inline-flex rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-400 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {createDraftMutation.isPending ? "生成中..." : "生成项目草案"}
          </button>
        </aside>
      </div>

      {draft ? (
        <ProjectDraftPanel
          project={draft.project}
          planningNotes={draft.planning_notes}
          tasks={draft.tasks}
          isApplying={applyDraftMutation.isPending}
          applyErrorMessage={applyErrorMessage}
          onProjectChange={handleProjectChange}
          onTaskChange={handleTaskChange}
          onApply={handleApplyDraft}
          onReset={handleResetDraft}
        />
      ) : null}
    </section>
  );
}

function toEditableDraft(result: ProjectPlanDraft): EditableProjectPlanDraft {
  return {
    project: result.project
      ? { ...result.project }
      : {
          ...DEFAULT_PROJECT_DRAFT,
          summary: result.project_summary,
        },
    planning_notes: [...result.planning_notes],
    tasks: result.tasks.map((task) => ({
      ...task,
      acceptance_criteria: [...task.acceptance_criteria],
      depends_on_draft_ids: [...task.depends_on_draft_ids],
    })),
  };
}

function clampTaskCount(value: number) {
  return Math.max(3, Math.min(10, Math.round(value)));
}
