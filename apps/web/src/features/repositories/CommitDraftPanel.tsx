import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { requestJson } from "../../lib/http";
import {
  useChangeBatchCommitCandidate,
  useGenerateChangeBatchCommitCandidate,
  useProjectChangeBatches,
  useProjectCommitCandidates,
} from "./hooks";
import { CHANGE_BATCH_PREFLIGHT_STATUS_LABELS } from "./types";

type CommitDraftPanelProps = {
  projectId: string | null;
};

type Day15ReleaseJudgement = {
  selected_status:
    | "blocked"
    | "pending_approval"
    | "approved"
    | "rejected"
    | "changes_requested"
    | null;
  selected_blocked: boolean;
  selected_decision_count: number;
  selected_gap_reasons: string[];
  release_qualification_established: boolean;
  git_write_actions_triggered: boolean;
  summary: string;
};

function useDay15ReleaseJudgement(projectId: string | null) {
  return useQuery({
    queryKey: ["day15-release-judgement", projectId],
    queryFn: () =>
      requestJson<Day15ReleaseJudgement>(
        `/approvals/projects/${projectId}/day15-release-judgement`,
      ),
    enabled: Boolean(projectId),
  });
}

export function CommitDraftPanel(props: CommitDraftPanelProps) {
  const batchesQuery = useProjectChangeBatches(props.projectId);
  const candidatesQuery = useProjectCommitCandidates(props.projectId);
  const releaseJudgementQuery = useDay15ReleaseJudgement(props.projectId);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);

  const batchSummaries = batchesQuery.data ?? [];
  const activeBatch = batchSummaries.find((item) => item.active) ?? null;
  const selectedBatch =
    batchSummaries.find((item) => item.id === selectedBatchId) ??
    activeBatch ??
    batchSummaries[0] ??
    null;

  useEffect(() => {
    if (batchSummaries.length === 0) {
      setSelectedBatchId(null);
      return;
    }

    if (selectedBatchId && batchSummaries.some((item) => item.id === selectedBatchId)) {
      return;
    }

    setSelectedBatchId(activeBatch?.id ?? batchSummaries[0]?.id ?? null);
  }, [activeBatch?.id, batchSummaries, selectedBatchId]);

  const detailQuery = useChangeBatchCommitCandidate(selectedBatch?.id ?? null);
  const generateMutation = useGenerateChangeBatchCommitCandidate(
    props.projectId,
    selectedBatch?.id ?? null,
  );
  const candidateDetail = generateMutation.data ?? detailQuery.data ?? null;
  const latestVersion = candidateDetail?.latest_version ?? null;
  const canGenerate =
    selectedBatch !== null &&
    (selectedBatch.preflight.status === "ready_for_execution" ||
      selectedBatch.preflight.status === "manual_confirmed") &&
    !generateMutation.isPending;
  const candidateCount = candidatesQuery.data?.length ?? 0;

  const selectedBatchHint = useMemo(() => {
    if (!selectedBatch) {
      return "请先选择一个批次。";
    }

    if (!canGenerate) {
      return "当前批次尚未通过提交前检查，暂时不能生成提交草案。";
    }

    if (!candidateDetail) {
      return "当前批次尚无提交草案，可生成首版草案。";
    }

    return `当前草案已生成 ${candidateDetail.revision_count} 个版本，可继续修订。`;
  }, [canGenerate, candidateDetail, selectedBatch]);

  return (
    <section className="space-y-4 border-y border-[#333333] py-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            提交草案
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-400">
            基于已通过检查的变更批次生成可审阅的提交草案，集中查看草案内容、验证摘要、关联文件和修订历史。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`草案 ${candidateCount}`}
            tone={candidateCount > 0 ? "info" : "warning"}
          />
          <StatusBadge
            label={selectedBatch ? `当前批次 ${selectedBatch.title}` : "尚未选择批次"}
            tone={selectedBatch ? "neutral" : "warning"}
          />
        </div>
      </div>

      {batchesQuery.isError ? (
        <Alert message={`批次列表加载失败：${batchesQuery.error.message}`} />
      ) : null}
      {candidatesQuery.isError ? (
        <Alert message={`提交草案列表加载失败：${candidatesQuery.error.message}`} />
      ) : null}
      {detailQuery.isError ? (
        <Alert message={`提交草案详情加载失败：${detailQuery.error.message}`} />
      ) : null}
      {generateMutation.isError ? (
        <Alert message={`生成提交草案失败：${generateMutation.error.message}`} />
      ) : null}

      {releaseJudgementQuery.data ? (
        <section className="border-l border-[#333333] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={`放行判断 ${renderReleaseStatusLabel(releaseJudgementQuery.data.selected_status)}`}
              tone={mapReleaseTone(releaseJudgementQuery.data.selected_status)}
            />
            <StatusBadge
              label={`决策 ${releaseJudgementQuery.data.selected_decision_count}`}
              tone="info"
            />
            <StatusBadge
              label={
                releaseJudgementQuery.data.release_qualification_established
                  ? "放行资格已成立"
                  : "放行资格未成立"
              }
              tone={
                releaseJudgementQuery.data.release_qualification_established
                  ? "success"
                  : "warning"
              }
            />
            <StatusBadge
              label={`提交操作 ${releaseJudgementQuery.data.git_write_actions_triggered ? "已执行" : "未执行"}`}
              tone={
                releaseJudgementQuery.data.git_write_actions_triggered
                  ? "danger"
                  : "neutral"
              }
            />
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            {releaseJudgementQuery.data.summary}
          </p>
          {releaseJudgementQuery.data.selected_gap_reasons.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {releaseJudgementQuery.data.selected_gap_reasons.map((reason) => (
                <StatusBadge key={reason} label={reason} tone="warning" />
              ))}
            </div>
          ) : null}
        </section>
      ) : releaseJudgementQuery.isLoading && props.projectId ? (
        <div className="text-sm leading-6 text-zinc-500">
          正在读取放行判断...
        </div>
      ) : releaseJudgementQuery.isError ? (
        <Alert message={`放行判断加载失败：${releaseJudgementQuery.error.message}`} />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)]">
        <section className="border-y border-[#333333] py-4">
          <div className="text-sm font-semibold text-zinc-100">批次选择</div>
          <div className="mt-2 text-sm leading-6 text-zinc-400">{selectedBatchHint}</div>

          {batchesQuery.isLoading && batchSummaries.length === 0 ? (
            <div className="mt-4 text-sm leading-6 text-zinc-500">正在加载批次...</div>
          ) : batchSummaries.length > 0 ? (
            <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
              {batchSummaries.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedBatchId(item.id)}
                  className={`w-full border-l px-4 py-3 text-left transition ${
                    selectedBatch?.id === item.id
                      ? "border-[#4a4a4a] bg-[#2b2b2b]"
                      : "border-[#333333] bg-transparent hover:border-[#4a4a4a]"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium text-zinc-100">{item.title}</div>
                    <StatusBadge
                      label={CHANGE_BATCH_PREFLIGHT_STATUS_LABELS[item.preflight.status]}
                      tone={mapPreflightTone(item.preflight.status)}
                    />
                  </div>
                  <div className="mt-2 text-xs leading-5 text-zinc-400">{item.summary}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <StatusBadge label={`任务 ${item.task_count}`} tone="info" />
                    <StatusBadge label={`文件 ${item.target_file_count}`} tone="neutral" />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="mt-4 border-l border-dashed border-[#3a3a3a] px-4 py-3 text-sm leading-6 text-zinc-500">
              当前项目还没有变更批次，暂时不能生成提交草案。
            </div>
          )}

          <div className="mt-4 flex items-center justify-between gap-3 border-y border-[#333333] px-4 py-3">
            <div className="text-xs leading-5 text-zinc-400">
              {candidateDetail
                ? `当前版本 v${candidateDetail.current_version_number} \u00b7 更新于 ${formatDateTime(candidateDetail.updated_at)}`
                : "尚无草案版本"}
            </div>
            <button
              type="button"
              onClick={() => {
                void generateMutation.mutateAsync({});
              }}
              disabled={!canGenerate}
              className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600"
            >
              {generateMutation.isPending
                ? "正在生成..."
                : candidateDetail
                  ? "追加修订版本"
                  : "生成首版草案"}
            </button>
          </div>
        </section>

        <section className="border-y border-[#333333] py-4">
          <div className="text-sm font-semibold text-zinc-100">草案详情</div>
          {latestVersion ? (
            <div className="mt-4 space-y-4">
              <div className="border-l border-[#333333] px-4 py-3 text-sm leading-6 text-zinc-400">
                <div className="font-semibold text-zinc-100">{latestVersion.message_title}</div>
                <div className="mt-2 whitespace-pre-line">
                  {latestVersion.message_body}
                </div>
                <div className="mt-2 text-xs text-zinc-500">
                  证据包：{latestVersion.evidence_package_key} · 版本 v
                  {latestVersion.version_number} · 生成于{" "}
                  {formatDateTime(latestVersion.created_at)}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="验证总数"
                  value={String(latestVersion.verification_summary.total_runs)}
                />
                <MetricCard
                  label="通过"
                  value={String(latestVersion.verification_summary.passed_runs)}
                  tone="success"
                />
                <MetricCard
                  label="失败"
                  value={String(latestVersion.verification_summary.failed_runs)}
                  tone={latestVersion.verification_summary.failed_runs > 0 ? "danger" : "neutral"}
                />
                <MetricCard
                  label="交付件"
                  value={String(latestVersion.related_deliverables.length)}
                />
              </div>

              <FieldList title="影响范围" items={latestVersion.impact_scope} />
              <FieldList
                title="关联文件"
                items={latestVersion.related_files}
                asCode
                maxVisible={20}
              />
              <FieldList
                title="验证摘要"
                items={latestVersion.verification_summary.highlights}
                maxVisible={8}
              />

              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
                  关联交付件
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {latestVersion.related_deliverables.length > 0 ? (
                    latestVersion.related_deliverables.map((item) => (
                      <StatusBadge
                        key={`${latestVersion.id}-${item.deliverable_id}`}
                        label={`${item.title} \u00b7 v${item.current_version_number}`}
                        tone="neutral"
                      />
                    ))
                  ) : (
                    <span className="text-sm text-zinc-400">当前草案未关联交付件。</span>
                  )}
                </div>
              </div>

              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">版本历史</div>
                <div className="mt-2 space-y-2">
                  {[...(candidateDetail?.versions ?? [])]
                    .slice()
                    .reverse()
                    .map((item) => (
                      <div
                        key={item.id}
                        className="border-l border-[#333333] px-3 py-2 text-sm"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-medium text-zinc-100">
                            v{item.version_number} · {item.message_title}
                          </span>
                          <span className="text-xs text-zinc-500">
                            {formatDateTime(item.created_at)}
                          </span>
                        </div>
                        {item.revision_note ? (
                          <div className="mt-1 text-xs text-zinc-400">
                            修订说明：{item.revision_note}
                          </div>
                        ) : null}
                      </div>
                    ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-4 border-l border-dashed border-[#3a3a3a] px-4 py-3 text-sm leading-6 text-zinc-500">
              当前批次尚未生成提交草案。通过检查后可在左侧生成首版。
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function FieldList(props: {
  title: string;
  items: string[];
  asCode?: boolean;
  maxVisible?: number;
}) {
  const visibleItems = props.items.slice(0, props.maxVisible ?? props.items.length);

  return (
    <div>
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">{props.title}</div>
      {visibleItems.length > 0 ? (
        <div className="mt-2 space-y-2">
          {visibleItems.map((item) => (
            <div
              key={`${props.title}-${item}`}
              className={`border-l border-[#333333] px-3 py-2 text-sm leading-6 text-zinc-400 ${
                props.asCode ? "font-mono text-xs" : ""
              }`}
            >
              {item}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-2 text-sm leading-6 text-zinc-400">暂无内容。</div>
      )}
    </div>
  );
}

function MetricCard(props: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "danger";
}) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">{props.label}</div>
      <div
        className={`mt-2 text-sm font-medium ${
          props.tone === "success"
            ? "text-emerald-100"
            : props.tone === "danger"
              ? "text-rose-100"
              : "text-zinc-100"
        }`}
      >
        {props.value}
      </div>
    </div>
  );
}

function Alert(props: { message: string }) {
  return (
    <div className="mt-4 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
      {props.message}
    </div>
  );
}

function mapPreflightTone(
  status: "not_started" | "ready_for_execution" | "blocked_requires_confirmation" | "manual_confirmed" | "manual_rejected",
): "neutral" | "success" | "warning" | "danger" {
  if (status === "ready_for_execution" || status === "manual_confirmed") {
    return "success";
  }
  if (status === "blocked_requires_confirmation") {
    return "warning";
  }
  if (status === "manual_rejected") {
    return "danger";
  }

  return "neutral";
}

function mapReleaseTone(
  status: Day15ReleaseJudgement["selected_status"],
): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "approved") {
    return "success";
  }
  if (status === "blocked" || status === "rejected") {
    return "danger";
  }
  if (status === "changes_requested") {
    return "warning";
  }
  if (status === "pending_approval") {
    return "info";
  }
  return "neutral";
}

function renderReleaseStatusLabel(status: Day15ReleaseJudgement["selected_status"]) {
  if (status === null) {
    return "未形成";
  }
  switch (status) {
    case "approved":
      return "已通过";
    case "blocked":
      return "检查单阻断";
    case "rejected":
      return "已驳回";
    case "changes_requested":
      return "待补证据";
    default:
      return "待审批";
  }
}
