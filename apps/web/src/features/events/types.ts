import type { ConsoleOverview, ConsoleRun, ConsoleTask } from "../console/types";
import type { TaskDetail } from "../task-detail/types";
import type { RunLogEvent, RunLogResponse } from "../run-log/types";

export type StreamConnectionStatus =
  | "connecting"
  | "open"
  | "reconnecting"
  | "unsupported";

export type StreamTaskPayload = Omit<ConsoleTask, "latest_run">;

export type StreamRunPayload = ConsoleRun & {
  task_id: string;
};

export type StreamLogPayload = {
  task_id: string | null;
  run_id: string | null;
  log_path: string;
  record: RunLogEvent;
};

export type ConsoleStreamEvent =
  | {
      id: string;
      type: "connected";
      timestamp: string;
      payload: { message: string; retry_ms?: number };
    }
  | {
      id: string;
      type: "heartbeat";
      timestamp: string;
      payload: { message: string };
    }
  | {
      id: string;
      type: "task_updated";
      timestamp: string;
      payload: {
        reason: string;
        previous_status?: string;
        task: StreamTaskPayload;
      };
    }
  | {
      id: string;
      type: "run_updated";
      timestamp: string;
      payload: {
        reason: string;
        task_id: string;
        run: StreamRunPayload;
      };
    }
  | {
      id: string;
      type: "log_event";
      timestamp: string;
      payload: StreamLogPayload;
    };

export type ConsoleEventState = {
  status: StreamConnectionStatus;
  lastEventType: string | null;
  lastEventAt: string | null;
};

export type OverviewUpdater = (overview: ConsoleOverview) => ConsoleOverview;
export type TaskDetailUpdater = (detail: TaskDetail) => TaskDetail;
export type RunLogUpdater = (logs: RunLogResponse) => RunLogResponse;
