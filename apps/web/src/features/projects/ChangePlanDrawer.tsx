import { type FormEvent, useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useProjectDeliverableSnapshot } from "../deliverables/hooks";
import { DELIVERABLE_TYPE_LABELS } from "../deliverables/types";
import type { CodeContextPack } from "../repositories/types";
import {
  useAppendChangePlanVersion,
  useChangePlanDetail,
  useCreateProjectChangePlan,
} from "./hooks";
import type {
  ChangePlanDraftInput,
  ChangePlanSummary,
  ChangePlanTargetFile,
  ProjectDetailTaskItem,
} from "./types";

type ChangePlanDrawerProps = {
  open: boolean;
  projectId: string | null;
  tasks: ProjectDetailTaskItem[];
  initialTaskId: string | null;
  codeContextPack: CodeContextPack | null;
  changePlans: ChangePlanSummary[];
  onClose: () => void;
};

export function ChangePlanDrawer(props: ChangePlanDrawerProps) {
  const deliverablesQuery = useProjectDeliverableSnapshot(props.projectId);
  const createMutation = useCreateProjectChangePlan(props.projectId);
  const appendVersionMutation = useAppendChangePlanVersion();

  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [primaryDeliverableId, setPrimaryDeliverableId] = useState("");
  const [selectedDeliverableIds, setSelectedDeliverableIds] = useState<string[]>([]);
  const [intentSummary, setIntentSummary] = useState("");
  const [expectedActionsText, setExpectedActionsText] = useState("");
  const [riskNotesText, setRiskNotesText] = useState("");
  const [verificationCommandsText, setVerificationCommandsText] = useState("");
  const [selectedTargetPaths, setSelectedTargetPaths] = useState<string[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const changePlanDetailQuery = useChangePlanDetail(
    props.open ? selectedPlanId : null,
  );
  const selectedPlanDetail = changePlanDetailQuery.data ?? null;
  const deliverables = deliverablesQuery.data?.deliverables ?? [];

  const changePlansForTask = useMemo(
    () => props.changePlans.filter((item) => item.task_id === selectedTaskId),
    [props.changePlans, selectedTaskId],
  );

  const selectedTask =
    props.tasks.find((task) => task.id === selectedTaskId) ?? null;

  const packTargetFiles = useMemo<ChangePlanTargetFile[]>(
    () =>
      props.codeContextPack?.entries.map((entry) => ({
        relative_path: entry.relative_path,
        language: entry.language,
        file_type: entry.file_type,
        rationale: null,
        match_reasons: entry.match_reasons,
      })) ?? [],
    [props.codeContextPack],
  );

  const activeBaselineVersion = selectedPlanDetail?.versions[0] ?? null;
  const activeSourceSummary =
    props.codeContextPack?.source_summary ??
    activeBaselineVersion?.source_summary ??
    "";
  const activeFocusTerms =
    props.codeContextPack?.focus_terms ?? activeBaselineVersion?.focus_terms ?? [];
  const activeContextPackGeneratedAt =
    props.codeContextPack?.generated_at ??
    activeBaselineVersion?.context_pack_generated_at ??
    null;
  const activeTargetFiles = useMemo<ChangePlanTargetFile[]>(() => {
    if (props.codeContextPack) {
      return packTargetFiles;
    }
    return activeBaselineVersion?.target_files ?? [];
  }, [activeBaselineVersion, packTargetFiles, props.codeContextPack]);

  useEffect(() => {
    if (!props.open) {
      return;
    }

    const fallbackTaskId = props.initialTaskId ?? props.tasks[0]?.id ?? "";
    setSelectedTaskId((current) => {
      if (current && props.tasks.some((task) => task.id === current)) {
        return current;
      }
      return fallbackTaskId;
    });
  }, [props.initialTaskId, props.open, props.tasks]);

  useEffect(() => {
    if (!props.open) {
      setSelectedPlanId(null);
      setErrorMessage(null);
      setSuccessMessage(null);
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
  }, [props.open]);

  useEffect(() => {
    if (!props.open) {
      return;
    }

    if (selectedPlanId && !selectedPlanDetail && changePlanDetailQuery.isLoading) {
      return;
    }

    const firstDeliverableId = deliverables[0]?.id ?? "";
    if (selectedPlanDetail) {
      const latestVersion = selectedPlanDetail.versions[0];
      const nextDeliverableIds = latestVersion.related_deliverables.map(
        (item) => item.deliverable_id,
      );
      setSelectedTaskId(selectedPlanDetail.task_id);
      setTitle(selectedPlanDetail.title);
      setSelectedDeliverableIds(nextDeliverableIds);
      setPrimaryDeliverableId(
        selectedPlanDetail.primary_deliverable_id ??
          nextDeliverableIds[0] ??
          firstDeliverableId,
      );
      setIntentSummary(latestVersion.intent_summary);
      setExpectedActionsText(latestVersion.expected_actions.join("\n"));
      setRiskNotesText(latestVersion.risk_notes.join("\n"));
      setVerificationCommandsText(latestVersion.verification_commands.join("\n"));
      setSelectedTargetPaths(
        (props.codeContextPack ? packTargetFiles : latestVersion.target_files).map(
          (item) => item.relative_path,
        ),
      );
      return;
    }

    setTitle("");
    setSelectedDeliverableIds(firstDeliverableId ? [firstDeliverableId] : []);
    setPrimaryDeliverableId(firstDeliverableId);
    setIntentSummary("");
    setExpectedActionsText("");
    setRiskNotesText("");
    setVerificationCommandsText("");
    setSelectedTargetPaths(packTargetFiles.map((item) => item.relative_path));
  }, [
    changePlanDetailQuery.isLoading,
    deliverables,
    packTargetFiles,
    props.codeContextPack,
    props.open,
    selectedPlanDetail,
    selectedPlanId,
  ]);

  useEffect(() => {
    if (!primaryDeliverableId) {
      if (selectedDeliverableIds[0]) {
        setPrimaryDeliverableId(selectedDeliverableIds[0]);
      }
      return;
    }

    if (!selectedDeliverableIds.includes(primaryDeliverableId)) {
      setSelectedDeliverableIds((current) => [primaryDeliverableId, ...current]);
    }
  }, [primaryDeliverableId, selectedDeliverableIds]);

  if (!props.open) {
    return null;
  }

  const isSaving = createMutation.isPending || appendVersionMutation.isPending;
  const canCreateNewDraft = Boolean(props.codeContextPack);
  const selectedPlanSummary =
    props.changePlans.find((item) => item.id === selectedPlanId) ?? null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!props.projectId) {
      setErrorMessage("当前没有可创建变更计划草案的项目。");
      return;
    }
    if (!selectedTaskId) {
      setErrorMessage("请先选择一个任务。");
      return;
    }

    const deliverableIds = Array.from(
      new Set(
        [primaryDeliverableId, ...selectedDeliverableIds].filter(
          (item): item is string => Boolean(item),
        ),
      ),
    );
    const expectedActions = parseLineItems(expectedActionsText);
    const riskNotes = parseLineItems(riskNotesText);
    const verificationCommands = parseLineItems(verificationCommandsText);
    const targetFiles = activeTargetFiles.filter((item) =>
      selectedTargetPaths.includes(item.relative_path),
    );

    if (deliverableIds.length === 0) {
      setErrorMessage("请至少关联一个交付件。");
      return;
    }
    if (!intentSummary.trim()) {
      setErrorMessage("请填写本次变更意图。");
      return;
    }
    if (!activeSourceSummary.trim()) {
      setErrorMessage("当前缺少 Day05 CodeContextPack 或上一版映射来源，无法生成草案。");
      return;
    }
    if (targetFiles.length === 0) {
      setErrorMessage("请至少保留一个目标文件。");
      return;
    }
    if (expectedActions.length === 0) {
      setErrorMessage("请至少填写一条预期动作。");
      return;
    }
    if (riskNotes.length === 0) {
      setErrorMessage("请至少填写一条风险说明。");
      return;
    }
    if (verificationCommands.length === 0) {
      setErrorMessage("请至少填写一条验证命令。");
      return;
    }

    const payload: ChangePlanDraftInput = {
      title: title.trim() || null,
      primary_deliverable_id: primaryDeliverableId || null,
      related_deliverable_ids: deliverableIds,
      intent_summary: intentSummary.trim(),
      source_summary: activeSourceSummary,
      focus_terms: activeFocusTerms,
      target_files: targetFiles,
      expected_actions: expectedActions,
      risk_notes: riskNotes,
      verification_commands: verificationCommands,
      context_pack_generated_at: activeContextPackGeneratedAt,
    };

    try {
      if (selectedPlanId) {
        const result = await appendVersionMutation.mutateAsync({
          changePlanId: selectedPlanId,
          payload,
        });
        setSelectedPlanId(result.id);
        setSuccessMessage(`已追加 v${result.current_version_number} 变更计划草案。`);
      } else {
        const result = await createMutation.mutateAsync({
          ...payload,
          task_id: selectedTaskId,
        });
        setSelectedPlanId(result.id);
        setSuccessMessage(`已创建变更计划草案《${result.title}》。`);
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "变更计划草案保存失败，请稍后重试。",
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/75 backdrop-blur-sm">
      <button
        type="button"
        aria-label="关闭变更计划抽屉"
        className="flex-1 cursor-default"
        onClick={props.onClose}
      />

      <aside className="flex h-full w-full max-w-5xl flex-col border-l border-slate-800 bg-slate-950 shadow-2xl shadow-slate-950/70">
        <header className="border-b border-slate-800 px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-cyan-300">
                Day06 ChangePlan
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-slate-50">
                仓库任务映射与变更计划草案
              </h2>
            </div>

            <div className="flex flex-wrap gap-2">
              <StatusBadge
                label={selectedPlanId ? "追加版本" : "新建草案"}
                tone={selectedPlanId ? "warning" : "success"}
              />
              <StatusBadge
                label={
                  props.codeContextPack
                    ? `CodeContextPack ${props.codeContextPack.included_file_count} 文件`
                    : "沿用上一版映射"
                }
                tone={props.codeContextPack ? "info" : "neutral"}
              />
            </div>
          </div>

          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            Day06 只把任务、交付件与候选文件集合整理成结构化草案，不进入 Day07
            变更批次、Day08 风险预检，也不会在产品链路里执行真实 Git 写操作。
          </p>
        </header>

        <div className="grid flex-1 gap-0 lg:grid-cols-[280px_minmax(0,1fr)]">
          <section className="border-b border-slate-800 px-6 py-5 lg:border-b-0 lg:border-r">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              任务映射
            </div>
            <select
              value={selectedTaskId}
              onChange={(event) => {
                setSelectedTaskId(event.target.value);
                setSelectedPlanId(null);
              }}
              disabled={Boolean(selectedPlanId)}
              className="mt-3 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
            >
              {props.tasks.length === 0 ? <option value="">暂无任务</option> : null}
              {props.tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>

            {selectedTask ? (
              <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm leading-6 text-slate-300">
                <div className="font-medium text-slate-100">{selectedTask.title}</div>
                <div className="mt-2">{selectedTask.input_summary}</div>
                <div className="mt-2 text-xs text-slate-500">
                  更新时间 {formatDateTime(selectedTask.updated_at)}
                </div>
              </div>
            ) : (
              <div className="mt-3 rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-4 text-sm leading-6 text-slate-400">
                当前项目还没有可映射的任务。
              </div>
            )}

            <div className="mt-5 flex items-center justify-between gap-3">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                草案历史
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedPlanId(null);
                  setSuccessMessage(null);
                  setErrorMessage(null);
                }}
                disabled={!canCreateNewDraft}
                className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
              >
                新建草案
              </button>
            </div>

            <div className="mt-3 space-y-3">
              {changePlansForTask.length > 0 ? (
                changePlansForTask.map((item) => {
                  const isSelected = item.id === selectedPlanId;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedPlanId(item.id)}
                      className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                        isSelected
                          ? "border-cyan-400/60 bg-cyan-500/10"
                          : "border-slate-800 bg-slate-900/60 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-medium text-slate-100">
                          {item.title}
                        </div>
                        <StatusBadge label={`v${item.current_version_number}`} tone="info" />
                      </div>
                      <div className="mt-2 text-xs leading-5 text-slate-400">
                        {item.latest_version.intent_summary}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
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
                })
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-4 text-sm leading-6 text-slate-400">
                  {canCreateNewDraft
                    ? "当前任务还没有变更计划草案，可以直接从当前 CodeContextPack 新建。"
                    : "请先在仓库页通过 Day05 FileLocator 生成 CodeContextPack，再新建 Day06 草案。"}
                </div>
              )}
            </div>
          </section>

          <form onSubmit={handleSubmit} className="flex min-h-0 flex-col">
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-100">当前映射来源</div>
                    <div className="mt-2 text-sm leading-6 text-slate-300">
                      {activeSourceSummary || "尚未提供映射来源。"}
                    </div>
                    {activeContextPackGeneratedAt ? (
                      <div className="mt-2 text-xs text-slate-500">
                        来源时间 {formatDateTime(activeContextPackGeneratedAt)}
                      </div>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {activeFocusTerms.map((term) => (
                      <StatusBadge key={term} label={`焦点 ${term}`} tone="neutral" />
                    ))}
                  </div>
                </div>

                {props.codeContextPack ? (
                  <div className="mt-3 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm leading-6 text-cyan-100">
                    本次保存将优先使用当前 CodeContextPack 中已收敛的文件集合作为 Day06 输入。
                  </div>
                ) : selectedPlanSummary ? (
                  <div className="mt-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
                    当前没有新的 CodeContextPack，将沿用《{selectedPlanSummary.title}》最新版本中的目标文件与来源摘要继续追加版本。
                  </div>
                ) : (
                  <div className="mt-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
                    新建草案需要先在 Day05 FileLocator 中生成 CodeContextPack。
                  </div>
                )}
              </section>

              <div className="mt-5 grid gap-5 xl:grid-cols-2">
                <FieldBlock
                  label="草案标题"
                  description="默认会按“任务 / 交付件 / 变更计划”自动生成，可按需覆写。"
                >
                  <input
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
                  />
                </FieldBlock>

                <FieldBlock
                  label="主交付件"
                  description="同一交付件可持续累积多版草案；Day06 只做草案，不进入提交候选。"
                >
                  <select
                    value={primaryDeliverableId}
                    onChange={(event) => setPrimaryDeliverableId(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
                  >
                    {deliverables.length === 0 ? <option value="">暂无交付件</option> : null}
                    {deliverables.map((deliverable) => (
                      <option key={deliverable.id} value={deliverable.id}>
                        {deliverable.title} · v{deliverable.current_version_number}
                      </option>
                    ))}
                  </select>
                </FieldBlock>
              </div>

              <FieldBlock
                className="mt-5"
                label="关联交付件"
                description="至少保留一个交付件，供项目详情和后续时间线反查映射关系。"
              >
                {deliverables.length > 0 ? (
                  <div className="space-y-3">
                    {deliverables.map((deliverable) => {
                      const checked = selectedDeliverableIds.includes(deliverable.id);
                      return (
                        <label
                          key={deliverable.id}
                          className="flex items-start gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => {
                              setSelectedDeliverableIds((current) => {
                                if (checked) {
                                  const next = current.filter((item) => item !== deliverable.id);
                                  if (primaryDeliverableId === deliverable.id) {
                                    setPrimaryDeliverableId(next[0] ?? "");
                                  }
                                  return next;
                                }
                                return [...current, deliverable.id];
                              });
                            }}
                            className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-sm font-medium text-slate-100">
                                {deliverable.title}
                              </div>
                              <StatusBadge
                                label={DELIVERABLE_TYPE_LABELS[deliverable.type] ?? deliverable.type}
                                tone="info"
                              />
                              <StatusBadge label={`v${deliverable.current_version_number}`} tone="neutral" />
                            </div>
                            <div className="mt-2 text-xs leading-5 text-slate-500">
                              {deliverable.latest_version.summary}
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-400">
                    当前项目还没有可关联的交付件，请先在交付件中心补齐最小产物。
                  </div>
                )}
              </FieldBlock>

              <FieldBlock
                className="mt-5"
                label="本次变更意图"
                description="说明为什么要改、准备改到什么程度；Day06 只写草案，不展开到实际代码执行。"
              >
                <textarea
                  value={intentSummary}
                  onChange={(event) => setIntentSummary(event.target.value)}
                  rows={5}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                />
              </FieldBlock>

              <div className="mt-5 grid gap-5 xl:grid-cols-3">
                <FieldBlock
                  label="预期动作"
                  description="一行一条，例如“更新仓储层查询”“补前端抽屉展示”。"
                >
                  <textarea
                    value={expectedActionsText}
                    onChange={(event) => setExpectedActionsText(event.target.value)}
                    rows={8}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                  />
                </FieldBlock>

                <FieldBlock
                  label="风险说明"
                  description="Day06 只记录风险，不做 Day08 的预检守卫与人工确认。"
                >
                  <textarea
                    value={riskNotesText}
                    onChange={(event) => setRiskNotesText(event.target.value)}
                    rows={8}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                  />
                </FieldBlock>

                <FieldBlock
                  label="验证命令引用"
                  description="一行一条，例如“python -m pytest ...”或“npm run build”。"
                >
                  <textarea
                    value={verificationCommandsText}
                    onChange={(event) => setVerificationCommandsText(event.target.value)}
                    rows={8}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                  />
                </FieldBlock>
              </div>

              <FieldBlock
                className="mt-5"
                label="目标文件集合"
                description="这里直接消费 Day05 的候选文件 / CodeContextPack，不提前进入 Day07 变更批次。"
              >
                {activeTargetFiles.length > 0 ? (
                  <div className="space-y-3">
                    {activeTargetFiles.map((item) => {
                      const checked = selectedTargetPaths.includes(item.relative_path);
                      return (
                        <label
                          key={item.relative_path}
                          className="flex items-start gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() =>
                              setSelectedTargetPaths((current) =>
                                checked
                                  ? current.filter((path) => path !== item.relative_path)
                                  : [...current, item.relative_path],
                              )
                            }
                            className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="break-all text-sm font-medium text-slate-100">
                              {item.relative_path}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <StatusBadge label={item.language} tone="success" />
                              <StatusBadge label={item.file_type} tone="warning" />
                              {item.match_reasons.map((reason) => (
                                <StatusBadge
                                  key={`${item.relative_path}-${reason}`}
                                  label={reason}
                                  tone="neutral"
                                />
                              ))}
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-400">
                    暂无目标文件；请先在 Day05 中生成 CodeContextPack，或先打开已有草案查看上一版映射。
                  </div>
                )}
              </FieldBlock>

              {selectedPlanDetail ? (
                <FieldBlock
                  className="mt-5"
                  label="版本时间线"
                  description="同一交付件下可连续沉淀多版草案，为 Day07 变更批次保留时间线。"
                >
                  <div className="space-y-3">
                    {selectedPlanDetail.versions.map((version) => (
                      <div
                        key={version.id}
                        className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-medium text-slate-100">
                            v{version.version_number}
                          </div>
                          <StatusBadge label={`${version.target_files.length} 文件`} tone="info" />
                          <StatusBadge
                            label={`${version.verification_commands.length} 验证命令`}
                            tone="warning"
                          />
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-300">
                          {version.intent_summary}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {version.related_deliverables.map((deliverable) => (
                            <StatusBadge
                              key={`${version.id}-${deliverable.deliverable_id}`}
                              label={deliverable.title}
                              tone="neutral"
                            />
                          ))}
                        </div>
                        <div className="mt-2 text-xs text-slate-500">
                          创建于 {formatDateTime(version.created_at)}
                        </div>
                      </div>
                    ))}
                  </div>
                </FieldBlock>
              ) : null}

              {errorMessage ? (
                <div className="mt-5 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
                  {errorMessage}
                </div>
              ) : null}

              {successMessage ? (
                <div className="mt-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm leading-6 text-emerald-100">
                  {successMessage}
                </div>
              ) : null}
            </div>

            <footer className="flex items-center justify-between gap-3 border-t border-slate-800 px-6 py-4">
              <button
                type="button"
                onClick={props.onClose}
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
              >
                关闭
              </button>

              <button
                type="submit"
                disabled={isSaving || (!selectedPlanId && !canCreateNewDraft)}
                className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
              >
                {isSaving ? "保存中..." : selectedPlanId ? "追加草案版本" : "创建草案"}
              </button>
            </footer>
          </form>
        </div>
      </aside>
    </div>
  );
}

function FieldBlock(props: {
  label: string;
  description: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`${props.className ?? ""} rounded-2xl border border-slate-800 bg-slate-900/60 p-4`}
    >
      <div className="text-sm font-medium text-slate-100">{props.label}</div>
      <div className="mt-1 text-xs leading-5 text-slate-400">
        {props.description}
      </div>
      <div className="mt-3">{props.children}</div>
    </section>
  );
}

function parseLineItems(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter((item, index, collection) => item.length > 0 && collection.indexOf(item) === index);
}
