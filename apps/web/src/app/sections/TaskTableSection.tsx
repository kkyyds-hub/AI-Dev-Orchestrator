import { StatusBadge } from "../../components/StatusBadge";
import type { ConsoleTask } from "../../features/console/types";
import { formatDateTime, formatNullableCurrencyUsd } from "../../lib/format";
import {
  buildLatestRunRuntimeFields,
  buildRoleModelPolicyRuntimeFields,
  hasRoleModelPolicyRuntimeData,
} from "../../lib/latestRunRuntimeContract";
import { mapRunStatusTone, mapTaskStatusTone } from "../../lib/status";

type TaskTableSectionProps = {
  tasks: ConsoleTask[];
  selectedTaskId: string | null;
  overviewIsLoading: boolean;
  overviewIsError: boolean;
  onSelectTask: (taskId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function TaskTableSection(props: TaskTableSectionProps) {
  return (
    <section
      data-testid="home-task-table-section"
      className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">任务列表</h2>
          <p className="text-sm text-slate-400">
            展示任务状态、最新运行状态，并支持直接打开详情、日志与任务操作侧栏。
          </p>
        </div>
        <StatusBadge
          label={props.overviewIsLoading ? "加载中" : props.overviewIsError ? "加载失败" : "数据已就绪"}
          tone={props.overviewIsLoading ? "warning" : props.overviewIsError ? "danger" : "success"}
        />
      </div>

      {props.overviewIsError ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载控制台首页数据，请确认后端已启动并可访问 `GET /tasks/console`。
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="text-left text-slate-400">
              <tr>
                <th className="py-3 pr-4 font-medium">任务</th>
                <th className="py-3 pr-4 font-medium">Task Status</th>
                <th className="py-3 pr-4 font-medium">Latest Run</th>
                <th className="py-3 pr-4 font-medium">Estimated Cost</th>
                <th className="py-3 pr-4 font-medium">日志</th>
                <th className="py-3 font-medium">更新时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {props.tasks.length ? (
                props.tasks.map((task) => {
                  const isSelected = props.selectedTaskId === task.id;

                  return (
                    <tr
                      key={task.id}
                      data-testid={`home-task-row-${task.id}`}
                      className={`align-top transition ${
                        isSelected ? "bg-slate-950/60" : "hover:bg-slate-950/40"
                      }`}
                    >
                      <td className="py-4 pr-4">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={() => props.onSelectTask(task.id)}
                              className="text-left"
                            >
                              <div className="font-medium text-slate-100">{task.title}</div>
                            </button>
                            <span
                              className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                                isSelected
                                  ? "bg-cyan-500/15 text-cyan-200"
                                  : "bg-slate-800 text-slate-400"
                              }`}
                            >
                              {isSelected ? "详情中" : "查看详情"}
                            </span>
                            {props.onNavigateToTask ? (
                              <button
                                type="button"
                                onClick={() => props.onNavigateToTask?.(task.id)}
                                className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[11px] font-medium text-cyan-100 transition hover:bg-cyan-500/20"
                              >
                                在任务中心打开
                              </button>
                            ) : null}
                          </div>
                          <div className="text-xs uppercase tracking-wide text-slate-500">
                            优先级：{task.priority}
                          </div>
                          <button
                            type="button"
                            onClick={() => props.onSelectTask(task.id)}
                            className="max-w-md text-left text-xs leading-5 text-slate-400"
                          >
                            {task.input_summary}
                          </button>
                        </div>
                      </td>
                      <td className="py-4 pr-4">
                        <StatusBadge label={task.status} tone={mapTaskStatusTone(task.status)} />
                      </td>
                      <td className="py-4 pr-4">
                        {task.latest_run ? (
                          <div className="space-y-2">
                            <StatusBadge
                              label={task.latest_run.status}
                              tone={mapRunStatusTone(task.latest_run.status)}
                            />
                            <TaskLatestRunRuntimeSummary taskId={task.id} run={task.latest_run} />
                            <div className="text-xs text-slate-400">
                              <div>
                                Quality Gate:{" "}
                                {task.latest_run.quality_gate_passed === true
                                  ? "passed"
                                  : task.latest_run.quality_gate_passed === false
                                    ? "blocked"
                                    : "unknown"}
                              </div>
                              {task.latest_run.failure_category ? (
                                <div>Failure Category: {task.latest_run.failure_category}</div>
                              ) : null}
                              <div>
                                Run: {task.latest_run.id} @ {formatDateTime(task.latest_run.created_at)}
                              </div>
                              <div className="max-w-xs">{task.latest_run.result_summary ?? "n/a"}</div>
                            </div>
                            <button
                              type="button"
                              data-testid={`home-task-latest-run-drilldown-${task.id}`}
                              onClick={() =>
                                props.onNavigateToProjectDrilldown({
                                  source: "home_latest_run",
                                  taskId: task.id,
                                  runId: task.latest_run?.id ?? null,
                                })
                              }
                              className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20"
                            >
                              Drill-down chain
                            </button>
                            {props.onNavigateToTask ? (
                              <button
                                type="button"
                                onClick={() =>
                                  props.onNavigateToTask?.(task.id, {
                                    runId: task.latest_run?.id ?? null,
                                  })
                                }
                                className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-cyan-400/30 hover:text-cyan-100"
                              >
                                打开任务详情页
                              </button>
                            ) : null}
                            {props.onNavigateToRun ? (
                              <button
                                type="button"
                                onClick={() =>
                                  task.latest_run?.id
                                    ? props.onNavigateToRun?.(task.latest_run.id, task.id)
                                    : undefined
                                }
                                className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-cyan-400/30 hover:text-cyan-100"
                              >
                                打开运行详情页
                              </button>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">尚未运行</span>
                        )}
                      </td>
                      <td
                        data-testid={`home-task-estimated-cost-${task.id}`}
                        className="py-4 pr-4 text-slate-200"
                      >
                        {task.latest_run ? formatNullableCurrencyUsd(task.latest_run.estimated_cost) : "n/a"}
                      </td>
                      <td className="py-4 pr-4">
                        {task.latest_run?.log_path ? (
                          <code className="break-all text-xs text-cyan-200">{task.latest_run.log_path}</code>
                        ) : (
                          <span className="text-xs text-slate-500">暂无日志</span>
                        )}
                      </td>
                      <td className="py-4 text-slate-400">{formatDateTime(task.updated_at)}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                    当前还没有任务。先在后端创建任务，再回到控制台查看状态、成本、日志和详情上下文。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function TaskLatestRunRuntimeSummary(props: {
  taskId: string;
  run: NonNullable<ConsoleTask["latest_run"]>;
}) {
  const runtimeContractInput = {
    providerKey: props.run.provider_key,
    promptTemplateKey: props.run.prompt_template_key,
    promptTemplateVersion: props.run.prompt_template_version,
    tokenAccountingMode: props.run.token_accounting_mode,
    tokenPricingSource: props.run.token_pricing_source,
    promptCharCount: props.run.prompt_char_count,
    promptTokens: props.run.prompt_tokens,
    completionTokens: props.run.completion_tokens,
    totalTokens: props.run.total_tokens,
    estimatedCost: props.run.estimated_cost,
    providerReceiptId: props.run.provider_receipt_id,
    roleModelPolicySource: props.run.role_model_policy_source,
    roleModelPolicyDesiredTier: props.run.role_model_policy_desired_tier,
    roleModelPolicyAdjustedTier: props.run.role_model_policy_adjusted_tier,
    roleModelPolicyFinalTier: props.run.role_model_policy_final_tier,
    roleModelPolicyStageOverrideApplied: props.run.role_model_policy_stage_override_applied,
  };
  const runtimeFields = buildLatestRunRuntimeFields(runtimeContractInput).filter(
    (field) => field.key !== "estimated_cost",
  );
  const roleModelPolicyFields = buildRoleModelPolicyRuntimeFields(runtimeContractInput);
  const hasRoleModelPolicyData = hasRoleModelPolicyRuntimeData(runtimeContractInput);

  return (
    <div
      data-testid={`home-task-runtime-summary-${props.taskId}`}
      className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300"
    >
      <div className="text-[11px] uppercase tracking-[0.16em] text-cyan-300">Latest Run Runtime</div>
      <div className="mt-2 grid gap-x-3 gap-y-1 sm:grid-cols-2">
        {runtimeFields.map((field) => (
          <ContractLine
            key={field.key}
            testId={`home-task-runtime-field-${props.taskId}-${field.key}`}
            label={toDay07RuntimeLabel(field.label)}
            value={field.value}
          />
        ))}
      </div>

      {hasRoleModelPolicyData ? (
        <div
          data-testid={`home-task-policy-card-${props.taskId}`}
          className="mt-3 border-t border-slate-800 pt-3"
        >
          <div className="text-[11px] uppercase tracking-[0.16em] text-emerald-300">
            Role Model Policy Runtime
          </div>
          <div className="mt-2">
            <ContractLine
              testId={`home-task-policy-field-${props.taskId}-contract-source`}
              label="role policy"
              value={runtimeContractInput.roleModelPolicySource ?? "-"}
            />
          </div>
          <div className="mt-2 grid gap-x-3 gap-y-1 sm:grid-cols-2">
            {roleModelPolicyFields.map((field) => (
              <ContractLine
                key={field.key}
                testId={`home-task-policy-field-${props.taskId}-${field.key}`}
                label={field.label}
                value={field.value}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function toDay07RuntimeLabel(label: string) {
  const normalized = label.trim().toLowerCase();
  if (normalized === "provider") {
    return "provider";
  }
  if (normalized.startsWith("prompt")) {
    return "prompt";
  }
  if (normalized.includes("accounting")) {
    return "accounting";
  }
  return label;
}

function ContractLine(props: { label: string; value: string; testId?: string }) {
  return (
    <div data-testid={props.testId} className="leading-5">
      <span data-slot="label" className="text-slate-500">
        {props.label}：
      </span>{" "}
      <span data-slot="value" className="text-slate-200">
        {props.value}
      </span>
    </div>
  );
}
