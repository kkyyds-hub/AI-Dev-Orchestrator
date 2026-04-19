import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { useProjectCostDashboardSnapshot } from "../hooks";

type CostDashboardSectionProps = {
  projectId: string | null;
  projectName: string | null;
};

export function CostDashboardSection(props: CostDashboardSectionProps) {
  const costQuery = useProjectCostDashboardSnapshot(props.projectId);

  if (!props.projectId) {
    return (
      <section
        id="day14-cost-dashboard"
        data-testid="day14-cost-dashboard"
        className="space-y-4 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
      >
        <h2 className="text-2xl font-semibold text-slate-50">Day14 Cost Dashboard</h2>
        <p className="text-sm text-slate-400">
          先选择项目，再查看 cache / cost 聚合与 fallback 口径。
        </p>
      </section>
    );
  }

  const snapshot = costQuery.data ?? null;
  return (
    <section
      id="day14-cost-dashboard"
      data-testid="day14-cost-dashboard"
      className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <header className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">
              Day14 Cache + Cost Dashboard
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">
              成本聚合与 fallback 观察面
            </h2>
            <p className="mt-2 text-sm text-slate-300">
              当前项目：{props.projectName ?? props.projectId}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void costQuery.refetch()}
            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            刷新聚合
          </button>
        </div>
      </header>

      {costQuery.isLoading && !snapshot ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
          正在加载 Day14 成本聚合...
        </div>
      ) : null}

      {costQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
          成本聚合加载失败：{costQuery.error.message}
        </div>
      ) : null}

      {snapshot ? (
        <>
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="run_count" value={String(snapshot.run_count)} />
            <MetricCard label="thread_count" value={String(snapshot.thread_count)} />
            <MetricCard
              label="total_estimated_cost_usd"
              value={formatUsd(snapshot.total_estimated_cost_usd)}
            />
            <MetricCard label="total_tokens" value={String(snapshot.total_tokens)} />
            <MetricCard
              label="generated_at"
              value={formatDateTime(snapshot.generated_at)}
            />
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={snapshot.fallback_contract.fallback_active ? "fallback active" : "provider-reported"}
                tone={snapshot.fallback_contract.fallback_active ? "warning" : "success"}
              />
              <StatusBadge label={`tasks ${snapshot.task_count}`} tone="info" />
              <StatusBadge
                label={`tasks_with_runs ${snapshot.task_count_with_runs}`}
                tone="neutral"
              />
            </div>
            <p className="mt-3 text-sm text-slate-300">
              {snapshot.fallback_contract.fallback_reason}
            </p>
            <div className="mt-2 text-xs text-slate-400">
              provider_reported={snapshot.fallback_contract.provider_reported_run_count} / heuristic=
              {snapshot.fallback_contract.heuristic_run_count} / missing=
              {snapshot.fallback_contract.missing_mode_run_count}
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h3 className="text-sm font-semibold text-slate-100">Token Accounting 模式聚合</h3>
              <div className="mt-3 space-y-2 text-sm">
                {snapshot.mode_breakdown.map((item) => (
                  <div
                    key={item.mode}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-slate-300"
                  >
                    <div className="font-medium text-slate-100">{item.mode}</div>
                    <div className="mt-1 text-xs text-slate-400">
                      runs={item.run_count} | cost={formatUsd(item.total_estimated_cost_usd)} |
                      tokens={item.total_tokens}
                    </div>
                  </div>
                ))}
                {snapshot.mode_breakdown.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-700 px-3 py-4 text-xs text-slate-500">
                    当前项目还没有可聚合的 run 数据。
                  </div>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h3 className="text-sm font-semibold text-slate-100">Cache（memory）聚合信号</h3>
              <p className="mt-2 text-xs text-slate-400">{snapshot.cache_summary.cache_signal_note}</p>
              <div className="mt-2 text-sm text-slate-300">
                total_memories={snapshot.cache_summary.total_memories}
              </div>
              <div className="mt-3 space-y-2 text-xs text-slate-300">
                {snapshot.cache_summary.memory_type_counts.map((item) => (
                  <div
                    key={item.memory_type}
                    className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    {item.memory_type}: {item.count}
                  </div>
                ))}
                {snapshot.cache_summary.memory_type_counts.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-700 px-3 py-4 text-slate-500">
                    暂无 memory 统计数据。
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="text-sm font-semibold text-slate-100">Role 维度成本聚合</h3>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-xs text-slate-300">
                <thead className="text-slate-400">
                  <tr>
                    <th className="px-2 py-1">role_code</th>
                    <th className="px-2 py-1">runs</th>
                    <th className="px-2 py-1">cost_usd</th>
                    <th className="px-2 py-1">tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.role_breakdown.map((item) => (
                    <tr key={item.role_code} className="border-t border-slate-800">
                      <td className="px-2 py-1">{item.role_code}</td>
                      <td className="px-2 py-1">{item.run_count}</td>
                      <td className="px-2 py-1">{formatUsd(item.total_estimated_cost_usd)}</td>
                      <td className="px-2 py-1">{item.total_tokens}</td>
                    </tr>
                  ))}
                  {snapshot.role_breakdown.length === 0 ? (
                    <tr className="border-t border-slate-800">
                      <td className="px-2 py-2 text-slate-500" colSpan={4}>
                        当前没有 role 维度可聚合数据。
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="text-sm font-semibold text-slate-100">Thread（agent session）维度聚合</h3>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-xs text-slate-300">
                <thead className="text-slate-400">
                  <tr>
                    <th className="px-2 py-1">session_id</th>
                    <th className="px-2 py-1">phase</th>
                    <th className="px-2 py-1">status</th>
                    <th className="px-2 py-1">role</th>
                    <th className="px-2 py-1">cost_usd</th>
                    <th className="px-2 py-1">tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.thread_breakdown.map((item) => (
                    <tr key={item.session_id} className="border-t border-slate-800">
                      <td className="px-2 py-1 font-mono">{item.session_id.slice(0, 8)}...</td>
                      <td className="px-2 py-1">{item.current_phase}</td>
                      <td className="px-2 py-1">
                        {item.status} / {item.review_status}
                      </td>
                      <td className="px-2 py-1">{item.owner_role_code}</td>
                      <td className="px-2 py-1">{formatUsd(item.total_estimated_cost_usd)}</td>
                      <td className="px-2 py-1">{item.total_tokens}</td>
                    </tr>
                  ))}
                  {snapshot.thread_breakdown.length === 0 ? (
                    <tr className="border-t border-slate-800">
                      <td className="px-2 py-2 text-slate-500" colSpan={6}>
                        当前没有 thread 维度可聚合数据。
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="text-sm font-semibold text-slate-100">Day15 Smoke Routes</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {snapshot.day15_smoke_routes.map((route) => (
                <code
                  key={route}
                  className="rounded-lg border border-slate-700 bg-slate-950/70 px-2 py-1 text-xs text-slate-300"
                >
                  {route}
                </code>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}

function MetricCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-lg font-semibold text-slate-50">{props.value}</div>
    </div>
  );
}

function formatUsd(value: number) {
  return `$${value.toFixed(6)}`;
}
