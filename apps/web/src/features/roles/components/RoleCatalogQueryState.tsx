type RoleCatalogQueryStateProps = {
  selectedProjectId: string | null;
  systemRoleErrorMessage?: string;
  projectRoleErrorMessage?: string;
};

export function RoleCatalogQueryState(props: RoleCatalogQueryStateProps) {
  return (
    <>
      {props.systemRoleErrorMessage ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          系统角色目录加载失败：{props.systemRoleErrorMessage}
        </div>
      ) : null}

      {props.selectedProjectId && props.projectRoleErrorMessage ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          项目角色配置加载失败：{props.projectRoleErrorMessage}
        </div>
      ) : null}

      {!props.selectedProjectId ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          还没有选中项目。当前先展示系统内置角色目录；在上方老板首页中选择项目后，就可以进入该项目的角色启用与身份配置编辑。
        </div>
      ) : null}
    </>
  );
}
