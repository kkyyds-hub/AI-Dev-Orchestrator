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
          ???????????{props.systemRoleErrorMessage}
        </div>
      ) : null}

      {props.selectedProjectId && props.projectRoleErrorMessage ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          ???????????{props.projectRoleErrorMessage}
        </div>
      ) : null}

      {!props.selectedProjectId ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          ?????????????????????????????????????????????????????????
        </div>
      ) : null}
    </>
  );
}
