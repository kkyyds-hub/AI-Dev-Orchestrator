type RoleCatalogMetricGridProps = {
  systemRoleCount: number;
  enabledRoleCount: number;
  disabledRoleCount: number;
  selectedProjectName: string | null;
};

export function RoleCatalogMetricGrid(props: RoleCatalogMetricGridProps) {
  const metrics = [
    {
      label: "系统角色数",
      value: String(props.systemRoleCount),
      hint: "系统内置的最小角色目录",
    },
    {
      label: "项目已启用",
      value: String(props.enabledRoleCount),
      hint: props.selectedProjectName ? "当前项目启用的角色数" : "选择项目后可查看",
    },
    {
      label: "项目未启用",
      value: String(props.disabledRoleCount),
      hint: "可在角色编辑抽屉中启用或停用",
    },
    {
      label: "目录模式",
      value: props.selectedProjectName ? "项目配置" : "系统只读",
      hint: "当前页仅维护角色目录与职责边界",
    },
  ];

  return (
    <section className="border-b border-[#333333] pb-5" aria-label="角色目录指标摘要">
      <dl className="grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="min-w-0">
            <dt className="text-xs font-medium tracking-[0.12em] text-zinc-500">
              {metric.label}
            </dt>
            <dd className="mt-2 truncate font-mono text-2xl font-semibold tracking-tight text-zinc-100">
              {metric.value}
            </dd>
            <dd className="mt-1.5 truncate text-xs text-zinc-600">
              {metric.hint}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
