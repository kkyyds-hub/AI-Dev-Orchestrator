import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { applyConsoleEventToOverview, applyConsoleEventToRunLogs, applyConsoleEventToTaskDetail } from "./helpers";
import type { ConsoleEventState, ConsoleStreamEvent, StreamConnectionStatus } from "./types";
import type { ConsoleOverview } from "../console/types";
import type { TaskDetail } from "../task-detail/types";
import type { RunLogResponse } from "../run-log/types";

const SUPPORTED_EVENT_TYPES = [
  "connected",
  "heartbeat",
  "task_updated",
  "run_updated",
  "log_event",
] as const;

export function useConsoleEventStream(): ConsoleEventState {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StreamConnectionStatus>("connecting");
  const [lastEventType, setLastEventType] = useState<string | null>(null);
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      setStatus("unsupported");
      return;
    }

    setStatus("connecting");
    const eventSource = new EventSource("/events/console");

    const handleOpen = () => {
      setStatus("open");
    };

    const handleError = () => {
      setStatus("reconnecting");
    };

    const handleStreamEvent = (rawEvent: MessageEvent<string>) => {
      const streamEvent = parseStreamEvent(rawEvent.data);
      if (!streamEvent) {
        return;
      }

      setLastEventType(streamEvent.type);
      setLastEventAt(streamEvent.timestamp);

      if (streamEvent.type === "task_updated" || streamEvent.type === "run_updated") {
        queryClient.setQueryData<ConsoleOverview>(["console-overview"], (current) =>
          current ? applyConsoleEventToOverview(current, streamEvent) : current,
        );
      }

      if (streamEvent.type === "task_updated") {
        const taskId = streamEvent.payload.task.id;
        queryClient.setQueryData<TaskDetail>(["task-detail", taskId], (current) =>
          current ? applyConsoleEventToTaskDetail(current, streamEvent) : current,
        );
        return;
      }

      if (streamEvent.type === "run_updated") {
        const taskId = streamEvent.payload.task_id;

        queryClient.setQueryData<TaskDetail>(["task-detail", taskId], (current) =>
          current ? applyConsoleEventToTaskDetail(current, streamEvent) : current,
        );
        return;
      }

      if (streamEvent.type === "log_event" && streamEvent.payload.run_id) {
        queryClient.setQueriesData<RunLogResponse>(
          { queryKey: ["run-logs", streamEvent.payload.run_id] },
          (current) => (current ? applyConsoleEventToRunLogs(current, streamEvent) : current),
        );
      }
    };

    eventSource.addEventListener("open", handleOpen as EventListener);
    eventSource.addEventListener("error", handleError as EventListener);

    for (const eventType of SUPPORTED_EVENT_TYPES) {
      eventSource.addEventListener(eventType, handleStreamEvent as EventListener);
    }

    return () => {
      eventSource.removeEventListener("open", handleOpen as EventListener);
      eventSource.removeEventListener("error", handleError as EventListener);
      for (const eventType of SUPPORTED_EVENT_TYPES) {
        eventSource.removeEventListener(eventType, handleStreamEvent as EventListener);
      }
      eventSource.close();
    };
  }, [queryClient]);

  return useMemo(
    () => ({
      status,
      lastEventType,
      lastEventAt,
    }),
    [lastEventAt, lastEventType, status],
  );
}

function parseStreamEvent(rawData: string): ConsoleStreamEvent | null {
  try {
    return JSON.parse(rawData) as ConsoleStreamEvent;
  } catch {
    return null;
  }
}
