export function buildDeliverablesRoute(input?: {
  projectId?: string | null;
  deliverableId?: string | null;
}) {
  const searchParams = new URLSearchParams();

  if (input?.projectId) {
    searchParams.set("projectId", input.projectId);
  }

  if (input?.deliverableId) {
    searchParams.set("deliverableId", input.deliverableId);
  }

  const search = searchParams.toString();
  return search ? `/deliverables?${search}` : "/deliverables";
}
