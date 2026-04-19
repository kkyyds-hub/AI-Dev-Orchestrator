import { StatusBadge } from "../../components/StatusBadge";
import {
  buildLatestRunRuntimeFields,
  buildRoleModelPolicyRuntimeFields,
  hasRoleModelPolicyRuntimeData,
} from "../../lib/latestRunRuntimeContract";
import { mapBudgetPressureTone } from "../../lib/status";
import { navigateToProjectOverviewHash } from "../projects/lib/overviewNavigation";
import type {
  BossDrilldownContext,
  BossProjectLatestTask,
} from "../projects/types";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { useProjectStrategyPreview } from "./hooks";

type StrategyDecisionPanelProps = {
  projectId: string | null;
  drilldownContext?: BossDrilldownContext | null;
  latestRunTaskSample?: BossProjectLatestTask | null;
  onNavigateToProjectLatestRun?: (() => void) | null;
  onNavigateToTaskDetail?: (
    taskId: string,
    options?: { runId?: string | null },
  ) => void;
};

const MODEL_TIER_LABELS: Record<string, string> = {
  economy: "经济",
  balanced: "均衡",
  premium: "高质量",
};

export function StrategyDecisionPanel(props: StrategyDecisionPanelProps) {
  const previewQuery = useProjectStrategyPreview(props.projectId);
  const latestRunRuntimeInput = props.latestRunTaskSample
    ? {
        providerKey: props.latestRunTaskSample.latest_run_provider_key,
        promptTemplateKey: props.latestRunTaskSample.latest_run_prompt_template_key,
        promptTemplateVersion: props.latestRunTaskSample.latest_run_prompt_template_version,
        tokenAccountingMode: props.latestRunTaskSample.latest_run_token_accounting_mode,
        tokenPricingSource: props.latestRunTaskSample.latest_run_token_pricing_source,
        promptCharCount: props.latestRunTaskSample.latest_run_prompt_char_count,
        promptTokens: props.latestRunTaskSample.latest_run_prompt_tokens,
        completionTokens: props.latestRunTaskSample.latest_run_completion_tokens,
        totalTokens: props.latestRunTaskSample.latest_run_total_tokens,
        estimatedCost: props.latestRunTaskSample.latest_run_estimated_cost,
        providerReceiptId: props.latestRunTaskSample.latest_run_provider_receipt_id,
        roleModelPolicySource: props.latestRunTaskSample.latest_run_role_model_policy_source,
        roleModelPolicyDesiredTier:
          props.latestRunTaskSample.latest_run_role_model_policy_desired_tier,
        roleModelPolicyAdjustedTier:
          props.latestRunTaskSample.latest_run_role_model_policy_adjusted_tier,
        roleModelPolicyFinalTier: props.latestRunTaskSample.latest_run_role_model_policy_final_tier,
        roleModelPolicyStageOverrideApplied:
          props.latestRunTaskSample.latest_run_role_model_policy_stage_override_applied,
      }
    : null;
  const latestRunRuntimeFields = latestRunRuntimeInput
    ? buildLatestRunRuntimeFields(latestRunRuntimeInput)
    : [];
  const latestRunPolicyFields = latestRunRuntimeInput
    ? buildRoleModelPolicyRuntimeFields(latestRunRuntimeInput)
    : [];
  const hasLatestRunPolicyData = latestRunRuntimeInput
    ? hasRoleModelPolicyRuntimeData(latestRunRuntimeInput)
    : false;

  if (!props.projectId) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          Strategy Preview
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          请选择一个项目后查看角色、模型和 Skill 的路由预览。
        </p>
      </section>
    );
  }

  if (previewQuery.isLoading) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          Strategy Preview
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          正在计算当前项目的策略预览...
        </p>
      </section>
    );
  }

  if (previewQuery.isError || !previewQuery.data) {
    return (
      <section className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-rose-200">
          Strategy Preview
        </div>
        <p className="mt-3 text-sm leading-6 text-rose-100">
          策略预览加载失败：
          {previewQuery.error instanceof Error ? previewQuery.error.message : "未知错误"}
        </p>
      </section>
    );
  }

  const preview = previewQuery.data;
  const drilldownTaskMatchesRuntimeSample =
    !props.drilldownContext?.task_id ||
    !props.latestRunTaskSample?.task_id ||
    props.drilldownContext.task_id === props.latestRunTaskSample.task_id;
  const drilldownRunMatchesLatest =
    !props.drilldownContext?.run_id ||
    !props.latestRunTaskSample?.latest_run_id ||
    props.drilldownContext.run_id === props.latestRunTaskSample.latest_run_id;

  return (
    <section
      id="strategy-preview-panel"
      data-testid="strategy-preview-panel"
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Strategy Preview
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">
            {preview.project_name}
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {preview.strategy_summary ?? preview.message}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={PROJECT_STAGE_LABELS[preview.project_stage] ?? preview.project_stage}
            tone="info"
          />
          <StatusBadge
            label={`预算 ${preview.budget_pressure_level}`}
            tone={mapBudgetPressureTone(preview.budget_pressure_level)}
          />
          {preview.model_tier ? (
            <StatusBadge
              label={`模型 ${MODEL_TIER_LABELS[preview.model_tier] ?? preview.model_tier}`}
              tone="success"
            />
          ) : null}
          {preview.owner_role_code ? (
            <StatusBadge
              label={`责任 ${ROLE_CODE_LABELS[preview.owner_role_code] ?? preview.owner_role_code}`}
              tone="warning"
            />
          ) : null}
          <button
            type="button"
            data-testid="goto-agent-thread-from-strategy-preview"
            onClick={scrollToAgentThreadControlSurface}
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
          >
            Open Agent Thread
          </button>
          <button
            type="button"
            data-testid="goto-team-control-center-from-strategy-preview"
            onClick={scrollToTeamControlCenterSurface}
            className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-100 transition hover:bg-emerald-500/20"
          >
            Open Team Control
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <InfoCard
          label="当前选中的任务"
          value={preview.selected_task_title ?? "当前没有可路由任务"}
          extra={preview.selected_task_id ? `任务 ID：${preview.selected_task_id}` : undefined}
        />
        <InfoCard
          label="模型 / 规则"
          value={
            preview.model_name
              ? `${preview.model_name}${preview.strategy_code ? ` · ${preview.strategy_code}` : ""}`
              : "尚未选出模型"
          }
          extra={preview.budget_strategy_summary}
        />
      </div>

      {props.drilldownContext ? (
        <div
          data-testid="strategy-preview-drilldown-status"
          className={`mt-4 rounded-xl border p-3 text-xs ${
            drilldownTaskMatchesRuntimeSample && drilldownRunMatchesLatest
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
              : "border-amber-500/30 bg-amber-500/10 text-amber-100"
          }`}
        >
          <div className="font-medium">
            {drilldownTaskMatchesRuntimeSample && drilldownRunMatchesLatest
              ? "Strategy preview is aligned with the current drill-down context."
              : "Strategy preview context differs from the incoming drill-down sample."}
          </div>
          <div className="mt-1">
            source={props.drilldownContext.source}; task={props.drilldownContext.task_id}; run=
            {props.drilldownContext.run_id ?? "n/a"}
          </div>
        </div>
      ) : null}

      {props.latestRunTaskSample ? (
        <div
          data-testid="strategy-preview-runtime-context"
          className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4"
        >
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
            Linked Latest Run Runtime Context
          </div>
          <p className="mt-2 text-xs text-slate-300">
            Task {props.latestRunTaskSample.task_id}; Run{" "}
            {props.latestRunTaskSample.latest_run_id ?? "n/a"}
          </p>
          {props.onNavigateToProjectLatestRun || props.onNavigateToTaskDetail ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {props.onNavigateToProjectLatestRun ? (
                <button
                  type="button"
                  data-testid="goto-project-latest-run-from-strategy-preview"
                  onClick={props.onNavigateToProjectLatestRun}
                  className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
                >
                  Back to Project Latest Run
                </button>
              ) : null}
              <button
                type="button"
                data-testid="goto-task-detail-from-strategy-preview"
                onClick={() => {
                  if (!props.latestRunTaskSample) {
                    return;
                  }
                  props.onNavigateToTaskDetail?.(props.latestRunTaskSample.task_id, {
                    runId: props.latestRunTaskSample.latest_run_id ?? null,
                  });
                }}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
              >
                Drill-down to Task Detail / Run Log
              </button>
              {props.latestRunTaskSample.latest_run_id ? (
                <button
                  type="button"
                  data-testid="goto-run-log-from-strategy-preview"
                  onClick={() => {
                    if (!props.latestRunTaskSample?.latest_run_id) {
                      return;
                    }
                    props.onNavigateToTaskDetail?.(props.latestRunTaskSample.task_id, {
                      runId: props.latestRunTaskSample.latest_run_id,
                    });
                  }}
                  className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
                >
                  Drill-down to Run Log
                </button>
              ) : null}
            </div>
          ) : null}
          <div
            data-testid="strategy-preview-runtime-card"
            className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5"
          >
            {latestRunRuntimeFields.map((field) => (
              <InfoCard
                key={field.key}
                testId={`strategy-preview-runtime-field-${field.key}`}
                label={field.label}
                value={field.value}
              />
            ))}
          </div>
          {hasLatestRunPolicyData ? (
            <div
              data-testid="strategy-preview-policy-card"
              className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3"
            >
              <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
                Linked Role Model Policy Runtime
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {latestRunPolicyFields.map((field) => (
                  <InfoCard
                    key={field.key}
                    testId={`strategy-preview-policy-field-${field.key}`}
                    label={field.label}
                    value={field.value}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {preview.owner_role_code || preview.model_tier || preview.model_name ? (
        <div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
            Role Model Policy 命中
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            当前策略预览已经把“责任角色 → 模型层级 → 最终模型”收敛成最小运行时结果；
            Worker 真正执行时会沿用同一条策略主链。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <InfoCard
              label="责任角色"
              value={
                preview.owner_role_code
                  ? ROLE_CODE_LABELS[preview.owner_role_code] ?? preview.owner_role_code
                  : "未分配"
              }
            />
            <InfoCard
              label="命中层级"
              value={
                preview.model_tier
                  ? MODEL_TIER_LABELS[preview.model_tier] ?? preview.model_tier
                  : "未命中"
              }
            />
            <InfoCard label="最终模型" value={preview.model_name ?? "未选择"} />
            <InfoCard
              label="策略代码"
              value={preview.strategy_code ?? "未生成"}
              extra={preview.dispatch_status ?? undefined}
            />
          </div>
        </div>
      ) : null}

      {preview.role_model_policy_runtime.source ? (
        <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-emerald-200">
            Role Model Policy Runtime Trace
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <InfoCard
              label="Policy Source"
              value={preview.role_model_policy_runtime.source}
            />
            <InfoCard
              label="Desired Tier"
              value={preview.role_model_policy_runtime.desired_tier ?? "n/a"}
            />
            <InfoCard
              label="Adjusted Tier"
              value={preview.role_model_policy_runtime.adjusted_tier ?? "n/a"}
            />
            <InfoCard
              label="Final Tier"
              value={preview.role_model_policy_runtime.final_tier ?? "n/a"}
              extra={
                preview.role_model_policy_runtime.stage_override_applied
                  ? "Stage override applied"
                  : "No stage override"
              }
            />
          </div>
        </div>
      ) : null}

      {preview.route_reason ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            路由说明
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{preview.route_reason}</p>
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              解释性理由
            </div>
            {preview.routing_score !== null ? (
              <span className="text-xs text-cyan-200">
                路由分数 {preview.routing_score.toFixed(1)}
              </span>
            ) : null}
          </div>

          {preview.strategy_reasons.length > 0 ? (
            <div className="mt-3 space-y-3">
              {preview.strategy_reasons.map((reason) => (
                <div
                  key={reason.code}
                  className="rounded-xl border border-slate-800 bg-slate-950/70 p-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-100">
                      {reason.label}
                    </div>
                    {reason.score !== null ? (
                      <span className="text-xs text-slate-500">
                        {reason.score > 0 ? "+" : ""}
                        {reason.score.toFixed(1)}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {reason.detail}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-400">
              当前没有额外的解释性理由。
            </p>
          )}

          {preview.selected_skill_names.length > 0 ? (
            <div className="mt-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                选中的 Skill
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {preview.selected_skill_names.map((skillName, index) => (
                  <span
                    key={`${skillName}-${preview.selected_skill_codes[index] ?? index}`}
                    className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100"
                  >
                    {skillName}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            候选任务对比
          </div>
          {preview.candidates.length > 0 ? (
            <div className="mt-3 space-y-3">
              {preview.candidates.slice(0, 4).map((candidate) => (
                <div
                  key={candidate.task_id}
                  className="rounded-xl border border-slate-800 bg-slate-950/70 p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium text-slate-100">
                      {candidate.title}
                    </div>
                    <StatusBadge
                      label={candidate.ready ? "可执行" : "未就绪"}
                      tone={candidate.ready ? "success" : "warning"}
                    />
                    {candidate.model_tier ? (
                      <StatusBadge
                        label={`模型 ${MODEL_TIER_LABELS[candidate.model_tier] ?? candidate.model_tier}`}
                        tone="info"
                      />
                    ) : null}
                  </div>

                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>
                      分数 {candidate.routing_score !== null ? candidate.routing_score.toFixed(1) : "-"}
                    </span>
                    <span>
                      责任角色 {candidate.owner_role_code ? ROLE_CODE_LABELS[candidate.owner_role_code] ?? candidate.owner_role_code : "未分配"}
                    </span>
                    <span>模型 {candidate.model_name ?? "未选择"}</span>
                    <span>重试 {candidate.execution_attempts}</span>
                    <span>近期失败 {candidate.recent_failure_count}</span>
                  </div>

                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {candidate.strategy_summary}
                  </p>

                  {candidate.selected_skill_names.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {candidate.selected_skill_names.map((skillName) => (
                        <span
                          key={`${candidate.task_id}-${skillName}`}
                          className="rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-300"
                        >
                          {skillName}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {candidate.blocking_signals.length > 0 ? (
                    <div className="mt-2 text-xs text-amber-200">
                      阻塞：{candidate.blocking_signals.map((signal) => signal.message).join("；")}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-400">
              当前项目还没有待路由的任务。
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 text-xs text-slate-500">
        预览会每 5 秒刷新一次，用于展示预算压力、阶段、角色和 Skill 绑定对路由结果的影响。
      </div>
    </section>
  );
}

function InfoCard(props: {
  label: string;
  value: string;
  extra?: string;
  testId?: string;
}) {
  return (
    <div
      data-testid={props.testId}
      className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
    >
      <div data-slot="label" className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div data-slot="value" className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
      {props.extra ? (
        <div className="mt-2 text-xs leading-5 text-slate-500">{props.extra}</div>
      ) : null}
    </div>
  );
}

function scrollToAgentThreadControlSurface() {
  navigateToProjectOverviewHash({
    view: "collaboration-control",
    targetId: "agent-thread-control-surface",
  });
}

function scrollToTeamControlCenterSurface() {
  navigateToProjectOverviewHash({
    view: "collaboration-control",
    targetId: "team-control-center-surface",
  });
}
