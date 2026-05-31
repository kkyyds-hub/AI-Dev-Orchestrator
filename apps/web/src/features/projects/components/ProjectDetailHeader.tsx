import { StatusBadge } from "../../../components/StatusBadge";
import { ProjectAiSummaryCard } from "../../project-summary/ProjectAiSummaryCard";
import { formatDateTime } from "../../../lib/format";
import {
  mapProjectRiskTone,
  mapProjectStatusTone,
} from "../../../lib/status";
import type { BossProjectItem, ProjectDetail } from "../types";
import {
  PROJECT_RISK_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
} from "../types";

export function ProjectDetailHeader(props: {
  project: BossProjectItem | null;
  projectName: string;
  projectSummary: string;
  projectStage: BossProjectItem["stage"] | ProjectDetail["stage"];
  projectStatus: BossProjectItem["status"] | ProjectDetail["status"];
  projectCreatedAt: string | null;
  projectUpdatedAt: string | null;
  projectId: string | null;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-xl font-semibold text-zinc-100">
            {props.projectName}
          </h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge
              label={PROJECT_STAGE_LABELS[props.projectStage] ?? props.projectStage}
              tone="info"
            />
            <StatusBadge
              label={PROJECT_STATUS_LABELS[props.projectStatus] ?? props.projectStatus}
              tone={mapProjectStatusTone(props.projectStatus)}
            />
            {props.project ? (
              <StatusBadge
                label={
                  PROJECT_RISK_LABELS[props.project.risk_level] ??
                  props.project.risk_level
                }
                tone={mapProjectRiskTone(props.project.risk_level)}
              />
            ) : null}
          </div>
        </div>

        <div className="text-right text-xs text-zinc-500">
          {props.projectCreatedAt ? (
            <div>创建于 {formatDateTime(props.projectCreatedAt)}</div>
          ) : null}
          {props.projectUpdatedAt ? (
            <div className="mt-1">
              更新时间 {formatDateTime(props.projectUpdatedAt)}
            </div>
          ) : null}
        </div>
      </div>

      <p className="mt-4 text-sm leading-6 text-zinc-400">
        {props.projectSummary}
      </p>

      <ProjectAiSummaryCard projectId={props.projectId} />
    </div>
  );
}
