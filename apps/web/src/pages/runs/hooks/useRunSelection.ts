import { useEffect, useMemo } from "react";
import type { NavigateFunction } from "react-router-dom";

import type { ConsoleRun, ConsoleTask } from "../../../features/console/types";
import { buildRunRoute } from "../../../lib/run-route";
import type { RunListItem } from "../types";

type UseRunSelectionInput = {
  tasks: ConsoleTask[];
  runId: string | undefined;
  routeTaskId: string | null;
  navigate: NavigateFunction;
};

export function useRunSelection(input: UseRunSelectionInput) {
  const latestRuns = useMemo<RunListItem[]>(
    () =>
      input.tasks
        .filter((task): task is ConsoleTask & { latest_run: ConsoleRun } =>
          Boolean(task.latest_run),
        )
        .map((task) => ({
          task,
          run: task.latest_run,
        }))
        .sort((left, right) =>
          right.run.created_at.localeCompare(left.run.created_at),
        ),
    [input.tasks],
  );

  const inferredTaskId = useMemo(
    () => latestRuns.find((item) => item.run.id === input.runId)?.task.id ?? null,
    [input.runId, latestRuns],
  );
  const effectiveTaskId = input.routeTaskId ?? inferredTaskId ?? null;
  const selectedTask = useMemo<ConsoleTask | null>(
    () => input.tasks.find((task) => task.id === effectiveTaskId) ?? null,
    [effectiveTaskId, input.tasks],
  );
  const selectedRunInLatestList = latestRuns.some(
    (item) => item.run.id === input.runId,
  );

  useEffect(() => {
    if (input.runId && !input.routeTaskId && inferredTaskId) {
      input.navigate(
        buildRunRoute({
          runId: input.runId,
          taskId: inferredTaskId,
          from: "runs",
        }),
        { replace: true },
      );
    }
  }, [inferredTaskId, input.navigate, input.routeTaskId, input.runId]);

  return {
    effectiveTaskId,
    latestRuns,
    selectedRunInLatestList,
    selectedTask,
  };
}
