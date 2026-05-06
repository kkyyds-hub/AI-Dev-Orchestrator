type RoleWorkbenchQueryStateProps = {
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
};

export function RoleWorkbenchQueryState(props: RoleWorkbenchQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
          正在加载角色工作台数据...
        </section>
      ) : null}

      {props.isError ? (
        <section className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-100">
          角色工作台加载失败：{props.errorMessage}
        </section>
      ) : null}
    </>
  );
}
