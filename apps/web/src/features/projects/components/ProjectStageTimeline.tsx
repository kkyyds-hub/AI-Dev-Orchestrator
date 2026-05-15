import { useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { BadgeTone } from "../../../lib/status";
import type { ProjectDetail } from "../types";
import {
  PROJECT_STAGE_HISTORY_OUTCOME_LABELS,
  PROJECT_STAGE_LABELS,
} from "../types";

type StageActionFeedback = {
  tone: BadgeTone;
  text: string;
};

type ProjectStageTimelineProps = {
  detail: ProjectDetail | null;
  isAdvancing: boolean;
  actionFeedback: StageActionFeedback | null;
  onAdvanceStage: (note: string | null) => Promise<void> | void;
};

export function ProjectStageTimeline(props: ProjectStageTimelineProps) {
  const [note, setNote] = useState("");
  const guard = props.detail?.stage_guard ?? null;
  const timelineEntries = useMemo(
    () => [...(props.detail?.stage_timeline ?? [])].reverse(),
    [props.detail?.stage_timeline],
  );
  const hasNextStage = guard?.target_stage !== null && guard?.target_stage !== undefined;

  async function handleAdvanceStage() {
    try {
      await props.onAdvanceStage(note.trim() || null);
      setNote("");
    } catch {
      // keep the note for retry when the mutation itself fails
    }
  }

  return (
    <section className="border border-[#333333] bg-transparent/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
            阶段时间线
          </div>
          <p className="mt-3 text-sm leading-6 text-zinc-400">
            记录项目阶段推进、阻断原因和检查结果，便于回看关键节点。
          </p>
        </div>

        {guard ? (
          <div className="flex flex-wrap gap-2">
            <StatusBadge
              label={`当前：${
                PROJECT_STAGE_LABELS[guard.current_stage] ?? guard.current_stage
              }`}
              tone="info"
            />
            <StatusBadge
              label={
                guard.target_stage
                  ? `目标：${
                      PROJECT_STAGE_LABELS[guard.target_stage] ?? guard.target_stage
                    }`
                  : "已到最终阶段"
              }
              tone={guard.target_stage ? "neutral" : "success"}
            />
          </div>
        ) : null}
      </div>

      {guard && hasNextStage ? (
        <div className="mt-4 border border-[#333333] bg-transparent/70 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex-1">
              <div className="text-sm font-medium text-zinc-100">
                {guard.can_advance
                  ? "当前里程碑已满足，可以推进到下一阶段。"
                  : "当前里程碑尚未满足，但你仍可记录一次正式的阶段检查结果。"}
              </div>
              <div className="mt-2 text-xs leading-6 text-zinc-500">
                {guard.can_advance
                  ? "推进成功后，项目阶段会立即更新并写入时间线。"
                  : "若守卫未通过，本次动作会以“被守卫拦截”写入时间线，方便回放与追踪。"}
              </div>
            </div>

            <button
              type="button"
              onClick={() => void handleAdvanceStage()}
              disabled={props.isAdvancing}
              className="inline-flex items-center justify-center rounded-xl border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-[#3a3a3a] hover:bg-transparent/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {props.isAdvancing
                ? "处理中..."
                : guard.can_advance
                  ? `推进到 ${
                      PROJECT_STAGE_LABELS[guard.target_stage!] ?? guard.target_stage
                    }`
                  : "记录守卫检查"}
            </button>
          </div>

          <label className="mt-4 block space-y-2">
            <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">
              推进备注（可选）
            </span>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              className="w-full border border-[#333333] bg-transparent px-3 py-3 text-sm leading-6 text-zinc-100 outline-none transition focus:border-[#3a3a3a]"
              placeholder="例如：已确认规划拆解完成，开始进入执行阶段。"
            />
          </label>
        </div>
      ) : guard ? (
        <div className="mt-4 border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm leading-6 text-emerald-100">
          当前项目已经处于最终阶段，无需继续推进。
        </div>
      ) : (
        <p className="mt-4 text-sm leading-6 text-zinc-400">
          正在读取项目阶段信息...
        </p>
      )}

      {props.actionFeedback ? (
        <div
          className={`mt-4 border px-4 py-3 text-sm leading-6 ${
            props.actionFeedback.tone === "success"
              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-100"
              : props.actionFeedback.tone === "danger"
                ? "border-rose-500/20 bg-rose-500/10 text-rose-100"
                : "border-amber-500/20 bg-amber-500/10 text-amber-100"
          }`}
        >
          {props.actionFeedback.text}
        </div>
      ) : null}

      {timelineEntries.length > 0 ? (
        <div className="mt-5 space-y-3">
          {timelineEntries.map((entry) => (
            <article
              key={entry.id}
              className="border border-[#333333] bg-transparent/70 px-4 py-4"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge
                      label={
                        PROJECT_STAGE_HISTORY_OUTCOME_LABELS[entry.outcome] ??
                        entry.outcome
                      }
                      tone={entry.outcome === "applied" ? "success" : "warning"}
                    />
                    <span className="text-sm font-medium text-zinc-100">
                      {entry.from_stage
                        ? `${
                            PROJECT_STAGE_LABELS[entry.from_stage] ?? entry.from_stage
                          } → ${
                            PROJECT_STAGE_LABELS[entry.to_stage] ?? entry.to_stage
                          }`
                        : `初始化到 ${
                            PROJECT_STAGE_LABELS[entry.to_stage] ?? entry.to_stage
                          }`}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-zinc-500">
                    {formatDateTime(entry.created_at)}
                  </div>
                </div>
              </div>

              {entry.note ? (
                <p className="mt-3 text-sm leading-6 text-zinc-400">
                  备注：{entry.note}
                </p>
              ) : null}

              {entry.reasons.length > 0 ? (
                <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-400">
                  {entry.reasons.map((reason) => (
                    <li
                      key={`${entry.id}-${reason}`}
                      className="rounded-xl border border-[#333333] bg-transparent/70 px-3 py-2"
                    >
                      {reason}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm leading-6 text-zinc-400">
                  本次阶段动作无额外阻塞说明。
                </p>
              )}
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-5 text-sm leading-6 text-zinc-400">
          当前还没有阶段推进记录。
        </p>
      )}
    </section>
  );
}
