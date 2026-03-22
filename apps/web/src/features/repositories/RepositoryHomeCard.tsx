import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type {
  RepositorySnapshot,
  RepositoryWorkspace,
} from "../projects/types";
import type { ChangeSession } from "./types";

type RepositoryHomeCardProps = {
  workspace: RepositoryWorkspace | null;
  snapshot: RepositorySnapshot | null;
  changeSession: ChangeSession | null;
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  variant?: "compact" | "full";
  className?: string;
};

type CardTone = "neutral" | "info" | "success" | "warning" | "danger";

export function RepositoryHomeCard(props: RepositoryHomeCardProps) {
  const variant = props.variant ?? "compact";
  const isBound = props.workspace !== null;
  const bindingStatus = isBound
    ? { label: "已绑定主仓库", tone: "success" as const }
    : { label: "未绑定仓库", tone: "warning" as const };
  const snapshotStatus = buildSnapshotStatus(props.snapshot, isBound);
  const changeSessionStatus = buildChangeSessionStatus(props.changeSession, isBound);
  const shouldShowAction =
    typeof props.onAction === "function" && typeof props.actionLabel === "string";

  return (
    <section
      className={`rounded-2xl border border-slate-800 bg-slate-900/70 p-4 shadow-xl shadow-slate-950/20 ${
        props.className ?? ""
      }`}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            {props.title ?? "仓库入口"}
          </div>
          <div className="text-lg font-semibold text-slate-50">
            {props.workspace?.display_name ?? "等待绑定主仓库入口"}
          </div>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            {props.description ??
              buildDescription({
                workspace: props.workspace,
                snapshot: props.snapshot,
                changeSession: props.changeSession,
              })}
          </p>
        </div>

        {shouldShowAction ? (
          <button
            type="button"
            onClick={props.onAction}
            className="inline-flex items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-400/50 hover:bg-cyan-500/20"
          >
            {props.actionLabel}
          </button>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge label={bindingStatus.label} tone={bindingStatus.tone} />
        <StatusBadge label={snapshotStatus.label} tone={snapshotStatus.tone} />
        <StatusBadge label={changeSessionStatus.label} tone={changeSessionStatus.tone} />
      </div>

      {isBound ? (
        <div
          className={`mt-4 grid gap-3 ${
            variant === "full" ? "xl:grid-cols-4" : "sm:grid-cols-2"
          }`}
        >
          <SummaryItem
            label="仓库根目录"
            value={props.workspace?.root_path ?? "—"}
            breakAll
          />
          <SummaryItem
            label="最新快照"
            value={buildSnapshotSummary(props.snapshot)}
          />
          <SummaryItem
            label="当前变更会话"
            value={buildChangeSessionSummary(props.changeSession)}
          />
          <SummaryItem
            label="语言分布"
            value={buildLanguageSummary(props.snapshot)}
          />
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-5 text-sm leading-6 text-slate-300">
          下一步：先为项目绑定主仓库入口，再生成 Day02 目录快照并记录 Day03
          变更会话；Day04 只把这三类摘要整合到老板入口和项目详情，不扩展到文件级编辑或真实
          Git 写操作。
        </div>
      )}

      {variant === "full" && props.snapshot?.status === "failed" && props.snapshot.scan_error ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          最近一次仓库快照刷新失败：{props.snapshot.scan_error}
        </div>
      ) : null}
    </section>
  );
}

function SummaryItem(props: {
  label: string;
  value: string;
  breakAll?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div
        className={`mt-2 text-sm leading-6 text-slate-100 ${
          props.breakAll ? "break-all" : ""
        }`}
      >
        {props.value}
      </div>
    </div>
  );
}

function buildDescription(input: {
  workspace: RepositoryWorkspace | null;
  snapshot: RepositorySnapshot | null;
  changeSession: ChangeSession | null;
}) {
  if (!input.workspace) {
    return "当前项目尚未暴露仓库视角入口，因此老板页和项目详情页都只展示下一步绑定提示，而不会给出空白仓库区域。";
  }

  if (!input.snapshot) {
    return "主仓库已绑定，但还没有 Day02 目录快照；可以在项目详情中手动刷新，以补齐目录结构和语言分布摘要。";
  }

  if (!input.changeSession) {
    return "主仓库已绑定且已有最新目录快照，但还没有 Day03 变更会话摘要；可在项目详情中记录当前分支、基线和工作区状态。";
  }

  return `当前仓库以 ${input.changeSession.current_branch} 为活跃分支，基线 ${input.changeSession.baseline_branch}，老板入口仅展示仓库准备状态摘要。`;
}

function buildSnapshotStatus(
  snapshot: RepositorySnapshot | null,
  isBound: boolean,
): { label: string; tone: CardTone } {
  if (!isBound) {
    return { label: "待绑定后生成快照", tone: "neutral" };
  }
  if (!snapshot) {
    return { label: "待生成目录快照", tone: "info" };
  }
  if (snapshot.status === "failed") {
    return { label: "快照刷新失败", tone: "danger" };
  }

  return { label: "快照已就绪", tone: "success" };
}

function buildChangeSessionStatus(
  changeSession: ChangeSession | null,
  isBound: boolean,
): { label: string; tone: CardTone } {
  if (!isBound) {
    return { label: "待绑定后记录会话", tone: "neutral" };
  }
  if (!changeSession) {
    return { label: "待记录变更会话", tone: "info" };
  }
  if (changeSession.guard_status === "blocked") {
    return { label: "会话存在阻断", tone: "warning" };
  }
  if (changeSession.workspace_status === "dirty") {
    return { label: "工作区待清点", tone: "warning" };
  }

  return { label: "会话可复用", tone: "success" };
}

function buildSnapshotSummary(snapshot: RepositorySnapshot | null) {
  if (!snapshot) {
    return "尚未生成目录快照";
  }

  if (snapshot.status === "failed") {
    return `失败 · ${formatDateTime(snapshot.scanned_at)}`;
  }

  return `${formatDateTime(snapshot.scanned_at)} · ${snapshot.directory_count} 目录 / ${snapshot.file_count} 文件`;
}

function buildChangeSessionSummary(changeSession: ChangeSession | null) {
  if (!changeSession) {
    return "尚未记录当前分支 / HEAD / 基线摘要";
  }

  if (changeSession.workspace_status === "dirty") {
    return `${changeSession.current_branch} · ${changeSession.dirty_file_count} 项未提交改动`;
  }

  return `${changeSession.current_branch} · 基线 ${changeSession.baseline_branch}`;
}

function buildLanguageSummary(snapshot: RepositorySnapshot | null) {
  if (!snapshot) {
    return "待生成语言分布";
  }

  if (snapshot.status === "failed") {
    return "最近一次快照失败，暂不展示语言摘要";
  }

  if (snapshot.language_breakdown.length === 0) {
    return "当前快照未识别出语言分布";
  }

  return snapshot.language_breakdown
    .slice(0, 3)
    .map((item) => `${item.language} ${item.file_count}`)
    .join(" / ");
}
