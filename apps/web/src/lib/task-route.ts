type BuildTaskRouteInput = {
  taskId?: string | null;
  runId?: string | null;
  from?: "workbench" | "project" | "tasks";
  projectId?: string | null;
};

export function buildTaskRoute(input: BuildTaskRouteInput = {}) {
  const normalizedTaskId = input.taskId?.trim();
  const pathname = normalizedTaskId ? `/tasks/${normalizedTaskId}` : "/tasks";
  const searchParams = new URLSearchParams();

  if (input.runId) {
    searchParams.set("runId", input.runId);
  }

  if (input.from) {
    searchParams.set("from", input.from);
  }

  if (input.projectId) {
    searchParams.set("projectId", input.projectId);
  }

  const search = searchParams.toString();
  return search ? `${pathname}?${search}` : pathname;
}
