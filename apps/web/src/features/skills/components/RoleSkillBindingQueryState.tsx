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
        <div className="border-y border-dashed border-[#333333] py-7 text-sm text-zinc-500">
          正在加载项目角色 Skill 绑定...
        </div>
      ) : null}

      {props.bindingError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          项目 Skill 绑定加载失败：{props.bindingError}
        </div>
      ) : null}

      {props.registryError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          Skill 注册中心加载失败：{props.registryError}
        </div>
      ) : null}

      {props.localError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          {props.localError}
        </div>
      ) : null}
    </>
  );
}