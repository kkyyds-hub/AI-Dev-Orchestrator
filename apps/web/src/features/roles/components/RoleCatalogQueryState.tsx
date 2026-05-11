type RoleCatalogQueryStateProps = {
  selectedProjectId: string | null;
  systemRoleErrorMessage?: string;
  projectRoleErrorMessage?: string;
};

export function RoleCatalogQueryState(props: RoleCatalogQueryStateProps) {
  return (
    <>
      {props.systemRoleErrorMessage ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          系统角色目录加载失败：{props.systemRoleErrorMessage}
        </div>
      ) : null}

      {props.selectedProjectId && props.projectRoleErrorMessage ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          项目角色配置加载失败：{props.projectRoleErrorMessage}
        </div>
      ) : null}

      {!props.selectedProjectId ? (
        <div className="border-y border-dashed border-[#333333] py-4 text-sm leading-6 text-zinc-500">
          还没有选中项目。当前先展示系统内置角色目录；在上方老板首页中选择项目后，就可以进入该项目的角色启用与身份配置编辑。
        </div>
      ) : null}
    </>
  );
}
