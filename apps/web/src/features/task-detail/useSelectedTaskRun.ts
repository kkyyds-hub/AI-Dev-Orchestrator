import { useEffect, useMemo, useState } from "react";

import type { TaskDetail } from "./types";

type UseSelectedTaskRunOptions = {
  taskId: string | null;
  detail: TaskDetail | undefined;
  requestedRunId: string | null;
};

export function useSelectedTaskRun({
  taskId,
  detail,
  requestedRunId,
}: UseSelectedTaskRunOptions) {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedRunId(null);
  }, [taskId]);

  useEffect(() => {
    if (!detail?.latest_run) {
      return;
    }

    const hasSelectedRun = detail.runs.some((run) => run.id === selectedRunId);
    if (!selectedRunId || !hasSelectedRun) {
      setSelectedRunId(detail.latest_run.id);
    }
  }, [detail, selectedRunId]);

  useEffect(() => {
    if (!requestedRunId || !detail?.runs.length) {
      return;
    }

    if (detail.runs.some((run) => run.id === requestedRunId)) {
      setSelectedRunId(requestedRunId);
    }
  }, [detail?.runs, requestedRunId]);

  const selectedRun = useMemo(
    () =>
      detail?.runs.find((run) => run.id === selectedRunId) ??
      detail?.latest_run ??
      null,
    [detail, selectedRunId],
  );

  return {
    selectedRunId,
    selectedRun,
    setSelectedRunId,
  };
}
