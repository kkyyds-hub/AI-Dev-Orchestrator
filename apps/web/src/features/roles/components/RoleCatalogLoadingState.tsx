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
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          正在加载项目角色目录...
        </div>
      ) : null}

      {props.isSystemRoleLoading && !props.hasSystemRoleData ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          正在加载系统内置角色目录...
        </div>
      ) : null}
    </>
  );
}
