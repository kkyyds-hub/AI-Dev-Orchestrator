import { requestJson } from "../../lib/http";

import type { WorkerSlotOverview } from "./types";

export function fetchWorkerSlots(): Promise<WorkerSlotOverview> {
  return requestJson<WorkerSlotOverview>("/console/worker-slots");
}
