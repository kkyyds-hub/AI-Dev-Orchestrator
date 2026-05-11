type CostDashboardQueryStateProps = {
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
};

export function CostDashboardQueryState(props: CostDashboardQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <div className="border-y border-dashed border-slate-800 px-1 py-5 text-sm text-slate-400">
          正在加载成本数据...
        </div>
      ) : null}

      {props.isError ? (
        <div className="border-y border-rose-900/60 px-1 py-5 text-sm text-rose-200">
          成本数据加载失败：{props.errorMessage}
        </div>
      ) : null}
    </>
  );
}
