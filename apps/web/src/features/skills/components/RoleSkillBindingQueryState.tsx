type RoleSkillBindingQueryStateProps = {
  bindingError: string | null;
  isLoading: boolean;
  localError: string | null;
  registryError: string | null;
};

export function RoleSkillBindingQueryState(props: RoleSkillBindingQueryStateProps) {
  return (
    <>
      {props.isLoading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          正在加载项目角色 Skill 绑定...
        </div>
      ) : null}

      {props.bindingError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          项目 Skill 绑定加载失败：{props.bindingError}
        </div>
      ) : null}

      {props.registryError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          Skill 注册中心加载失败：{props.registryError}
        </div>
      ) : null}

      {props.localError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          {props.localError}
        </div>
      ) : null}
    </>
  );
}
