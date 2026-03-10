import type { TaskDetail } from "./types";
import { requestJson } from "../../lib/http";

export function fetchTaskDetail(taskId: string): Promise<TaskDetail> {
  return requestJson<TaskDetail>(`/tasks/${taskId}/detail`);
}
