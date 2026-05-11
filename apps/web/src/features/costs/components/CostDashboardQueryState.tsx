type CostDashboardQueryStateProps = {
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
};

export function CostDashboardQueryState(props: CostDashboardQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 px-4 py-5 text-sm text-slate-400">
          正在加载成本数据...
        </div>
      ) : null}

      {props.isError ? (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 px-4 py-5 text-sm text-rose-200">
          成本数据加载失败：{props.errorMessage}
        </div>
      ) : null}
    </>
  );
}
