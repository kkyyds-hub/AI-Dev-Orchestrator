import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../../lib/format";
import {
  mapFailureCategoryTone,
  mapQualityGateTone,
  mapRunStatusTone,
} from "../../../lib/status";
import type { ConsoleRun } from "../../console/types";
import { DetailField } from "./TaskDetailField";

export function TaskDetailLatestRunCard(props: {
  latestRun: ConsoleRun | null;
  selectedRun: ConsoleRun | null;
  onSelectRun: (runId: string) => void;
}) {
  return (
    <RunCard
      title="最新运行"
      run={props.latestRun}
      isSelected={props.latestRun?.id === props.selectedRun?.id}
      onViewLog={(run) => props.onSelectRun(run.id)}
    />
  );
}

export function TaskDetailRunHistorySection(props: {
  taskId: string;
  runs: ConsoleRun[];
  selectedRun: ConsoleRun | null;
  onSelectRun: (runId: string) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-base font-semibold text-slate-50">运行历史</h3>
        <span className="text-xs text-slate-500">共 {props.runs.length} 条</span>
      </div>

      {props.runs.length ? (
        <div className="mt-4 max-h-[28rem] space-y-3 overflow-y-auto pr-1">
          {props.runs.map((run, index) => {
            const isSelected = run.id === props.selectedRun?.id;

            return (
              <div
                key={run.id}
                className={`rounded-xl border p-4 ${
                  isSelected
                    ? "border-cyan-500/40 bg-cyan-500/5"
                    : "border-slate-800 bg-slate-900/70"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-slate-100">
                      Run #{props.runs.length - index}
                    </div>
                    <div className="text-xs text-slate-500">
                      创建于 {formatDateTime(run.created_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
                    <button
                      type="button"
                      onClick={() => props.onSelectRun(run.id)}
                      className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-200"
                    >
                      {isSelected ? "日志中" : "查看日志"}
                    </button>
                    {props.onNavigateToRun ? (
                      <button
                        type="button"
                        onClick={() => props.onNavigateToRun?.(run.id, props.taskId)}
                        className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-200"
                      >
                        打开运行详情页
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <DetailField
                    label="Token"
                    value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
                  />
                  <DetailField label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
                  <DetailField label="开始时间" value={formatDateTime(run.started_at)} />
                  <DetailField label="结束时间" value={formatDateTime(run.finished_at)} />
                </div>

                <RunNarrative run={run} />
                <VerificationSection run={run} />
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
          这条任务还没有运行历史。你可以先在页面顶部手动触发一次 Worker。
        </div>
      )}
    </div>
  );
}

function RunCard(props: {
  title: string;
  run: ConsoleRun | null;
  isSelected: boolean;
  onViewLog: (run: ConsoleRun) => void;
}) {
  if (!props.run) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-base font-semibold text-slate-50">{props.title}</h3>
        <p className="mt-3 text-sm text-slate-400">这条任务还没有最新运行记录。</p>
      </div>
    );
  }

  const run = props.run;

  return (
    <div
      className={`rounded-xl border p-4 ${
        props.isSelected
          ? "border-cyan-500/40 bg-cyan-500/5"
          : "border-slate-800 bg-slate-950/60"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">{props.title}</h3>
          <p className="mt-1 text-xs text-slate-500">创建于 {formatDateTime(run.created_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
          <button
            type="button"
            onClick={() => props.onViewLog(run)}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-200"
          >
            {props.isSelected ? "日志中" : "查看日志"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField
          label="Token"
          value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
        />
        <DetailField label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
        <DetailField label="开始时间" value={formatDateTime(run.started_at)} />
        <DetailField label="结束时间" value={formatDateTime(run.finished_at)} />
      </div>

      <RunNarrative run={run} />
      <VerificationSection run={run} />
    </div>
  );
}

function RunNarrative(props: { run: ConsoleRun }) {
  return (
    <div className="mt-4 space-y-2 text-sm">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">路由原因</div>
        <p className="mt-1 leading-6 text-slate-300">
          {props.run.route_reason ?? "暂无路由说明"}
        </p>
        {props.run.routing_score !== null ? (
          <p className="mt-1 text-xs text-slate-500">
            路由分数：{props.run.routing_score}
          </p>
        ) : null}
        {props.run.routing_score_breakdown.length > 0 ? (
          <div className="mt-2 space-y-2">
            {props.run.routing_score_breakdown.map((item, index) => (
              <div
                key={`${props.run.id}-route-score-${item.code}-${index}`}
                className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="font-medium text-slate-100">
                    {item.label}
                    <span className="ml-2 text-slate-400">({item.code})</span>
                  </span>
                  <span
                    className={
                      item.score >= 0 ? "text-emerald-300" : "text-amber-300"
                    }
                  >
                    {item.score >= 0 ? "+" : ""}
                    {item.score.toFixed(1)}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-400">{item.detail}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">摘要</div>
        <p className="mt-1 leading-6 text-slate-300">
          {props.run.result_summary ?? "暂无运行摘要"}
        </p>
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">日志路径</div>
        {props.run.log_path ? (
          <code className="mt-1 block break-all text-xs text-cyan-200">
            {props.run.log_path}
          </code>
        ) : (
          <p className="mt-1 text-sm text-slate-500">暂无日志路径</p>
        )}
      </div>
    </div>
  );
}

function VerificationSection(props: { run: ConsoleRun }) {
  const run = props.run;

  return (
    <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-semibold text-slate-50">验证与质量闸门</h4>
          <p className="mt-1 text-xs text-slate-500">
            展示验证模板/命令、失败分类和是否允许最终进入 `completed`。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            label={formatQualityGateLabel(run.quality_gate_passed)}
            tone={mapQualityGateTone(run.quality_gate_passed)}
          />
          {run.failure_category ? (
            <StatusBadge
              label={run.failure_category}
              tone={mapFailureCategoryTone(run.failure_category)}
            />
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField label="验证模式" value={run.verification_mode ?? "未记录"} />
        <DetailField
          label="验证模板"
          value={run.verification_template ?? "未使用内置模板"}
        />
        <DetailField label="失败分类" value={run.failure_category ?? "无"} />
        <DetailField
          label="闸门结果"
          value={formatQualityGateLabel(run.quality_gate_passed)}
        />
      </div>

      <div className="mt-4 space-y-2 text-sm">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            验证入口
          </div>
          {run.verification_command ? (
            <code className="mt-1 block break-all text-xs text-cyan-200">
              {run.verification_command}
            </code>
          ) : (
            <p className="mt-1 text-sm text-slate-400">
              {run.verification_template
                ? `使用内置模板 ${run.verification_template}`
                : "未记录显式验证命令"}
            </p>
          )}
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            验证摘要
          </div>
          <p className="mt-1 leading-6 text-slate-300">
            {run.verification_summary ?? "暂无验证摘要"}
          </p>
        </div>
      </div>
    </div>
  );
}

function formatQualityGateLabel(qualityGatePassed: boolean | null): string {
  if (qualityGatePassed === true) {
    return "质量闸门放行";
  }

  if (qualityGatePassed === false) {
    return "质量闸门拦截";
  }

  return "闸门未知";
}
