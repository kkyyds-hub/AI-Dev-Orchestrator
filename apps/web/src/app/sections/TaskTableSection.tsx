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
      className="rounded-[26px] border border-slate-800/90 bg-slate-950/65 p-4 shadow-xl shadow-black/20 ring-1 ring-white/[0.025]"
    >
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-50">Task list</h2>
          <p className="mt-1 text-sm text-slate-500">
            Primary workbench content: select tasks, open details, inspect runs, or follow Drill-down links.
          </p>
        </div>
        <StatusBadge
          label={props.overviewIsLoading ? "Loading" : props.overviewIsError ? "Load failed" : "Ready"}
          tone={props.overviewIsLoading ? "warning" : props.overviewIsError ? "danger" : "success"}
        />
      </div>

      {props.overviewIsError ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          Unable to load workbench data. Confirm the backend is running and GET /tasks/console is reachable.
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-800/80">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800/80 text-sm">
              <thead className="bg-slate-950/80 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Task</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Latest run</th>
                  <th className="px-4 py-3 font-medium">Cost</th>
                  <th className="px-4 py-3 font-medium">Log</th>
                  <th className="px-4 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70 bg-slate-950/35">
                {props.tasks.length ? (
                  props.tasks.map((task) => {
                    const isSelected = props.selectedTaskId === task.id;

                    return (
                      <tr
                        key={task.id}
                        data-testid={`home-task-row-${task.id}`}
                        className={`align-top transition ${
                          isSelected
                            ? "bg-slate-900/75 shadow-[inset_3px_0_0_rgba(34,211,238,0.55)]"
                            : "hover:bg-slate-900/45"
                        }`}
                      >
                        <td className="max-w-[360px] px-4 py-3">
                          <div className="space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => props.onSelectTask(task.id)}
                                className="min-w-0 text-left"
                              >
                                <div className="truncate font-medium text-slate-100">{task.title}</div>
                              </button>
                              <span
                                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                  isSelected
                                    ? "bg-cyan-500/15 text-cyan-200"
                                    : "bg-slate-800/80 text-slate-400"
                                }`}
                              >
                                {isSelected ? "Selected" : "Select"}
                              </span>
                            </div>
                            <div className="text-xs uppercase tracking-wide text-slate-600">
                              Priority {task.priority}
                            </div>
                            <button
                              type="button"
                              onClick={() => props.onSelectTask(task.id)}
                              className="line-clamp-2 max-w-md text-left text-xs leading-5 text-slate-500 transition hover:text-slate-300"
                            >
                              {task.input_summary}
                            </button>
                            {props.onNavigateToTask ? (
                              <button
                                type="button"
                                onClick={() => props.onNavigateToTask?.(task.id)}
                                className="rounded-lg border border-slate-700/80 bg-slate-900/60 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition hover:border-cyan-400/30 hover:text-cyan-100"
                              >
                                Open task center
                              </button>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge label={task.status} tone={mapTaskStatusTone(task.status)} />
                        </td>
                        <td className="min-w-[280px] px-4 py-3">
                          {task.latest_run ? (
                            <div className="space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <StatusBadge
                                  label={task.latest_run.status}
                                  tone={mapRunStatusTone(task.latest_run.status)}
                                />
                                <span className="text-xs text-slate-500">
                                  {formatDateTime(task.latest_run.created_at)}
                                </span>
                              </div>
                              <div className="text-xs leading-5 text-slate-500">
                                <div>
                                  Quality Gate: {" "}
                                  {task.latest_run.quality_gate_passed === true
                                    ? "passed"
                                    : task.latest_run.quality_gate_passed === false
                                      ? "blocked"
                                      : "unknown"}
                                </div>
                                {task.latest_run.failure_category ? (
                                  <div>Failure: {task.latest_run.failure_category}</div>
                                ) : null}
                                <div className="line-clamp-2 max-w-sm">
                                  {task.latest_run.result_summary ?? "No run summary"}
                                </div>
                              </div>
                              <TaskLatestRunRuntimeSummary taskId={task.id} run={task.latest_run} />
                              <div className="flex flex-wrap gap-2">
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
                                  className="rounded-lg border border-cyan-400/25 bg-cyan-500/10 px-2.5 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/15"
                                >
                                  Drill-down
                                </button>
                                {props.onNavigateToTask ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      props.onNavigateToTask?.(task.id, {
                                        runId: task.latest_run?.id ?? null,
                                      })
                                    }
                                    className="rounded-lg border border-slate-700/80 bg-slate-900/60 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-cyan-400/30 hover:text-cyan-100"
                                  >
                                    Task detail
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
                                    className="rounded-lg border border-slate-700/80 bg-slate-900/60 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-cyan-400/30 hover:text-cyan-100"
                                  >
                                    Run detail
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">No runs yet</span>
                          )}
                        </td>
                        <td
                          data-testid={`home-task-estimated-cost-${task.id}`}
                          className="px-4 py-3 text-slate-200"
                        >
                          {task.latest_run ? formatNullableCurrencyUsd(task.latest_run.estimated_cost) : "n/a"}
                        </td>
                        <td className="max-w-[220px] px-4 py-3">
                          {task.latest_run?.log_path ? (
                            <code className="line-clamp-2 break-all text-xs text-cyan-200/80">{task.latest_run.log_path}</code>
                          ) : (
                            <span className="text-xs text-slate-500">No logs</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                          {formatDateTime(task.updated_at)}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                      No tasks yet. Create tasks in the backend, then return here to inspect status, cost, logs, and context.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
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
    <details
      data-testid={`home-task-runtime-summary-${props.taskId}`}
      className="group rounded-xl border border-slate-800/80 bg-slate-950/60 px-3 py-2 text-xs text-slate-400"
    >
      <summary className="cursor-pointer list-none text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500 transition group-open:text-cyan-300">
        Runtime context
      </summary>
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
    </details>
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
      <span data-slot="label" className="text-slate-600">
        {props.label}:
      </span>{" "}
      <span data-slot="value" className="text-slate-300">
        {props.value}
      </span>
    </div>
  );
}
