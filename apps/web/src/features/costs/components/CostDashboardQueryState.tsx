type CostDashboardQueryStateProps = {
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
};

export function CostDashboardQueryState(props: CostDashboardQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <div className="border-y border-dashed border-[#333333] py-5 text-sm text-zinc-500">
          正在加载成本数据...
        </div>
      ) : null}

      {props.isError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          成本数据加载失败：{props.errorMessage}
        </div>
      ) : null}
    </>
  );
}
