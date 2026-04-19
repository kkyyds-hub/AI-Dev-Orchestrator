type BuildRunRouteInput = {
  runId?: string | null;
  taskId?: string | null;
  from?: "workbench" | "tasks" | "runs";
};

export function buildRunRoute(input: BuildRunRouteInput = {}) {
  const normalizedRunId = input.runId?.trim();
  const pathname = normalizedRunId ? `/runs/${normalizedRunId}` : "/runs";
  const searchParams = new URLSearchParams();

  if (input.taskId) {
    searchParams.set("taskId", input.taskId);
  }

  if (input.from) {
    searchParams.set("from", input.from);
  }

  const search = searchParams.toString();
  return search ? `${pathname}?${search}` : pathname;
}
