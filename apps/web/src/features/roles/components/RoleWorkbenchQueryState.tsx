type RoleWorkbenchQueryStateProps = {
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
};

export function RoleWorkbenchQueryState(props: RoleWorkbenchQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <section className="border-y border-dashed border-[#333333] py-7 text-sm text-zinc-500">
          正在加载角色工作台数据...
        </section>
      ) : null}

      {props.isError ? (
        <section className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          角色工作台加载失败：{props.errorMessage}
        </section>
      ) : null}
    </>
  );
}