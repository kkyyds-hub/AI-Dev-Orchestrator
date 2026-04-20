export function buildApprovalsRoute(input?: {
  projectId?: string | null;
  approvalId?: string | null;
}) {
  const searchParams = new URLSearchParams();

  if (input?.projectId) {
    searchParams.set("projectId", input.projectId);
  }

  if (input?.approvalId) {
    searchParams.set("approvalId", input.approvalId);
  }

  const search = searchParams.toString();
  return search ? `/approvals?${search}` : "/approvals";
}
