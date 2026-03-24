import type { ReactNode } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { APPROVAL_STATUS_LABELS } from "../approvals/types";
import {
  useApprovalChangeEvidence,
  useDeliverableChangeEvidence,
} from "./hooks";
import {
  DELIVERABLE_TYPE_LABELS,
  type ChangeEvidenceApprovalReference,
  type ChangeEvidenceDeliverableReference,
  type ChangeEvidencePackage,
} from "./types";

type ChangeEvidencePanelProps = {
  deliverableId?: string | null;
  approvalId?: string | null;
  open?: boolean;
};

const VERIFICATION_STATUS_LABELS = {
  passed: "通过",
  failed: "失败",
  skipped: "跳过",
} as const;

const SNAPSHOT_KIND_LABELS = {
  change_batch: "批次快照",
  deliverable_version: "交付件版本",
  approval: "审批快照",
  verification_run: "验证结果",
} as const;

export function ChangeEvidencePanel(props: ChangeEvidencePanelProps) {
  const deliverableQuery = useDeliverableChangeEvidence(
    props.approvalId ? null : props.deliverableId ?? null,
  );
  const approvalQuery = useApprovalChangeEvidence(
    props.approvalId ?? null,
    props.open ?? true,
  );

  const activeQuery = props.approvalId ? approvalQuery : deliverableQuery;
  const evidence = activeQuery.data ?? null;

  return (
    <section className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">
            V4 Day11 Acceptance Evidence
          </div>
          <h4 className="mt-2 text-lg font-semibold text-slate-50">代码差异验收证据包</h4>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            围绕当前交付件或审批项，汇总仓库差异摘要、变更计划、验证记录、交付件引用和审批上下文，供老板直接验收。
          </p>
        </div>

        {evidence ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <MiniInfo label="证据包键" value={evidence.package_key} mono />
            <MiniInfo
              label="生成时间"
              value={formatDateTime(evidence.generated_at)}
            />
          </div>
        ) : null}
      </header>

      {!props.deliverableId && !props.approvalId ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
          先选择交付件或审批项，再查看 Day11 验收证据包。
        </div>
      ) : activeQuery.isLoading && !evidence ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
          正在汇总代码差异摘要与验收证据包...
        </div>
      ) : activeQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          验收证据包加载失败：{activeQuery.error.message}
        </div>
      ) : evidence ? (
        <EvidenceContent evidence={evidence} />
      ) : null}
    </section>
  );
}

function EvidenceContent(props: { evidence: ChangeEvidencePackage }) {
  const { evidence } = props;

  return (
    <>
      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={evidence.selected_change_batch_title ?? "当前项目上下文"}
                tone="info"
              />
              {evidence.selected_deliverable_id ? (
                <StatusBadge label="交付件反查" tone="success" />
              ) : null}
              {evidence.selected_approval_id ? (
                <StatusBadge label="审批反查" tone="warning" />
              ) : null}
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{evidence.summary}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MiniInfo
              label="差异文件"
              value={String(evidence.diff_summary.metrics.changed_file_count)}
            />
            <MiniInfo
              label="验证记录"
              value={String(evidence.verification_summary.total_runs)}
            />
            <MiniInfo label="交付件引用" value={String(evidence.deliverables.length)} />
            <MiniInfo label="审批上下文" value={String(evidence.approvals.length)} />
          </div>
        </div>

        {evidence.diff_summary.note ? (
          <div className="mt-4 rounded-2xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
            {evidence.diff_summary.note}
          </div>
        ) : null}

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MiniInfo
            label="基线"
            value={evidence.diff_summary.baseline_label}
            mono
          />
          <MiniInfo label="目标" value={evidence.diff_summary.target_label} mono />
          <MiniInfo
            label="仓库根目录"
            value={evidence.repository_root_path}
            mono
          />
          <MiniInfo
            label="脏工作区"
            value={
              evidence.diff_summary.dirty_workspace
                ? `是（${evidence.diff_summary.dirty_file_count} 个文件）`
                : "否"
            }
          />
        </div>
      </section>

      <SectionCard
        title="关键差异文件"
        description="优先展示与 ChangeBatch 计划直接相关、或被删除 / 未跟踪的关键文件。"
        badge={`${evidence.diff_summary.key_files.length} 项`}
      >
        {evidence.diff_summary.key_files.length > 0 ? (
          <div className="space-y-3">
            {evidence.diff_summary.key_files.map((file) => (
              <div
                key={file.relative_path}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <code className="text-sm text-slate-100">{file.relative_path}</code>
                  <StatusBadge
                    label={renderDiffKind(file.change_kind)}
                    tone={mapDiffTone(file.change_kind)}
                  />
                  {file.in_change_batch ? (
                    <StatusBadge label="批次覆盖" tone="info" />
                  ) : null}
                  {file.in_dirty_workspace ? (
                    <StatusBadge label="工作区变更" tone="warning" />
                  ) : null}
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
                  <span>+{file.added_line_count}</span>
                  <span>-{file.deleted_line_count}</span>
                  <span>任务 {file.linked_task_ids.length} 个</span>
                  <span>计划 {file.linked_change_plan_ids.length} 个</span>
                </div>
                {file.notes.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {file.notes.map((note) => (
                      <StatusBadge key={note} label={note} tone="neutral" />
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyText text="当前范围内尚未识别到关键差异文件。" />
        )}
      </SectionCard>

      <SectionCard
        title="变更计划引用"
        description="收口到本轮 ChangeBatch 的 ChangePlan 快照，避免把 Day12+ 的回退重做链路提前并入。"
        badge={`${evidence.plan_items.length} 项`}
      >
        {evidence.plan_items.length > 0 ? (
          <div className="space-y-3">
            {evidence.plan_items.map((item) => (
              <div
                key={item.change_plan_id}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium text-slate-50">
                    {item.change_plan_title}
                  </div>
                  <StatusBadge label={`v${item.selected_version_number}`} tone="info" />
                  <StatusBadge label={item.task_title} tone="neutral" />
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  {item.intent_summary}
                </p>
                <TagGroup title="预期动作" values={item.expected_actions} />
                <TagGroup title="风险备注" values={item.risk_notes} />
                <TagGroup title="目标文件" values={item.target_file_paths} mono />
                <TagGroup
                  title="验证命令"
                  values={item.verification_commands}
                  mono
                />
                <TagGroup
                  title="交付件引用"
                  values={item.related_deliverable_titles}
                />
              </div>
            ))}
          </div>
        ) : (
          <EmptyText text="当前证据包未绑定 ChangeBatch 快照，暂未展示 ChangePlan 引用。" />
        )}
      </SectionCard>

      <SectionCard
        title="验证结果摘要"
        description="沿用 Day10 的 VerificationRun，按批次聚合通过 / 失败 / 跳过结果。"
        badge={`${evidence.verification_summary.total_runs} 条`}
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MiniInfo
            label="通过"
            value={String(evidence.verification_summary.passed_runs)}
          />
          <MiniInfo
            label="失败"
            value={String(evidence.verification_summary.failed_runs)}
          />
          <MiniInfo
            label="跳过"
            value={String(evidence.verification_summary.skipped_runs)}
          />
          <MiniInfo
            label="最新完成"
            value={
              evidence.verification_summary.latest_finished_at
                ? formatDateTime(evidence.verification_summary.latest_finished_at)
                : "暂无"
            }
          />
        </div>

        {evidence.verification_summary.runs.length > 0 ? (
          <div className="mt-4 space-y-3">
            {evidence.verification_summary.runs.map((run) => (
              <div
                key={run.verification_run_id}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium text-slate-50">
                    {run.change_plan_title}
                  </div>
                  <StatusBadge
                    label={VERIFICATION_STATUS_LABELS[run.status]}
                    tone={mapVerificationTone(run.status)}
                  />
                  <StatusBadge
                    label={run.verification_template_name ?? "手工命令"}
                    tone="info"
                  />
                  <StatusBadge label={run.change_batch_title} tone="neutral" />
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  {run.output_summary}
                </p>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
                  <span>命令来源：{run.command_source === "template" ? "模板" : "手工"}</span>
                  <span>开始：{formatDateTime(run.started_at)}</span>
                  <span>结束：{formatDateTime(run.finished_at)}</span>
                  {run.failure_category ? <span>归因：{run.failure_category}</span> : null}
                </div>
                <code className="mt-3 block overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-300">
                  {run.command}
                </code>
              </div>
            ))}
          </div>
        ) : (
          <EmptyText text="当前证据包还没有可展示的验证记录。" />
        )}
      </SectionCard>

      <div className="grid gap-5 xl:grid-cols-2">
        <SectionCard
          title="交付件引用"
          description="交付件页面可以按 deliverable_id 反查对应证据包。"
          badge={`${evidence.deliverables.length} 项`}
        >
          {evidence.deliverables.length > 0 ? (
            <div className="space-y-3">
              {evidence.deliverables.map((deliverable) => (
                <DeliverableReferenceCard
                  key={deliverable.deliverable_id}
                  deliverable={deliverable}
                />
              ))}
            </div>
          ) : (
            <EmptyText text="当前证据包未命中交付件引用。" />
          )}
        </SectionCard>

        <SectionCard
          title="审批上下文"
          description="审批页可以按 approval_id 反查同一份证据包，并直接看到最新审批结论。"
          badge={`${evidence.approvals.length} 项`}
        >
          {evidence.approvals.length > 0 ? (
            <div className="space-y-3">
              {evidence.approvals.map((approval) => (
                <ApprovalReferenceCard
                  key={approval.approval_id}
                  approval={approval}
                />
              ))}
            </div>
          ) : (
            <EmptyText text="当前证据包未找到审批上下文。" />
          )}
        </SectionCard>
      </div>

      <SectionCard
        title="版本快照"
        description="同一批次下保留 ChangeBatch、交付件版本、审批节点和验证结果的时间序列，便于审批前后对比。"
        badge={`${evidence.snapshots.length} 条`}
      >
        {evidence.snapshots.length > 0 ? (
          <div className="space-y-3">
            {evidence.snapshots.map((snapshot) => (
              <div
                key={snapshot.snapshot_id}
                className={`rounded-2xl border px-4 py-4 ${
                  snapshot.selected
                    ? "border-cyan-400/40 bg-cyan-500/10"
                    : "border-slate-800 bg-slate-950/60"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium text-slate-50">{snapshot.label}</div>
                  <StatusBadge
                    label={SNAPSHOT_KIND_LABELS[snapshot.snapshot_kind]}
                    tone={snapshot.selected ? "info" : "neutral"}
                  />
                  {snapshot.selected ? <StatusBadge label="当前焦点" tone="success" /> : null}
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {snapshot.summary}
                </p>
                <div className="mt-2 text-xs text-slate-400">
                  {formatDateTime(snapshot.recorded_at)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyText text="当前证据包暂未形成可对比的版本快照。" />
        )}
      </SectionCard>
    </>
  );
}

function DeliverableReferenceCard(props: {
  deliverable: ChangeEvidenceDeliverableReference;
}) {
  const deliverable = props.deliverable;

  return (
    <div
      className={`rounded-2xl border px-4 py-4 ${
        deliverable.selected
          ? "border-cyan-400/40 bg-cyan-500/10"
          : "border-slate-800 bg-slate-950/60"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-medium text-slate-50">{deliverable.title}</div>
        <StatusBadge
          label={DELIVERABLE_TYPE_LABELS[deliverable.type] ?? deliverable.type}
          tone="info"
        />
        <StatusBadge
          label={PROJECT_STAGE_LABELS[deliverable.stage] ?? deliverable.stage}
          tone="neutral"
        />
        <StatusBadge label={`v${deliverable.current_version_number}`} tone="success" />
      </div>
      {deliverable.latest_version_summary ? (
        <p className="mt-3 text-sm leading-6 text-slate-300">
          {deliverable.latest_version_summary}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
        <span>
          最新版本：
          {deliverable.latest_version_created_at
            ? formatDateTime(deliverable.latest_version_created_at)
            : "暂无"}
        </span>
        {deliverable.source_task_id ? <span>来源任务已绑定</span> : null}
        {deliverable.source_run_id ? <span>来源运行已绑定</span> : null}
      </div>
    </div>
  );
}

function ApprovalReferenceCard(props: {
  approval: ChangeEvidenceApprovalReference;
}) {
  const approval = props.approval;

  return (
    <div
      className={`rounded-2xl border px-4 py-4 ${
        approval.selected
          ? "border-cyan-400/40 bg-cyan-500/10"
          : "border-slate-800 bg-slate-950/60"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-medium text-slate-50">
          {approval.deliverable_title} · v{approval.deliverable_version_number}
        </div>
        <StatusBadge
          label={APPROVAL_STATUS_LABELS[approval.status] ?? approval.status}
          tone={mapApprovalTone(approval.status)}
        />
        {approval.selected ? <StatusBadge label="当前审批项" tone="success" /> : null}
      </div>
      <div className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
        {approval.request_note ? <p>发起说明：{approval.request_note}</p> : null}
        {approval.latest_summary ? <p>最近结论：{approval.latest_summary}</p> : null}
        {approval.latest_decision_summary ? (
          <p>
            最新动作：{approval.latest_decision_summary}
            {approval.latest_decision_actor_name
              ? `（${approval.latest_decision_actor_name}）`
              : ""}
          </p>
        ) : null}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
        <span>发起时间：{formatDateTime(approval.requested_at)}</span>
        <span>截止时间：{formatDateTime(approval.due_at)}</span>
        {approval.latest_decision_at ? (
          <span>最近审批：{formatDateTime(approval.latest_decision_at)}</span>
        ) : null}
      </div>
      <TagGroup title="要求修改" values={approval.requested_changes} />
      <TagGroup title="高亮风险" values={approval.highlighted_risks} />
    </div>
  );
}

function SectionCard(props: {
  title: string;
  description: string;
  badge?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h5 className="text-base font-semibold text-slate-50">{props.title}</h5>
          <p className="mt-1 text-sm leading-6 text-slate-400">{props.description}</p>
        </div>
        {props.badge ? <StatusBadge label={props.badge} tone="neutral" /> : null}
      </div>
      <div className="mt-4">{props.children}</div>
    </section>
  );
}

function TagGroup(props: {
  title: string;
  values: string[];
  mono?: boolean;
}) {
  if (props.values.length === 0) {
    return null;
  }

  return (
    <div className="mt-3">
      <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.title}
      </div>
      <div className="flex flex-wrap gap-2">
        {props.values.map((value) => (
          <span
            key={`${props.title}-${value}`}
            className={`rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-300 ${
              props.mono ? "font-mono" : ""
            }`}
          >
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function EmptyText(props: { text: string }) {
  return <p className="text-sm leading-6 text-slate-400">{props.text}</p>;
}

function MiniInfo(props: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div
        className={`mt-2 break-all text-sm font-medium text-slate-100 ${
          props.mono ? "font-mono" : ""
        }`}
      >
        {props.value}
      </div>
    </div>
  );
}

function renderDiffKind(kind: string) {
  switch (kind) {
    case "added":
      return "新增";
    case "deleted":
      return "删除";
    case "untracked":
      return "未跟踪";
    default:
      return "修改";
  }
}

function mapDiffTone(kind: string): "success" | "danger" | "warning" | "info" {
  switch (kind) {
    case "added":
      return "success";
    case "deleted":
      return "danger";
    case "untracked":
      return "warning";
    default:
      return "info";
  }
}

function mapVerificationTone(
  status: string,
): "success" | "danger" | "warning" {
  switch (status) {
    case "passed":
      return "success";
    case "failed":
      return "danger";
    default:
      return "warning";
  }
}

function mapApprovalTone(
  status: ChangeEvidenceApprovalReference["status"],
): "success" | "danger" | "warning" {
  switch (status) {
    case "approved":
      return "success";
    case "rejected":
      return "danger";
    default:
      return "warning";
  }
}
