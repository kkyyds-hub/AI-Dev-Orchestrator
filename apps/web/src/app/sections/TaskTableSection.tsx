import { StatusBadge } from "../../components/StatusBadge";
import type { ConsoleTask } from "../../features/console/types";
import {
  formatDateTime,
  formatNullableCurrencyUsd,
} from "../../lib/format";
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
          <h2 className="text-lg font-semibold text-slate-50">浠诲姟鍒楄〃</h2>
          <p className="text-sm text-slate-400">
            灞曠ず浠诲姟鐘舵€併€佹渶鏂拌繍琛岀姸鎬侊紝骞舵敮鎸佺洿鎺ユ墦寮€璇︽儏銆佹棩蹇椾笌浠诲姟鎿嶄綔渚ф澘銆?
          </p>
        </div>
        <StatusBadge
          label={props.overviewIsLoading ? "鍔犺浇涓?" : props.overviewIsError ? "鍔犺浇澶辫触" : "鏁版嵁宸插氨缁?"}
          tone={props.overviewIsLoading ? "warning" : props.overviewIsError ? "danger" : "success"}
        />
      </div>

      {props.overviewIsError ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          鏃犳硶鍔犺浇鎺у埗鍙伴椤垫暟鎹紝璇风‘璁ゅ悗绔凡鍚姩骞跺彲璁块棶 `GET /tasks/console`銆?
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="text-left text-slate-400">
              <tr>
                <th className="py-3 pr-4 font-medium">浠诲姟</th>
                <th className="py-3 pr-4 font-medium">Task Status</th>
                <th className="py-3 pr-4 font-medium">Latest Run</th>
                <th className="py-3 pr-4 font-medium">Estimated Cost</th>
                <th className="py-3 pr-4 font-medium">鏃ュ織</th>
                <th className="py-3 font-medium">鏇存柊鏃堕棿</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {props.tasks.length ? (
                props.tasks.map((task) => {
                  const isSelected = props.selectedTaskId === task.id;

                  return (
                    <tr
                      key={task.id}
                      className={`align-top transition ${
                        isSelected ? "bg-slate-950/60" : "hover:bg-slate-950/40"
                      }`}
                    >
                      <td className="py-4 pr-4">
                        <button type="button" onClick={() => props.onSelectTask(task.id)} className="w-full text-left">
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <div className="font-medium text-slate-100">{task.title}</div>
                              <span
                                className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                                  isSelected
                                    ? "bg-cyan-500/15 text-cyan-200"
                                    : "bg-slate-800 text-slate-400"
                                }`}
                              >
                                {isSelected ? "璇︽儏涓?" : "鏌ョ湅璇︽儏"}
                              </span>
                            </div>
                            <div className="text-xs uppercase tracking-wide text-slate-500">
                              浼樺厛绾э細{task.priority}
                            </div>
                            <div className="max-w-md text-xs leading-5 text-slate-400">{task.input_summary}</div>
                          </div>
                        </button>
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
                            <TaskLatestRunRuntimeSummary run={task.latest_run} />
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
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">灏氭湭杩愯</span>
                        )}
                      </td>
                      <td className="py-4 pr-4 text-slate-200">
                        {task.latest_run ? formatNullableCurrencyUsd(task.latest_run.estimated_cost) : "n/a"}
                      </td>
                      <td className="py-4 pr-4">
                        {task.latest_run?.log_path ? (
                          <code className="break-all text-xs text-cyan-200">{task.latest_run.log_path}</code>
                        ) : (
                          <span className="text-xs text-slate-500">鏆傛棤鏃ュ織</span>
                        )}
                      </td>
                      <td className="py-4 text-slate-400">{formatDateTime(task.updated_at)}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                    褰撳墠杩樻病鏈変换鍔°€傚厛鍦ㄥ悗绔垱寤轰换鍔★紝鍐嶅洖鍒版帶鍒跺彴鏌ョ湅鐘舵€併€佹垚鏈€佹棩蹇楀拰璇︽儏涓婁笅鏂囥€?
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
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
      <div className="text-[11px] uppercase tracking-[0.16em] text-cyan-300">Latest Run Runtime</div>
      <div className="mt-2 grid gap-x-3 gap-y-1 sm:grid-cols-2">
        {runtimeFields.map((field) => (
          <ContractLine key={field.key} label={field.label} value={field.value} />
        ))}
      </div>

      {hasRoleModelPolicyData ? (
        <div className="mt-3 border-t border-slate-800 pt-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-emerald-300">
            Role Model Policy Runtime
          </div>
          <div className="mt-2 grid gap-x-3 gap-y-1 sm:grid-cols-2">
            {roleModelPolicyFields.map((field) => (
              <ContractLine key={field.key} label={field.label} value={field.value} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ContractLine(props: { label: string; value: string }) {
  return (
    <div className="leading-5">
      <span className="text-slate-500">{props.label}: </span>
      <span className="text-slate-200">{props.value}</span>
    </div>
  );
}
