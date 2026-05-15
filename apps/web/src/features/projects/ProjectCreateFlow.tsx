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
    <section className="space-y-5 border-b border-[#333333] pb-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            快速录入
          </p>
          <h2 className="text-xl font-semibold text-zinc-100">
            创建项目草案
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-zinc-500">
            输入项目需求说明，自动生成包含项目信息与任务映射的草案，确认后可一键创建项目和任务。
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

      <div className="grid gap-5">
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            项目需求说明
          </span>
          <textarea
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            rows={5}
            className="w-full rounded-xl border border-[#3a3a3a] bg-transparent px-3 py-3 text-sm leading-6 text-zinc-100 outline-none transition focus:border-zinc-500"
            placeholder="例如：做一个项目级规划入口，先根据 brief 生成项目草案，再把任务映射到该项目下，并在项目详情中可见任务树。"
          />
        </label>

        <aside className="space-y-4 border-l border-[#333333] pl-4">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.2em] text-zinc-600">
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
              className="w-full rounded-lg border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
            />
          </label>

          <div className="border-l-2 border-l-[#555555] py-2 pl-4 text-sm leading-6 text-zinc-400">
            生成完成后仍需人工确认：项目名称、摘要、依赖关系和验收标准都可以改；应用后只创建项目/任务，不会一键自动执行。
          </div>

          {generateErrorMessage ? (
            <div className="border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
              生成失败：{generateErrorMessage}
            </div>
          ) : null}

          {successMessage ? (
            <div className="border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
              {successMessage}
            </div>
          ) : null}

          <button
            type="button"
            onClick={handleGenerateDraft}
            disabled={!canGenerate}
            className="inline-flex rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:opacity-60"
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
