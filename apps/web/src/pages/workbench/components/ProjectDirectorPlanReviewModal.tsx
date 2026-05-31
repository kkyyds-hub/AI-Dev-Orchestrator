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
            <section className="space-y-3 rounded border border-[#333333] bg-[#111111] p-4">
              <h4 className="text-sm font-semibold text-zinc-100">项目范围 / 不做范围</h4>
              <ListBlock title="范围内" items={planVersion.project_scope?.in_scope ?? []} />
              <ListBlock title="不做范围" items={planVersion.project_scope?.out_of_scope ?? []} />
              <ListBlock title="关键假设" items={planVersion.project_scope?.assumptions ?? []} />
            </section>

            <section className="space-y-3 rounded border border-[#333333] bg-[#111111] p-4">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold text-zinc-100">复杂度评估</h4>
                <StatusBadge
                  label={`${planVersion.complexity_assessment?.label ?? formatComplexityLevel(planVersion.complexity_assessment?.level)} · ${planVersion.complexity_assessment?.score ?? "-"} / 5`}
                  tone="info"
                />
                <StatusBadge
                  label={`建议 ${planVersion.complexity_assessment?.recommended_agent_count ?? "-"} 人编队`}
                  tone="neutral"
                />
              </div>
              <ListBlock title="驱动因素" items={planVersion.complexity_assessment?.drivers ?? []} />
              <ListBlock
                title="缓解建议"
                items={planVersion.complexity_assessment?.mitigation_suggestions ?? []}
              />
            </section>
          </div>

          {planVersion.agent_team_suggestions.length > 0 ? (
            <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
              <h4 className="text-sm font-semibold text-zinc-100">Agent 编队建议</h4>
              <div className="grid gap-2 lg:grid-cols-2">
                {planVersion.agent_team_suggestions.map((item) => (
                  <div
                    key={`${item.role_code}-${item.responsibility}`}
                    className="rounded border border-[#2f2f2f] bg-[#171717] p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge label={item.role_name || formatRoleCode(item.role_code)} tone="warning" />
                      <span className="text-xs text-zinc-500">{item.role_code}</span>
                    </div>
                    <p className="mt-2 text-sm text-zinc-300">{item.responsibility}</p>
                    <ListBlock title="协作说明" items={item.collaboration_notes} compact />
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            {planVersion.skill_binding_suggestions.length > 0 ? (
              <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
                <h4 className="text-sm font-semibold text-zinc-100">Skill 绑定建议</h4>
                <div className="space-y-2">
                  {planVersion.skill_binding_suggestions.map((item) => (
                    <div key={`${item.skill_code}-${item.owner_role_code}`} className="rounded border border-[#2f2f2f] bg-[#171717] p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                        <span className="font-medium text-zinc-200">{item.skill_code}</span>
                        <StatusBadge label={formatRoleCode(item.owner_role_code)} tone="warning" />
                        <StatusBadge label={`阶段：${item.activation_stage}`} tone="neutral" />
                        <StatusBadge label={`绑定：${item.binding_mode}`} tone="neutral" />
                      </div>
                      <p className="mt-2 text-sm text-zinc-400">{item.usage}</p>
                      <p className="mt-1 text-xs leading-5 text-zinc-500">原因：{item.reason}</p>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {planVersion.repository_binding_suggestions.length > 0 ? (
              <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
                <h4 className="text-sm font-semibold text-zinc-100">仓库绑定建议</h4>
                <div className="space-y-2">
                  {planVersion.repository_binding_suggestions.map((item) => (
                    <div key={`${item.binding_type}-${item.target}`} className="rounded border border-[#2f2f2f] bg-[#171717] p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                        <span className="font-medium text-zinc-200">{item.target}</span>
                        <StatusBadge label={item.binding_type} tone="neutral" />
                        <StatusBadge label={`模式：${item.binding_mode}`} tone="neutral" />
                        <StatusBadge label={`分支：${item.branch}`} tone="info" />
                      </div>
                      <p className="mt-2 text-sm text-zinc-400">{item.usage}</p>
                      <ListBlock title="关注路径" items={item.focus_paths} compact />
                      <p className="mt-2 text-xs leading-5 text-amber-200">{item.safety_note}</p>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {planVersion.verification_mechanisms.length > 0 ? (
              <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
                <h4 className="text-sm font-semibold text-zinc-100">验证机制建议</h4>
                <div className="space-y-2">
                  {planVersion.verification_mechanisms.map((item) => (
                    <div key={`${item.name}-${item.command_or_method}`} className="rounded border border-[#2f2f2f] bg-[#171717] p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                        <span className="font-medium text-zinc-200">{item.name}</span>
                        <StatusBadge label={formatRoleCode(item.owner_role_code)} tone="warning" />
                        <StatusBadge label={`风险：${item.risk_level}`} tone="neutral" />
                        <StatusBadge
                          label={item.requires_user_confirmation ? "需用户确认" : "无需用户确认"}
                          tone={item.requires_user_confirmation ? "warning" : "neutral"}
                        />
                      </div>
                      <p className="mt-2 text-sm text-zinc-300">{item.purpose}</p>
                      <p className="mt-2 break-words text-sm text-zinc-300">{item.command_or_method}</p>
                      <p className="mt-1 text-xs leading-5 text-zinc-500">{item.evidence_required}</p>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {planVersion.deliverable_boundaries.length > 0 ? (
              <section className="space-y-2 rounded border border-[#333333] bg-[#111111] p-4">
                <h4 className="text-sm font-semibold text-zinc-100">交付件边界</h4>
                <div className="space-y-2">
                  {planVersion.deliverable_boundaries.map((item) => (
                    <div key={`${item.name}-${item.owner_role_code}`} className="rounded border border-[#2f2f2f] bg-[#171717] p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                        <span className="font-medium text-zinc-200">{item.name}</span>
                        <StatusBadge label={formatRoleCode(item.owner_role_code)} tone="warning" />
                      </div>
                      <p className="mt-2 text-sm text-zinc-300">{item.description}</p>
                      <ListBlock title="必须包含" items={item.required_contents} compact />
                      <p className="mt-2 text-xs leading-5 text-zinc-500">{item.done_definition}</p>
                      <p className="mt-1 text-xs leading-5 text-emerald-200">
                        验收信号：{item.acceptance_signal}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}
          </div>

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

function ListBlock({
  title,
  items,
  compact = false,
}: {
  title: string;
  items: string[];
  compact?: boolean;
}) {
  if (items.length === 0) {
    return (
      <p className={`${compact ? "mt-2 text-xs" : "text-sm"} text-zinc-600`}>
        {title}：暂无
      </p>
    );
  }

  return (
    <div className={compact ? "mt-2" : undefined}>
      <p className={`${compact ? "text-xs" : "text-sm"} font-medium text-zinc-300`}>
        {title}
      </p>
      <ul className={`${compact ? "mt-1 text-xs" : "mt-2 text-sm"} list-disc space-y-1 pl-5 text-zinc-500`}>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
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

function formatComplexityLevel(level: string | undefined) {
  switch (level) {
    case "low":
      return "低复杂度";
    case "medium":
      return "中复杂度";
    case "high":
      return "高复杂度";
    default:
      return level || "未评估";
  }
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
