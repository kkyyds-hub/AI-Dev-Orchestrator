import type { RoleCatalogDisplayRole } from "../lib/roleCatalogRoles";
import { RoleCatalogCard } from "./RoleCatalogCard";

type RoleCatalogGridProps = {
  roles: RoleCatalogDisplayRole[];
  projectSelected: boolean;
  onEditRole: (roleCode: string | null) => void;
};

export function RoleCatalogGrid(props: RoleCatalogGridProps) {
  return (
    <section aria-label="角色列表" className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-zinc-100">角色列表</h3>
        <p className="mt-1 text-xs leading-5 text-zinc-500">
          查看系统目录和项目角色配置；选择项目后可进入角色编辑。
        </p>
      </div>
      <div className="divide-y divide-[#333333] border-y border-[#333333]">
        {props.roles.map((role) => (
          <RoleCatalogCard
            key={role.key}
            projectRole={role.projectRole}
            systemRole={role.systemRole}
            projectSelected={props.projectSelected}
            onEdit={() =>
              props.onEditRole(role.projectRole?.role_code ?? role.systemRole?.code ?? null)
            }
          />
        ))}
      </div>
    </section>
  );
}
