import type { RoleCatalogDisplayRole } from "../lib/roleCatalogRoles";
import { RoleCatalogCard } from "./RoleCatalogCard";

type RoleCatalogGridProps = {
  roles: RoleCatalogDisplayRole[];
  projectSelected: boolean;
  onEditRole: (roleCode: string | null) => void;
};

export function RoleCatalogGrid(props: RoleCatalogGridProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
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
  );
}
