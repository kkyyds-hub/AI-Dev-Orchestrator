import type { RunUserSummary } from "../lib/runUserSummary";

type RunUserSummaryCardProps = {
  summary: RunUserSummary;
};

export function RunUserSummaryCard({ summary }: RunUserSummaryCardProps) {
  const {
    conclusion,
    executionModeLabel,
    completedItems,
    warnings,
    nextSteps,
    isRealExecution,
    isSimulatedVerification,
    qualityGatePassed,
  } = summary;

  return (
    <div
      data-testid="run-user-summary-card"
      className="space-y-4 rounded-lg border border-[#333333] bg-[#0f0f0f]/60 p-4"
    >
      {/* ── Header: execution mode badge + conclusion ────────── */}
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
              isRealExecution
                ? "bg-emerald-500/[0.12] text-emerald-300"
                : qualityGatePassed === false
                  ? "bg-rose-500/[0.12] text-rose-300"
                  : "bg-amber-500/[0.12] text-amber-300"
            }`}
          >
            {executionModeLabel}
          </span>
        </div>
        <p className="mt-3 text-sm leading-6 text-zinc-200">{conclusion}</p>
      </div>

      {/* ── Completed items ──────────────────────────────────── */}
      {completedItems.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">
            完成内容
          </h4>
          <ul className="mt-2 space-y-1">
            {completedItems.map((item, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm leading-6 text-zinc-400"
              >
                <span className="mt-[0.35em] block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-600" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ── Warnings ─────────────────────────────────────────── */}
      {warnings.length > 0 ? (
        <div className="rounded border-l-2 border-amber-500/50 bg-amber-500/[0.04] px-3 py-2.5">
          <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-400">
            需要注意
          </h4>
          <ul className="mt-2 space-y-1">
            {warnings.map((w, i) => (
              <li
                key={i}
                className="text-sm leading-6 text-amber-200/80"
              >
                {w}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ── Status indicators ────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">
        {isSimulatedVerification ? (
          <span className="inline-block rounded border border-amber-500/30 bg-amber-500/[0.06] px-2 py-0.5 text-xs text-amber-300">
            模拟验证
          </span>
        ) : null}
        {qualityGatePassed === true ? (
          <span className="inline-block rounded border border-emerald-500/30 bg-emerald-500/[0.06] px-2 py-0.5 text-xs text-emerald-300">
            质量检查通过
          </span>
        ) : qualityGatePassed === false ? (
          <span className="inline-block rounded border border-rose-500/30 bg-rose-500/[0.06] px-2 py-0.5 text-xs text-rose-300">
            质量检查拦截
          </span>
        ) : null}
      </div>

      {/* ── Next steps ───────────────────────────────────────── */}
      {nextSteps.length > 0 ? (
        <div className="border-t border-[#333333] pt-3">
          <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">
            建议下一步
          </h4>
          <ul className="mt-2 space-y-1">
            {nextSteps.map((step, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm leading-6 text-zinc-400"
              >
                <span className="mt-[0.35em] block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500" />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
