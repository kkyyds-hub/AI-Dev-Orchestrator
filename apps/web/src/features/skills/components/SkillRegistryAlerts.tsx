type SkillRegistryAlertsProps = {
  registryError: string | null;
  formError: string | null;
};

export function SkillRegistryAlerts(props: SkillRegistryAlertsProps) {
  return (
    <>
      {props.registryError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          Skill 注册中心加载失败：{props.registryError}
        </div>
      ) : null}

      {props.formError ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          {props.formError}
        </div>
      ) : null}
    </>
  );
}