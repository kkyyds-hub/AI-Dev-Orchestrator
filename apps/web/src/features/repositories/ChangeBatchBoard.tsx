import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type { ChangePlanSummary } from "../projects/types";
import { PreflightChecklist } from "./components/PreflightChecklist";
import {
  useChangeBatchDetail,
  useCreateProjectChangeBatch,
  useProjectChangeBatches,
  useRunChangeBatchPreflight,
} from "./hooks";
import type {
  ChangeBatchDetail,
  ChangeBatchSummary,
  ChangeBatchTargetFileAggregate,
} from "./types";
import { CHANGE_BATCH_PREFLIGHT_STATUS_LABELS } from "./types";

type ChangeBatchBoardProps = {
  projectId: string | null;
  changePlans: ChangePlanSummary[];
  isLoadingChangePlans: boolean;
  changePlanErrorMessage: string | null;
};

export function ChangeBatchBoard(props: ChangeBatchBoardProps) {
  const batchesQuery = useProjectChangeBatches(props.projectId);
  const createMutation = useCreateProjectChangeBatch(props.projectId);
  const [draftTitle, setDraftTitle] = useState("");
  const [selectedPlanIds, setSelectedPlanIds] = useState<string[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);

  const candidateChangePlans = useMemo(() => {
    const seenTaskIds = new Set<string>();

    return props.changePlans.filter((item) => {
      if (seenTaskIds.has(item.task_id)) {
        return false;
      }

      seenTaskIds.add(item.task_id);
      return true;
    });
  }, [props.changePlans]);
  const batchSummaries = batchesQuery.data ?? [];
  const activeBatch = batchSummaries.find((item) => item.active) ?? null;

  useEffect(() => {
    setSelectedPlanIds((current) =>
      current.filter((planId) => candidateChangePlans.some((item) => item.id === planId)),
    );
  }, [candidateChangePlans]);

  useEffect(() => {
    if (batchSummaries.length === 0) {
      setSelectedBatchId(null);
      return;
    }

    const selectedStillExists = batchSummaries.some((item) => item.id === selectedBatchId);
    if (selectedStillExists) {
      return;
    }

    setSelectedBatchId(activeBatch?.id ?? batchSummaries[0]?.id ?? null);
  }, [activeBatch?.id, batchSummaries, selectedBatchId]);

  const detailQuery = useChangeBatchDetail(selectedBatchId);
  const preflightMutation = useRunChangeBatchPreflight(props.projectId, selectedBatchId);
  const selectedBatchSummary =
    batchSummaries.find((item) => item.id === selectedBatchId) ??
    activeBatch ??
    batchSummaries[0] ??
    null;
  const selectedBatchDetail = detailQuery.data ?? null;
  const canCreate =
    props.projectId !== null &&
    selectedPlanIds.length >= 2 &&
    activeBatch === null &&
    !createMutation.isPending;

  async function handleCreateBatch() {
    const result = await createMutation.mutateAsync({
      title: draftTitle.trim() || null,
      change_plan_ids: selectedPlanIds,
    });
    setSelectedBatchId(result.id);
    setSelectedPlanIds([]);
    setDraftTitle("");
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Day07 变更批次与执行准备
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            这里把多个已确认的 ChangePlan 合并成可推进的 ChangeBatch，明确任务顺序、
            依赖关系与文件重叠风险；当前已补上 Day08 的执行前风险预检与人工确认，
            但仍不进入 Day09+ 的验证运行、证据包或任何产品内真实 Git 写操作。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`批次 ${batchSummaries.length}`}
            tone={batchSummaries.length > 0 ? "info" : "warning"}
          />
          <StatusBadge
            label={
              activeBatch
                ? `活跃批次 ${activeBatch.change_plan_count} 计划`
                : "当前无活跃批次"
            }
            tone={activeBatch ? "warning" : "success"}
          />
        </div>
      </div>

      {props.changePlanErrorMessage ? (
        <Alert tone="danger" message={`批次候选 ChangePlan 加载失败：${props.changePlanErrorMessage}`} />
      ) : null}
      {batchesQuery.isError ? (
        <Alert tone="danger" message={`批次列表加载失败：${batchesQuery.error.message}`} />
      ) : null}
      {createMutation.isError ? (
        <Alert tone="danger" message={`创建批次失败：${createMutation.error.message}`} />
      ) : null}
      {detailQuery.isError ? (
        <Alert tone="danger" message={`批次详情加载失败：${detailQuery.error.message}`} />
      ) : null}
      {preflightMutation.isError ? (
        <Alert tone="danger" message={`执行前预检失败：${preflightMutation.error.message}`} />
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.9fr)]">
        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-50">创建 ChangeBatch</div>
              <div className="mt-2 text-sm leading-6 text-slate-400">
                默认每个任务只取当前最新一条 ChangePlan 线程；至少选择 2 个不同任务的
                草案，才能形成一份 Day07 执行准备批次。
              </div>
            </div>
            <StatusBadge
              label={`可选 ${candidateChangePlans.length}`}
              tone={candidateChangePlans.length >= 2 ? "success" : "warning"}
            />
          </div>

          {activeBatch ? (
            <div className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
              当前项目已存在活跃批次：
              <span className="font-medium"> {activeBatch.title}</span>。Day07
              约束同一项目同一时刻只允许一个活跃批次，避免范围混乱。
            </div>
          ) : null}

          <label className="mt-4 block text-xs uppercase tracking-[0.2em] text-slate-500">
            批次标题（可选）
          </label>
          <input
            type="text"
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            placeholder="例如：Day07 仓库批次准备"
            className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-400/40"
          />

          {props.isLoadingChangePlans ? (
            <div className="mt-4 text-sm leading-6 text-slate-400">
              正在加载可并入批次的 ChangePlan...
            </div>
          ) : candidateChangePlans.length > 0 ? (
            <div className="mt-4 space-y-3">
              {candidateChangePlans.map((item) => {
                const selected = selectedPlanIds.includes(item.id);

                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setSelectedPlanIds((current) =>
                        current.includes(item.id)
                          ? current.filter((planId) => planId !== item.id)
                          : [...current, item.id],
                      );
                    }}
                    className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                      selected
                        ? "border-cyan-400/50 bg-cyan-500/10"
                        : "border-slate-800 bg-slate-950/60 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-medium text-slate-50">
                            {item.task_title}
                          </div>
                          <StatusBadge
                            label={`v${item.current_version_number}`}
                            tone="warning"
                          />
                          <StatusBadge
                            label={`${item.latest_version.target_files.length} 文件`}
                            tone="info"
                          />
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-300">
                          {item.title}
                        </div>
                        <div className="mt-2 text-xs leading-5 text-slate-500">
                          {item.latest_version.intent_summary}
                        </div>
                      </div>

                      <div className="flex flex-col items-start gap-2 lg:items-end">
                        <StatusBadge
                          label={selected ? "已选择" : "点击纳入"}
                          tone={selected ? "success" : "neutral"}
                        />
                        <span className="text-xs text-slate-500">
                          更新于 {formatDateTime(item.updated_at)}
                        </span>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.latest_version.related_deliverables.map((deliverable) => (
                        <StatusBadge
                          key={`${item.id}-${deliverable.deliverable_id}`}
                          label={deliverable.title}
                          tone="neutral"
                        />
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-400">
              当前可并入批次的最新 ChangePlan 不足 2 条。请先在上方 Day06 草案区补齐至少
              2 个任务的 ChangePlan，再创建 Day07 批次。
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
            <div className="text-sm leading-6 text-slate-400">
              已选 <span className="font-medium text-slate-100">{selectedPlanIds.length}</span>{" "}
              / 至少 2 条最新 ChangePlan
            </div>
            <button
              type="button"
              onClick={() => {
                void handleCreateBatch();
              }}
              disabled={!canCreate}
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
            >
              {createMutation.isPending ? "正在创建批次..." : "创建 ChangeBatch"}
            </button>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-sm font-semibold text-slate-50">批次列表</div>
          <div className="mt-2 text-sm leading-6 text-slate-400">
            这里展示当前项目的 ChangeBatch 摘要；Day08 预检状态也会同步回写到列表、详情与时间线。
          </div>

          {batchesQuery.isLoading && batchSummaries.length === 0 ? (
            <div className="mt-4 text-sm leading-6 text-slate-400">正在加载批次列表...</div>
          ) : batchSummaries.length > 0 ? (
            <div className="mt-4 space-y-3">
              {batchSummaries.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedBatchId(item.id)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                    item.id === selectedBatchId
                      ? "border-cyan-400/50 bg-cyan-500/10"
                      : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium text-slate-100">{item.title}</div>
                    <StatusBadge
                      label={item.active ? "活跃" : item.status}
                      tone={item.active ? "warning" : mapBatchStatusTone(item.status)}
                    />
                  </div>
                  <div className="mt-2 text-xs leading-5 text-slate-400">{item.summary}</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <StatusBadge label={`任务 ${item.task_count}`} tone="info" />
                    <StatusBadge label={`文件 ${item.target_file_count}`} tone="neutral" />
                    <StatusBadge
                      label={`重叠 ${item.overlap_file_count}`}
                      tone={item.overlap_file_count > 0 ? "warning" : "success"}
                    />
                    <StatusBadge
                      label={CHANGE_BATCH_PREFLIGHT_STATUS_LABELS[item.preflight.status]}
                      tone={
                        item.preflight.status === "ready_for_execution" ||
                        item.preflight.status === "manual_confirmed"
                          ? "success"
                          : item.preflight.status === "blocked_requires_confirmation"
                            ? "warning"
                            : item.preflight.status === "manual_rejected"
                              ? "danger"
                              : "neutral"
                      }
                    />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-900/60 px-4 py-3 text-sm leading-6 text-slate-400">
              当前项目还没有 Day07 ChangeBatch；创建后会在这里显示摘要。
            </div>
          )}
        </section>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-slate-50">批次详情</div>
            <div className="mt-2 text-sm leading-6 text-slate-400">
              查看当前批次的执行顺序、依赖关系、目标文件与本地时间线。
            </div>
          </div>

          {selectedBatchSummary ? (
            <div className="flex flex-wrap gap-2">
              <StatusBadge label={selectedBatchSummary.title} tone="info" />
              <StatusBadge
                label={selectedBatchSummary.active ? "活跃批次" : selectedBatchSummary.status}
                tone={
                  selectedBatchSummary.active
                    ? "warning"
                    : mapBatchStatusTone(selectedBatchSummary.status)
                }
              />
            </div>
          ) : null}
        </div>

        {detailQuery.isLoading && selectedBatchSummary ? (
          <div className="mt-4 text-sm leading-6 text-slate-400">正在加载批次详情...</div>
        ) : selectedBatchDetail ? (
          <ChangeBatchDetailPanel
            detail={selectedBatchDetail}
            onRunPreflight={() => {
              void preflightMutation.mutateAsync({});
            }}
            isRunningPreflight={preflightMutation.isPending}
          />
        ) : (
          <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-900/60 px-4 py-3 text-sm leading-6 text-slate-400">
            请选择一条批次摘要，或先创建新的 ChangeBatch。
          </div>
        )}
      </div>
    </section>
  );
}

function ChangeBatchDetailPanel(props: {
  detail: ChangeBatchDetail;
  onRunPreflight: () => void;
  isRunningPreflight: boolean;
}) {
  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm leading-6 text-cyan-100">
        {props.detail.summary}
        <div className="mt-2 text-xs text-cyan-50/70">
          创建于 {formatDateTime(props.detail.created_at)} · 最近更新{" "}
          {formatDateTime(props.detail.updated_at)}
        </div>
      </div>

      <PreflightChecklist
        title={props.detail.title}
        preflight={props.detail.preflight}
        targetFileCount={props.detail.target_file_count}
        taskCount={props.detail.task_count}
        overlapFileCount={props.detail.overlap_file_count}
        onRunPreflight={props.onRunPreflight}
        isRunning={props.isRunningPreflight}
        helperText="Day08 在这里执行风险分类与人工确认预检；即使结果为“可进入执行”，当前也不会扩展到验证运行、证据包或真实 Git 写操作。"
      />

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="任务数" value={String(props.detail.task_count)} />
        <MetricCard label="目标文件" value={String(props.detail.target_file_count)} />
        <MetricCard
          label="重叠提醒"
          value={String(props.detail.overlap_file_count)}
          tone={props.detail.overlap_file_count > 0 ? "warning" : "success"}
        />
        <MetricCard
          label="验证命令"
          value={String(props.detail.verification_command_count)}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.9fr)]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="text-sm font-semibold text-slate-50">任务执行顺序</div>
          <div className="mt-2 text-sm leading-6 text-slate-400">
            任务顺序由批次内依赖自动排序；Day08 只在执行前做风险分类和人工确认，不直接运行代码修改。
          </div>

          <div className="mt-4 space-y-3">
            {props.detail.tasks.map((task) => (
              <div
                key={task.task_id}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge label={`步骤 ${task.order_index}`} tone="info" />
                      <div className="text-sm font-medium text-slate-50">{task.task_title}</div>
                      <StatusBadge label={`v${task.selected_version_number}`} tone="warning" />
                      <StatusBadge
                        label={`重叠 ${task.overlap_file_paths.length}`}
                        tone={task.overlap_file_paths.length > 0 ? "warning" : "success"}
                      />
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-300">
                      {task.intent_summary}
                    </div>
                    <div className="mt-2 text-xs leading-5 text-slate-500">
                      ChangePlan：{task.change_plan_title} · 风险 {task.task_risk_level} · 优先级{" "}
                      {task.task_priority}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {task.related_deliverables.map((deliverable) => (
                      <StatusBadge
                        key={`${task.task_id}-${deliverable.deliverable_id}`}
                        label={deliverable.title}
                        tone="neutral"
                      />
                    ))}
                  </div>
                </div>

                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      依赖关系
                    </div>
                    {task.dependencies.length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {task.dependencies.map((dependency) => (
                          <StatusBadge
                            key={`${task.task_id}-${dependency.task_id}`}
                            label={
                              dependency.in_batch && dependency.order_index
                                ? `${dependency.task_title} (#${dependency.order_index})`
                                : dependency.task_title
                            }
                            tone={
                              dependency.missing
                                ? "danger"
                                : dependency.in_batch
                                  ? "warning"
                                  : "neutral"
                            }
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="mt-2 text-sm leading-6 text-slate-400">无前置依赖。</div>
                    )}
                  </div>

                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      预期动作
                    </div>
                    <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-300">
                      {task.expected_actions.map((action) => (
                        <li key={`${task.task_id}-${action}`}>• {action}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {task.target_files.map((targetFile) => (
                    <StatusBadge
                      key={`${task.task_id}-${targetFile.relative_path}`}
                      label={targetFile.relative_path}
                      tone={
                        task.overlap_file_paths.includes(targetFile.relative_path)
                          ? "warning"
                          : "neutral"
                      }
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-4">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="text-sm font-semibold text-slate-50">文件重叠风险</div>
          <div className="mt-2 text-sm leading-6 text-slate-400">
              这里继续提示同一批次内多个 ChangePlan 指向同一文件的情况；Day08 的更高风险分类会在上方预检区统一展示。
          </div>

            {props.detail.overlap_files.length > 0 ? (
              <div className="mt-4 space-y-3">
                {props.detail.overlap_files.map((item) => (
                  <FileAggregateCard
                    key={item.relative_path}
                    item={item}
                    tone="warning"
                  />
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm leading-6 text-emerald-100">
                当前批次未发现文件重叠，可以继续保持 Day07 的范围收口。
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="text-sm font-semibold text-slate-50">本轮准备改动文件</div>
            <div className="mt-2 text-sm leading-6 text-slate-400">
              汇总所有选中 ChangePlan 的目标文件，帮助后续执行前快速锁定范围。
            </div>

            <div className="mt-4 space-y-3">
              {props.detail.target_files.map((item) => (
                <FileAggregateCard
                  key={item.relative_path}
                  item={item}
                  tone={item.overlap_count > 1 ? "warning" : "neutral"}
                />
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="text-sm font-semibold text-slate-50">批次时间线</div>
            <div className="mt-2 text-sm leading-6 text-slate-400">
              这里会同时沉淀 ChangeBatch 创建、Day08 预检结果和人工确认结论，仍不扩展到 Day09+ 的验证与证据链路。
            </div>

            <div className="mt-4 space-y-3">
              {props.detail.timeline.map((item) => (
                <div
                  key={`${item.entry_type}-${item.label}-${item.occurred_at}`}
                  className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium text-slate-100">{item.label}</div>
                    <span className="text-xs text-slate-500">
                      {formatDateTime(item.occurred_at)}
                    </span>
                  </div>
                  <div className="mt-2 text-sm leading-6 text-slate-300">{item.summary}</div>
                </div>
              ))}
            </div>
          </section>
        </section>
      </div>
    </div>
  );
}

function FileAggregateCard(props: {
  item: ChangeBatchTargetFileAggregate;
  tone: "neutral" | "warning";
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="break-all text-sm font-medium text-slate-100">
          {props.item.relative_path}
        </div>
        <StatusBadge
          label={`涉及 ${props.item.task_titles.length} 任务`}
          tone={props.tone === "warning" ? "warning" : "neutral"}
        />
      </div>
      <div className="mt-2 text-xs leading-5 text-slate-500">
        {props.item.language} / {props.item.file_type}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {props.item.task_titles.map((taskTitle) => (
          <StatusBadge
            key={`${props.item.relative_path}-${taskTitle}`}
            label={taskTitle}
            tone={props.tone === "warning" ? "warning" : "info"}
          />
        ))}
      </div>
      {props.item.match_reasons.length > 0 ? (
        <div className="mt-3 text-xs leading-5 text-slate-400">
          命中原因：{props.item.match_reasons.join(" / ")}
        </div>
      ) : null}
    </div>
  );
}

function MetricCard(props: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "warning";
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div
        className={`mt-2 text-sm font-semibold ${
          props.tone === "warning"
            ? "text-amber-100"
            : props.tone === "success"
              ? "text-emerald-100"
              : "text-slate-100"
        }`}
      >
        {props.value}
      </div>
    </div>
  );
}

function Alert(props: {
  tone: "danger";
  message: string;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
      {props.message}
    </div>
  );
}

function mapBatchStatusTone(
  status: ChangeBatchSummary["status"],
): "neutral" | "success" | "warning" {
  switch (status) {
    case "preparing":
      return "warning";
    case "superseded":
      return "neutral";
    default:
      return "success";
  }
}
