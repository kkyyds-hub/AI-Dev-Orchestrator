import type { ConsoleRun, ConsoleTask } from "../../features/console/types";

export type RunListItem = {
  task: ConsoleTask;
  run: ConsoleRun;
};

export type BossDrilldownNavigateDetail = {
  source: "home_latest_run" | "home_manual_run";
  taskId: string;
  runId?: string | null;
};
