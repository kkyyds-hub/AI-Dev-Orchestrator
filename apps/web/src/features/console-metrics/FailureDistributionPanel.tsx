import { StatusBadge } from "../../components/StatusBadge";
import { useConsoleFailureDistribution, useConsoleRoutingDistribution } from "./hooks";

export function FailureDistributionPanel() {
  const failureQuery = useConsoleFailureDistribution();
  const routingQuery = useConsoleRoutingDistribution();

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">失败与路由分布</h2>
          <p className="mt-1 text-sm text-slate-400">
            展示失败状态、失败类型和主要路由原因，支撑 Day09 管理判断。
          </p>
        </div>
        <StatusBadge
          label={
            failureQuery.isLoading && routingQuery.isLoading
              ? "加载中"
              : failureQuery.isError || routingQuery.isError
                ? "加载失败"
                : "已接通"
          }
          tone={
            failureQuery.isLoading && routingQuery.isLoading
              ? "warning"
              : failureQuery.isError || routingQuery.isError
                ? "danger"
                : "success"
          }
        />
      </div>

      {failureQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载失败分布：{failureQuery.error.message}
        </div>
      ) : null}

      {routingQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载路由分布：{routingQuery.error.message}
        </div>
      ) : null}

      {failureQuery.data ? (
        <div className="mt-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric
              label="总运行数"
              value={String(failureQuery.data.total_runs)}
            />
            <Metric
              label="失败 / 取消"
              value={String(failureQuery.data.failed_or_cancelled_runs)}
            />
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">状态分布</div>
            <div className="mt-2 space-y-2">
              {failureQuery.data.status_distribution.map((item) => (
                <DistributionRow
                  key={item.status}
                  label={item.label}
                  value={item.count}
                />
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">失败类型</div>
            <div className="mt-2 space-y-2">
              {failureQuery.data.failure_category_distribution.length ? (
                failureQuery.data.failure_category_distribution.map((item) => (
                  <DistributionRow
                    key={item.category_code}
                    label={item.category_label}
                    value={item.count}
                  />
                ))
              ) : (
                <p className="text-sm text-slate-500">暂无失败类型数据</p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {routingQuery.data ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">路由原因分布</div>
          <div className="mt-2 text-xs text-slate-500">
            已统计路由运行：{routingQuery.data.total_routed_runs}
          </div>
          <div className="mt-2 space-y-2">
            {routingQuery.data.distribution.length ? (
              routingQuery.data.distribution.map((item) => (
                <DistributionRow
                  key={item.reason_code}
                  label={item.reason_label}
                  value={item.count}
                />
              ))
            ) : (
              <p className="text-sm text-slate-500">暂无路由分布数据</p>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function DistributionRow(props: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2">
      <span className="text-sm text-slate-300">{props.label}</span>
      <span className="text-sm font-medium text-slate-100">{props.value}</span>
    </div>
  );
}
