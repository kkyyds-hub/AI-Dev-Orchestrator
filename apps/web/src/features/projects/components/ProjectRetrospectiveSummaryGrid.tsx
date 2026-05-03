import type { ProjectRetrospectiveSummary } from "../../approvals/types";
import { ProjectRetrospectiveStat } from "./ProjectRetrospectiveShared";

export function ProjectRetrospectiveSummaryGrid(props: {
  summary: ProjectRetrospectiveSummary;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <ProjectRetrospectiveStat
        label="审批请求数"
        value={String(props.summary.total_approval_requests)}
      />
      <ProjectRetrospectiveStat
        label="审批返工回路"
        value={String(props.summary.negative_approval_cycles)}
      />
      <ProjectRetrospectiveStat
        label="待收口返工"
        value={String(props.summary.open_rework_cycles)}
      />
      <ProjectRetrospectiveStat
        label="失败复盘总数"
        value={String(props.summary.total_failure_reviews)}
      />
      <ProjectRetrospectiveStat
        label="失败聚类"
        value={String(props.summary.failure_clusters)}
      />
    </div>
  );
}
