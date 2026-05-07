export type BossDrilldownNavigateDetail = {
  source: "home_latest_run" | "home_manual_run";
  taskId: string;
  runId?: string | null;
};

export function buildBossDrilldownHash(detail: BossDrilldownNavigateDetail) {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.taskId);

  if (detail.runId) {
    params.set("runId", detail.runId);
  }

  return `#boss-drilldown?${params.toString()}`;
}
