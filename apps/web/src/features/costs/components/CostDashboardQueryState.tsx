type CostDashboardQueryStateProps = {
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
};

export function CostDashboardQueryState(props: CostDashboardQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
          正在加载 Day14 成本聚合...
        </div>
      ) : null}

      {props.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
          成本聚合加载失败：{props.errorMessage}
        </div>
      ) : null}
    </>
  );
}
