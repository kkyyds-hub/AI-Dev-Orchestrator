type SkillRegistryAlertsProps = {
  registryError: string | null;
  formError: string | null;
};

export function SkillRegistryAlerts(props: SkillRegistryAlertsProps) {
  return (
    <>
      {props.registryError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          Skill 注册中心加载失败：{props.registryError}
        </div>
      ) : null}

      {props.formError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          {props.formError}
        </div>
      ) : null}
    </>
  );
}
