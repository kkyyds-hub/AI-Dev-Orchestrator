import { StatusBadge } from "../../components/StatusBadge";
import { WorkerMemoryRecallCard } from "../../features/task-actions/WorkerMemoryRecallCard";
import { WorkerProviderPromptTokenCard } from "../../features/task-actions/WorkerProviderPromptTokenCard";
import { WorkerRoleModelPolicyCard } from "../../features/task-actions/WorkerRoleModelPolicyCard";
import type { WorkerRunOnceResponse } from "../../features/task-actions/types";
import { formatDateTime } from "../../lib/format";

type ManualRunResultSectionProps = {
  data: WorkerRunOnceResponse | undefined;
  isError: boolean;
  errorMessage: string | null;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function ManualRunResultSection(props: ManualRunResultSectionProps) {
  if (!props.data && !props.isError) {
    return null;
  }

  return (
    <section
      data-testid="home-manual-run-result-section"
      className={`rounded-2xl border p-4 ${
        props.isError
          ? "border-rose-500/30 bg-rose-500/10"
          : props.data?.claimed
            ? "border-emerald-500/30 bg-emerald-500/10"
            : "border-amber-500/30 bg-amber-500/10"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-50">鏈€杩戜竴娆℃墜鍔ㄦ墽琛?</h2>
          <p
            className={`mt-1 text-sm ${
              props.isError
                ? "text-rose-100"
                : props.data?.claimed
                  ? "text-emerald-100"
                  : "text-amber-100"
            }`}
          >
            {props.isError ? props.errorMessage : props.data?.message}
          </p>
        </div>
        {!props.isError && props.data ? (
          <StatusBadge
            label={props.data.claimed ? "宸插鐞嗕换鍔?" : "鏈鍙栦换鍔?"}
            tone={props.data.claimed ? "success" : "warning"}
          />
        ) : null}
      </div>

      {!props.isError && props.data?.task_title ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <MiniInfo label="浠诲姟" value={props.data.task_title} />
          <MiniInfo label="杩愯鐘舵€?" value={props.data.run_status ?? "鈥?"} />
          <MiniInfo
            label="璺敱鍒嗘暟"
            value={
              props.data.routing_score !== null && props.data.routing_score !== undefined
                ? String(props.data.routing_score)
                : "鈥?"
            }
          />
          <MiniInfo label="Run ID" value={props.data.run_id ?? "鈥?"} />
          <MiniInfo label="鍒涘缓鏃堕棿" value={formatDateTime(props.data.run_created_at)} />
          <MiniInfo label="缁撴潫鏃堕棿" value={formatDateTime(props.data.run_finished_at)} />
        </div>
      ) : null}

      {!props.isError && props.data?.task_id && props.data?.run_id ? (
        <div className="mt-3">
          <button
            type="button"
            data-testid="home-manual-run-drilldown"
            onClick={() =>
              props.onNavigateToProjectDrilldown({
                source: "home_manual_run",
                taskId: props.data?.task_id as string,
                runId: props.data?.run_id,
              })
            }
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20"
          >
            Drill-down to Project Detail and Strategy Preview
          </button>
        </div>
      ) : null}

      {!props.isError && props.data?.route_reason ? (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">璺敱鍘熷洜</div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{props.data.route_reason}</p>
        </div>
      ) : null}

      {!props.isError && (props.data?.model_name || props.data?.selected_skill_names.length) ? (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">绛栫暐寮曟搸缁撴灉</div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <MiniInfo
              label="妯″瀷"
              value={
                props.data?.model_name
                  ? `${props.data.model_name}${props.data.model_tier ? ` (${props.data.model_tier})` : ""}`
                  : "鈥?"
              }
            />
            <MiniInfo label="绛栫暐浠ｇ爜" value={props.data?.strategy_code ?? "鈥?"} />
          </div>
          {props.data?.strategy_summary ? (
            <p className="mt-3 text-sm leading-6 text-slate-300">{props.data.strategy_summary}</p>
          ) : null}
          {props.data?.selected_skill_names.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {props.data.selected_skill_names.map((skillName) => (
                <span
                  key={`${skillName}-${props.data?.run_id ?? "run"}`}
                  className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100"
                >
                  {skillName}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {!props.isError && props.data ? <WorkerRoleModelPolicyCard {...props.data} /> : null}
      {!props.isError && props.data ? <WorkerProviderPromptTokenCard {...props.data} /> : null}
      {!props.isError && props.data ? <WorkerMemoryRecallCard {...props.data} /> : null}
    </section>
  );
}

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
