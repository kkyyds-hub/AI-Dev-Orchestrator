import { useMemo } from "react";

import type { ConsoleTask } from "../../../features/console/types";

type UseTaskSelectionInput = {
  tasks: ConsoleTask[];
  taskId: string | undefined;
  overviewIsLoading: boolean;
};

export function useTaskSelection(input: UseTaskSelectionInput) {
  const selectedTask = useMemo<ConsoleTask | null>(
    () => input.tasks.find((task) => task.id === input.taskId) ?? null,
    [input.taskId, input.tasks],
  );

  const taskNotFound =
    Boolean(input.taskId) &&
    !input.overviewIsLoading &&
    input.tasks.length > 0 &&
    !selectedTask;

  return {
    selectedTask,
    taskNotFound,
  };
}
