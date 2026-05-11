type RoleCatalogLoadingStateProps = {
  selectedProjectId: string | null;
  isProjectRoleLoading: boolean;
  hasProjectRoleData: boolean;
  isSystemRoleLoading: boolean;
  hasSystemRoleData: boolean;
};

export function RoleCatalogLoadingState(props: RoleCatalogLoadingStateProps) {
  return (
    <>
      {props.selectedProjectId &&
      props.isProjectRoleLoading &&
      !props.hasProjectRoleData ? (
        <div className="border-y border-[#333333] py-4 text-sm leading-6 text-zinc-500">
          正在加载项目角色目录...
        </div>
      ) : null}

      {props.isSystemRoleLoading && !props.hasSystemRoleData ? (
        <div className="border-y border-[#333333] py-4 text-sm leading-6 text-zinc-500">
          正在加载系统内置角色目录...
        </div>
      ) : null}
    </>
  );
}
