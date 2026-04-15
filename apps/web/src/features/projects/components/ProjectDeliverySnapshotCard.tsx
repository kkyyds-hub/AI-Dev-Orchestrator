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
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">
            V4 Day15 仓库接入最小闭环演示
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            串联 Day01~Day14，终点保持在“可审阅 / 可解释 / 可拒绝”；不触发真实 Git
            写操作。
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
        <p className="mt-3 text-sm leading-6 text-slate-400">
          正在加载 Day15 闭环总览...
        </p>
      ) : errorMessage ? (
        <p className="mt-3 text-sm leading-6 text-rose-200">
          Day15 闭环总览加载失败：{errorMessage}
        </p>
      ) : overview ? (
        <>
          <p className="mt-3 text-sm leading-6 text-slate-200">{overview.summary}</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            当前批次：
            {overview.selected_change_batch_title ?? "未建立"}；真实 Git 写动作触发：
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
