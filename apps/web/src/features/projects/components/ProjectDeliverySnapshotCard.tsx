import { StatusBadge } from "../../../components/StatusBadge";

type ProjectDeliverySnapshotCardProps = {
  overview: {
    overall_status: "in_progress" | "blocked" | "ready_for_review";
    summary: string;
    completed_step_count: number;
    total_step_count: number;
    blocked_step_count: number;
    selected_change_batch_title: string | null;
    release_status: string | null;
    git_write_actions_triggered: boolean;
  } | null;
  isLoading: boolean;
  errorMessage: string | null;
};

export function ProjectDeliverySnapshotCard(
  props: ProjectDeliverySnapshotCardProps,
) {
  const { overview, isLoading, errorMessage } = props;

  return (
    <section className="border-b border-[#333333] border-l-2 border-l-[#5c7cfa] py-5 pl-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-[#8ea2ff]">
            交付闭环
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            汇总当前交付批次的完成度、阻断项和放行状态。
          </p>
        </div>
        {overview ? (
          <div className="flex flex-wrap gap-2">
            <StatusBadge
              label={renderDay15OverallStatusLabel(overview.overall_status)}
              tone={mapDay15OverviewTone(overview.overall_status)}
            />
            <StatusBadge
              label={`完成 ${overview.completed_step_count}/${overview.total_step_count}`}
              tone="info"
            />
            <StatusBadge
              label={`阻断 ${overview.blocked_step_count}`}
              tone={overview.blocked_step_count > 0 ? "danger" : "success"}
            />
            {overview.release_status ? (
              <StatusBadge
                label={`放行 ${overview.release_status}`}
                tone="neutral"
              />
            ) : null}
          </div>
        ) : null}
      </div>

      {isLoading && !overview ? (
        <p className="mt-3 text-sm leading-6 text-zinc-500">
          正在加载交付闭环...
        </p>
      ) : errorMessage ? (
        <p className="mt-3 text-sm leading-6 text-rose-200">
          交付闭环加载失败：{errorMessage}
        </p>
      ) : overview ? (
        <>
          <p className="mt-3 text-sm leading-6 text-zinc-200">{overview.summary}</p>
          <p className="mt-2 text-xs leading-5 text-zinc-500">
            当前批次：
            {overview.selected_change_batch_title ?? "未建立"}；代码写入：
            {overview.git_write_actions_triggered ? "是" : "否"}。
          </p>
        </>
      ) : null}
    </section>
  );
}

function mapDay15OverviewTone(
  status: NonNullable<ProjectDeliverySnapshotCardProps["overview"]>["overall_status"],
): "success" | "warning" | "danger" {
  if (status === "ready_for_review") {
    return "success";
  }
  if (status === "blocked") {
    return "danger";
  }
  return "warning";
}

function renderDay15OverallStatusLabel(
  status: NonNullable<ProjectDeliverySnapshotCardProps["overview"]>["overall_status"],
) {
  switch (status) {
    case "ready_for_review":
      return "闭环可审阅";
    case "blocked":
      return "闭环阻断";
    default:
      return "闭环进行中";
  }
}
