import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../../lib/format";
import {
  mapFailureCategoryTone,
  mapQualityGateTone,
  mapRunStatusTone,
} from "../../../lib/status";
import type { ConsoleRun } from "../../console/types";
import { DetailField, type TaskDetailSurfaceVariant } from "./TaskDetailField";

export function TaskDetailLatestRunCard(props: {
  latestRun: ConsoleRun | null;
  selectedRun: ConsoleRun | null;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onSelectRun: (runId: string) => void;
  onNavigateToLogs?: (runId: string) => void;
}) {
  return (
    <RunCard
      title="最新运行"
      run={props.latestRun}
      isSelected={props.latestRun?.id === props.selectedRun?.id}
      surfaceVariant={props.surfaceVariant}
      onViewLog={(run) => (props.onNavigateToLogs ?? props.onSelectRun)(run.id)}
    />
  );
}

export function TaskDetailRunHistorySection(props: {
  taskId: string;
  runs: ConsoleRun[];
  selectedRun: ConsoleRun | null;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onSelectRun: (runId: string) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToLogs?: (runId: string) => void;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <section
      className={
        isLine
          ? "border-b border-[#333333] pb-5"
          : "rounded-xl border border-[#333333] bg-transparent p-4"
      }
    >
      <div className="flex items-center justify-between gap-4">
        <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>运行历史</h3>
        <span className={`text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>共 {props.runs.length} 条</span>
      </div>

      {props.runs.length ? (
        <div className={isLine ? "mt-4 max-h-[28rem] divide-y divide-[#333333] overflow-y-auto border-y border-[#333333]" : "mt-4 max-h-[28rem] space-y-3 overflow-y-auto pr-1"}>
          {props.runs.map((run, index) => {
            const isSelected = run.id === props.selectedRun?.id;

            return (
              <div
                key={run.id}
                className={
                  isLine
                    ? `px-3 py-4 ${isSelected ? "bg-[#2b2b2b]" : "bg-transparent"}`
                    : `rounded-xl border p-4 ${
                        isSelected
                          ? "border-[#3a3a3a] bg-transparent"
                          : "border-[#333333] bg-transparent"
                      }`
                }
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className={`text-sm font-medium ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>
                      运行 #{props.runs.length - index}
                    </div>
                    <div className={`text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
                      创建于 {formatDateTime(run.created_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
                    <button
                      type="button"
                      onClick={() => (props.onNavigateToLogs ?? props.onSelectRun)(run.id)}
                      className={isLine ? "rounded-md border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-[#6a6a6a] hover:text-zinc-200"}
                    >
                      {isSelected ? "日志中" : "查看日志"}
                    </button>
                    {props.onNavigateToRun ? (
                      <button
                        type="button"
                        onClick={() => props.onNavigateToRun?.(run.id, props.taskId)}
                        className={isLine ? "rounded-md border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-[#6a6a6a] hover:text-zinc-200"}
                      >
                        打开运行详情页
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <DetailField
                    surfaceVariant={props.surfaceVariant}
                    label="令牌用量"
                    value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
                  />
                  <DetailField surfaceVariant={props.surfaceVariant} label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
                  <DetailField surfaceVariant={props.surfaceVariant} label="开始时间" value={formatDateTime(run.started_at)} />
                  <DetailField surfaceVariant={props.surfaceVariant} label="结束时间" value={formatDateTime(run.finished_at)} />
                </div>

                <RunNarrative run={run} surfaceVariant={props.surfaceVariant} />
                <VerificationSection run={run} surfaceVariant={props.surfaceVariant} />
              </div>
            );
          })}
        </div>
      ) : (
        <div className={isLine ? "mt-4 border-y border-dashed border-[#333333] py-6 text-sm text-zinc-500" : "mt-4 rounded-xl border border-dashed border-[#333333] bg-transparent p-4 text-sm text-zinc-400"}>
          这条任务还没有运行历史。你可以先在工作台手动执行一次任务。
        </div>
      )}
    </section>
  );
}

function RunCard(props: {
  title: string;
  run: ConsoleRun | null;
  isSelected: boolean;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onViewLog: (run: ConsoleRun) => void;
}) {
  const isLine = props.surfaceVariant === "line";

  if (!props.run) {
    return (
      <section className={isLine ? "border-b border-[#333333] pb-5" : "rounded-xl border border-[#333333] bg-transparent p-4"}>
        <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>{props.title}</h3>
        <p className={`mt-3 text-sm ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>这条任务还没有最新运行记录。</p>
      </section>
    );
  }

  const run = props.run;

  return (
    <section
      className={
        isLine
          ? "border-b border-[#333333] pb-5"
          : `rounded-xl border p-4 ${
              props.isSelected
                ? "border-[#3a3a3a] bg-transparent"
                : "border-[#333333] bg-transparent"
            }`
      }
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>{props.title}</h3>
          <p className={`mt-1 text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>创建于 {formatDateTime(run.created_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
          <button
            type="button"
            onClick={() => props.onViewLog(run)}
            className={isLine ? "rounded-md border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-[#333333] px-3 py-1.5 text-xs text-zinc-200 transition hover:border-[#6a6a6a] hover:text-zinc-200"}
          >
            {props.isSelected ? "日志中" : "查看日志"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="令牌用量"
          value={`${formatTokenCount(run.prompt_tokens)} / ${formatTokenCount(run.completion_tokens)}`}
        />
        <DetailField surfaceVariant={props.surfaceVariant} label="估算成本" value={formatCurrencyUsd(run.estimated_cost)} />
        <DetailField surfaceVariant={props.surfaceVariant} label="开始时间" value={formatDateTime(run.started_at)} />
        <DetailField surfaceVariant={props.surfaceVariant} label="结束时间" value={formatDateTime(run.finished_at)} />
      </div>

      <RunNarrative run={run} surfaceVariant={props.surfaceVariant} />
      <VerificationSection run={run} surfaceVariant={props.surfaceVariant} />
    </section>
  );
}

function RunNarrative(props: { run: ConsoleRun; surfaceVariant?: TaskDetailSurfaceVariant }) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div className="mt-4 space-y-2 text-sm">
      <div>
        <div className={`text-xs uppercase tracking-[0.18em] ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>分配原因</div>
        <p className={`mt-1 leading-6 ${isLine ? "text-zinc-300" : "text-zinc-400"}`}>
          {props.run.route_reason ?? "暂无路由说明"}
        </p>
        {props.run.routing_score !== null ? (
          <p className={`mt-1 text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
            分配评分：{props.run.routing_score}
          </p>
        ) : null}
        {props.run.routing_score_breakdown.length > 0 ? (
          <div className="mt-2 space-y-2">
            {props.run.routing_score_breakdown.map((item, index) => (
              <div
                key={`${props.run.id}-route-score-${item.code}-${index}`}
                className={isLine ? "border-l border-[#333333] px-3 py-2" : "rounded-lg border border-[#333333] bg-transparent px-3 py-2"}
              >
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className={`font-medium ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>
                    {item.label}
                    <span className={`ml-2 ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>({item.code})</span>
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
                <p className={`mt-1 text-xs leading-5 ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>{item.detail}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div>
        <div className={`text-xs uppercase tracking-[0.18em] ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>摘要</div>
        <p className={`mt-1 leading-6 ${isLine ? "text-zinc-300" : "text-zinc-400"}`}>
          {props.run.result_summary ?? "暂无运行摘要"}
        </p>
      </div>
      <div>
        <div className={`text-xs uppercase tracking-[0.18em] ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>日志路径</div>
        {props.run.log_path ? (
          <code className={`mt-1 block break-all text-xs ${isLine ? "text-zinc-300" : "text-zinc-200"}`}>
            {props.run.log_path}
          </code>
        ) : (
          <p className={`mt-1 text-sm ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>暂无日志路径</p>
        )}
      </div>
    </div>
  );
}

function VerificationSection(props: { run: ConsoleRun; surfaceVariant?: TaskDetailSurfaceVariant }) {
  const run = props.run;
  const isLine = props.surfaceVariant === "line";

  return (
    <div className={isLine ? "mt-4 border-t border-[#333333] pt-4" : "mt-4 rounded-xl border border-[#333333] bg-transparent p-4"}>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h4 className={`text-sm font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>验证与质量闸门</h4>
          <p className={`mt-1 text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
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
        <DetailField surfaceVariant={props.surfaceVariant} label="验证模式" value={run.verification_mode ?? "未记录"} />
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="验证模板"
          value={run.verification_template ?? "未使用内置模板"}
        />
        <DetailField surfaceVariant={props.surfaceVariant} label="失败分类" value={run.failure_category ?? "无"} />
        <DetailField
          surfaceVariant={props.surfaceVariant}
          label="闸门结果"
          value={formatQualityGateLabel(run.quality_gate_passed)}
        />
      </div>

      <div className="mt-4 space-y-2 text-sm">
        <div>
          <div className={`text-xs uppercase tracking-[0.18em] ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
            验证入口
          </div>
          {run.verification_command ? (
            <code className={`mt-1 block break-all text-xs ${isLine ? "text-zinc-300" : "text-zinc-200"}`}>
              {run.verification_command}
            </code>
          ) : (
            <p className={`mt-1 text-sm ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>
              {run.verification_template
                ? `使用内置模板 ${run.verification_template}`
                : "未记录显式验证命令"}
            </p>
          )}
        </div>
        <div>
          <div className={`text-xs uppercase tracking-[0.18em] ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
            验证摘要
          </div>
          <p className={`mt-1 leading-6 ${isLine ? "text-zinc-300" : "text-zinc-400"}`}>
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
