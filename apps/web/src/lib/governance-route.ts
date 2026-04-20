export type GovernanceRouteSection =
  | "memory"
  | "search"
  | "roles"
  | "skills"
  | "workbench";

export function buildGovernanceRoute(input?: {
  projectId?: string | null;
  section?: GovernanceRouteSection | null;
}) {
  const searchParams = new URLSearchParams();

  if (input?.projectId) {
    searchParams.set("projectId", input.projectId);
  }

  if (input?.section) {
    searchParams.set("section", input.section);
  }

  const search = searchParams.toString();
  return search ? `/governance?${search}` : "/governance";
}
