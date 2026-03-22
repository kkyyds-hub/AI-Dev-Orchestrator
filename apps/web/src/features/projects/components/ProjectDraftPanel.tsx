import { StatusBadge } from "../../../components/StatusBadge";
import {
  mapProjectStatusTone,
  mapTaskStatusTone,
} from "../../../lib/status";
import {
  HUMAN_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_RISK_LABELS,
  TASK_STATUS_LABELS,
} from "../types";

type DraftProject = {
  name: string;
  summary: string;
  status: string;
  stage: string;
};

type DraftTask = {
  draft_id: string;
  title: string;
  input_summary: string;
  priority: string;
  acceptance_criteria: string[];
  depends_on_draft_ids: string[];
  risk_level: string;
  human_status: string;
  paused_reason: string | null;
};

type ProjectDraftPanelProps = {
  project: DraftProject;
  planningNotes: string[];
  tasks: DraftTask[];
  isApplying: boolean;
  applyErrorMessage: string | null;
  onProjectChange: (patch: Partial<DraftProject>) => void;
  onTaskChange: (draftId: string, patch: Partial<DraftTask>) => void;
  onApply: () => void;
  onReset: () => void;
};

export function ProjectDraftPanel(props: ProjectDraftPanelProps) {
  return (
    <section className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            Day03 项目草案
          </p>
          <h3 className="mt-2 text-xl font-semibold text-slate-50">
            项目级规划入口与任务映射
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            先生成项目草案，再人工调整项目名称、任务内容与依赖关系，最后确认应用。此步骤只会创建项目和任务，不会自动执行。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={PROJECT_STAGE_LABELS[props.project.stage] ?? props.project.stage}
            tone="info"
          />
          <StatusBadge
            label={PROJECT_STATUS_LABELS[props.project.status] ?? props.project.status}
            tone={mapProjectStatusTone(props.project.status)}
          />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                项目名称
              </span>
              <input
                value={props.project.name}
                onChange={(event) =>
                  props.onProjectChange({ name: event.target.value })
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                placeholder="输入项目名称"
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  项目阶段
                </span>
                <select
                  value={props.project.stage}
                  onChange={(event) =>
                    props.onProjectChange({ stage: event.target.value })
                  }
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                >
                  {Object.entries(PROJECT_STAGE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-2">
                <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  项目状态
                </span>
                <select
                  value={props.project.status}
                  onChange={(event) =>
                    props.onProjectChange({ status: event.target.value })
                  }
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                >
                  {Object.entries(PROJECT_STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
              项目摘要
            </span>
            <textarea
              value={props.project.summary}
              onChange={(event) =>
                props.onProjectChange({ summary: event.target.value })
              }
              rows={4}
              className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-500"
              placeholder="输入项目摘要"
            />
          </label>
        </div>

        <aside className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              规划备注
            </div>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
              {props.planningNotes.map((note) => (
                <li key={note} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                  {note}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
            当前链路保留人工调整空间；点击“应用草案”前，你可以修改项目摘要、任务标题、验收标准和依赖，不会直接触发 Worker 执行。
          </div>

          {props.applyErrorMessage ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
              应用失败：{props.applyErrorMessage}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={props.onApply}
              disabled={props.isApplying}
              className="inline-flex rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-400 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {props.isApplying ? "应用中..." : "应用草案并创建项目"}
            </button>
            <button
              type="button"
              onClick={props.onReset}
              disabled={props.isApplying}
              className="inline-flex rounded-xl border border-slate-700 bg-slate-950/80 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              丢弃草案
            </button>
          </div>
        </aside>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-lg font-semibold text-slate-50">任务映射草案</h4>
          <span className="text-xs text-slate-500">
            共 {props.tasks.length} 个任务，依赖关系仍可手动调整
          </span>
        </div>

        <div className="space-y-4">
          {props.tasks.map((task, index) => (
            <article
              key={task.draft_id}
              className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    草案 {task.draft_id}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-slate-100">
                      任务 {index + 1}
                    </span>
                    <StatusBadge
                      label={TASK_STATUS_LABELS[task.human_status === "none" ? "pending" : "waiting_human"] ?? "待处理"}
                      tone={mapTaskStatusTone(
                        task.human_status === "none" ? "pending" : "waiting_human",
                      )}
                    />
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 text-xs">
                  <StatusBadge
                    label={TASK_PRIORITY_LABELS[task.priority] ?? task.priority}
                    tone="info"
                  />
                  <StatusBadge
                    label={TASK_RISK_LABELS[task.risk_level] ?? task.risk_level}
                    tone="warning"
                  />
                  <StatusBadge
                    label={HUMAN_STATUS_LABELS[task.human_status] ?? task.human_status}
                    tone={task.human_status === "none" ? "neutral" : "warning"}
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    任务标题
                  </span>
                  <input
                    value={task.title}
                    onChange={(event) =>
                      props.onTaskChange(task.draft_id, { title: event.target.value })
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                  />
                </label>

                <div className="grid gap-4 md:grid-cols-3">
                  <SelectField
                    label="优先级"
                    value={task.priority}
                    options={TASK_PRIORITY_LABELS}
                    onChange={(value) =>
                      props.onTaskChange(task.draft_id, { priority: value })
                    }
                  />
                  <SelectField
                    label="风险等级"
                    value={task.risk_level}
                    options={TASK_RISK_LABELS}
                    onChange={(value) =>
                      props.onTaskChange(task.draft_id, { risk_level: value })
                    }
                  />
                  <SelectField
                    label="人工状态"
                    value={task.human_status}
                    options={HUMAN_STATUS_LABELS}
                    onChange={(value) =>
                      props.onTaskChange(task.draft_id, { human_status: value })
                    }
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    任务摘要
                  </span>
                  <textarea
                    value={task.input_summary}
                    rows={4}
                    onChange={(event) =>
                      props.onTaskChange(task.draft_id, {
                        input_summary: event.target.value,
                      })
                    }
                    className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-500"
                  />
                </label>

                <div className="space-y-4">
                  <label className="space-y-2">
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      验收标准
                    </span>
                    <textarea
                      value={task.acceptance_criteria.join("\n")}
                      rows={4}
                      onChange={(event) =>
                        props.onTaskChange(task.draft_id, {
                          acceptance_criteria: splitMultiline(event.target.value),
                        })
                      }
                      className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-500"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      依赖草案 ID
                    </span>
                    <input
                      value={task.depends_on_draft_ids.join(", ")}
                      onChange={(event) =>
                        props.onTaskChange(task.draft_id, {
                          depends_on_draft_ids: splitCommaValues(event.target.value),
                        })
                      }
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                      placeholder="例如 draft-1, draft-2"
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      暂停原因
                    </span>
                    <input
                      value={task.paused_reason ?? ""}
                      onChange={(event) =>
                        props.onTaskChange(task.draft_id, {
                          paused_reason: normalizeOptionalText(event.target.value),
                        })
                      }
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                      placeholder="无则留空"
                    />
                  </label>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function SelectField(props: {
  label: string;
  value: string;
  options: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2">
      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </span>
      <select
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
      >
        {Object.entries(props.options).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}

function splitMultiline(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitCommaValues(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeOptionalText(value: string) {
  const normalizedValue = value.trim();
  return normalizedValue.length > 0 ? normalizedValue : null;
}
