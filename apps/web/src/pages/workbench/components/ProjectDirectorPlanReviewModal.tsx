import { StatusBadge } from "../../../components/StatusBadge";
import { PROJECT_DIRECTOR_PLAN_STATUS_LABELS } from "../../../features/project-director/types";
import { TASK_PRIORITY_LABELS } from "../../../features/projects/types";
import { ROLE_CODE_LABELS } from "../../../features/roles/types";
import type {
  ProjectDirectorPlanReviewAction,
  ProjectDirectorPlanVersion,
} from "../../../features/project-director/types";
import { DetailModal } from "./DetailModal";

type ProjectDirectorPlanReviewModalProps = {
  open: boolean;
  onClose: () => void;
  planVersion: ProjectDirectorPlanVersion | null;
  reviewFeedback: string;
  onReviewFeedbackChange: (value: string) => void;
  onReview: (action: ProjectDirectorPlanReviewAction) => void;
  reviewErrorMessage?: string | null;
  reviewStatusMessage?: string | null;
  isReviewPending: boolean;
};

export function ProjectDirectorPlanReviewModal({
  open,
  onClose,
  planVersion,
  reviewFeedback,
  onReviewFeedbackChange,
  onReview,
  reviewErrorMessage,
  reviewStatusMessage,
  isReviewPending,
}: ProjectDirectorPlanReviewModalProps) {
  const reviewable = planVersion?.status === "pending_confirmation";
  const canRequestChanges = reviewable && reviewFeedback.trim().length > 0 && !isReviewPending;

  return (
    <DetailModal open={open} onClose={onClose} title="项目草案审核">
      {!planVersion ? (
        <p className="text-sm text-zinc-400">当前还没有可审阅的项目草案。</p>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <StatusBadge label={`v${planVersion.version_no}`} tone="info" />
            <StatusBadge
              label={PROJECT_DIRECTOR_PLAN_STATUS_LABELS[planVersion.status]}
              tone={mapPlanStatusTone(planVersion.status)}
            />
            <span>Gate: {planVersion.gate_conclusion}</span>
          </div>

          {reviewStatusMessage ? (
            <div className="rounded border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100">
              {reviewStatusMessage}
            </div>
          ) : null}

          <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
            <h4 className="text-sm font-semibold text-zinc-100">作战计划摘要</h4>
            <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-300">
              {planVersion.plan_summary}
            </p>
          </section>

          {planVersion.phases.length > 0 ? (
            <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
              <h4 className="text-sm font-semibold text-zinc-100">阶段拆解</h4>
              <div className="space-y-2">
                {planVersion.phases.map((phase) => (
                  <div
                    key={`${phase.sequence}-${phase.name}`}
                    className="rounded border border-[#2f2f2f] bg-[#171717] p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                      <StatusBadge label={`P${phase.sequence}`} tone="info" />
                      <span className="font-medium text-zinc-200">{phase.name}</span>
                      <span>任务建议 {phase.task_count_hint}</span>
                    </div>
                    <p className="mt-2 text-sm text-zinc-400">{phase.goal}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {planVersion.proposed_tasks.length > 0 ? (
            <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
              <h4 className="text-sm font-semibold text-zinc-100">拟议任务</h4>
              <div className="grid gap-2 lg:grid-cols-2">
                {planVersion.proposed_tasks.map((task, index) => (
                  <div
                    key={`${task.title}-${index}`}
                    className="rounded border border-[#2f2f2f] bg-[#171717] p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                      <span className="font-medium text-zinc-200">{task.title}</span>
                      <StatusBadge label={formatPriorityHint(task.priority_hint)} tone="neutral" />
                      <StatusBadge label={formatRoleCode(task.suggested_role_code)} tone="warning" />
                    </div>
                    <p className="mt-2 text-sm text-zinc-400">{task.description}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
              <h4 className="text-sm font-semibold text-zinc-100">验收标准</h4>
              {planVersion.acceptance_criteria.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-400">
                  {planVersion.acceptance_criteria.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-zinc-500">当前没有额外验收标准。</p>
              )}
            </section>

            <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
              <h4 className="text-sm font-semibold text-zinc-100">风险提示</h4>
              {planVersion.risks.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-400">
                  {planVersion.risks.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-zinc-500">当前没有额外风险提示。</p>
              )}
            </section>
          </div>

          <section className="space-y-3 rounded border border-amber-500/20 bg-amber-500/5 p-4">
            <div>
              <h4 className="text-sm font-semibold text-amber-100">审核结论</h4>
              <p className="mt-1 text-xs leading-5 text-zinc-400">
                草案只用于审阅，不会自动调用真实 provider、Worker Pool、planning/apply 或仓库写入。
              </p>
            </div>

            <textarea
              value={reviewFeedback}
              onChange={(event) => onReviewFeedbackChange(event.target.value)}
              rows={4}
              disabled={!reviewable || isReviewPending}
              placeholder="如果需要整改，请写明要补充的范围、阶段、验收标准或风险说明。"
              className="w-full rounded border border-[#3a3a3a] bg-[#101010] px-3 py-2 text-sm text-zinc-200 outline-none transition focus:border-amber-500/50 disabled:cursor-not-allowed disabled:opacity-60"
            />

            {reviewErrorMessage ? (
              <div className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                {reviewErrorMessage}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={!reviewable || isReviewPending}
                onClick={() => onReview("approve")}
                className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
              >
                {isReviewPending ? "处理中..." : "通过草案"}
              </button>
              <button
                type="button"
                disabled={!reviewable || isReviewPending}
                onClick={() => onReview("reject")}
                className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm font-medium text-rose-200 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
              >
                {isReviewPending ? "处理中..." : "拒绝草案"}
              </button>
              <button
                type="button"
                disabled={!canRequestChanges}
                onClick={() => onReview("request_changes")}
                className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:border-[#333333] disabled:bg-[#171717] disabled:text-zinc-600"
              >
                {isReviewPending ? "重新规划中..." : "要求整改并生成新版本"}
              </button>
            </div>
          </section>
        </div>
      )}
    </DetailModal>
  );
}

function formatPriorityHint(priorityHint: string) {
  const normalizedPriority = priorityHint.toLowerCase();
  const label = TASK_PRIORITY_LABELS[normalizedPriority] ?? priorityHint;
  return `优先级：${label}`;
}

function formatRoleCode(roleCode: string) {
  const label = ROLE_CODE_LABELS[roleCode] ?? roleCode;
  return `角色：${label}`;
}

function mapPlanStatusTone(status: ProjectDirectorPlanVersion["status"]) {
  switch (status) {
    case "confirmed":
      return "success" as const;
    case "rejected":
      return "danger" as const;
    case "pending_confirmation":
      return "warning" as const;
    case "superseded":
      return "neutral" as const;
    default:
      return "info" as const;
  }
}
