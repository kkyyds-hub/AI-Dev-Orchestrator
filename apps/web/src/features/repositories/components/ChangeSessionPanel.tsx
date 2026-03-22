import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { RepositorySnapshot, RepositoryWorkspace } from "../../projects/types";
import type {
  ChangeSession,
  ChangeSessionDirtyFile,
  ChangeSessionDirtyFileScope,
  ChangeSessionGuardStatus,
  ChangeSessionWorkspaceStatus,
} from "../types";

type ChangeSessionPanelProps = {
  workspace: RepositoryWorkspace;
  latestSnapshot: RepositorySnapshot | null;
  changeSession: ChangeSession | null;
  isLoading: boolean;
  isCapturing: boolean;
  errorMessage: string | null;
  onCapture: () => void;
};

export function ChangeSessionPanel(props: ChangeSessionPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            分支会话
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
            Day03 只记录当前分支 / HEAD / 基线引用与工作区脏状态快照，
            不执行 checkout、建分支、stash、reset、merge 或 commit。
          </p>
        </div>

        <button
          type="button"
          onClick={props.onCapture}
          disabled={props.isCapturing}
          className={`inline-flex items-center justify-center rounded-xl border px-4 py-2 text-sm font-medium transition ${
            props.isCapturing
              ? "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-500"
              : "border-cyan-500/30 bg-cyan-500/10 text-cyan-100 hover:border-cyan-400/50 hover:bg-cyan-500/20"
          }`}
        >
          {props.isCapturing ? "正在记录会话..." : "记录当前会话"}
        </button>
      </div>

      {props.errorMessage ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          变更会话读取失败：{props.errorMessage}
        </div>
      ) : null}

      {props.isLoading && !props.changeSession ? (
        <p className="mt-4 text-sm leading-6 text-slate-400">
          正在读取当前变更会话...
        </p>
      ) : null}

      {!props.changeSession && !props.isLoading ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-6 text-sm leading-6 text-slate-400">
          当前仓库已绑定为 <span className="text-slate-200">{props.workspace.display_name}</span>，
          但还没有生成 Day03 分支会话。点击上方按钮后，会冻结当前分支 /
          HEAD / 基线 / 工作区状态的只读快照。
        </div>
      ) : null}

      {props.changeSession ? (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <StatusBadge
              label={buildGuardLabel(props.changeSession.guard_status)}
              tone={mapGuardTone(props.changeSession.guard_status)}
            />
            <StatusBadge
              label={buildWorkspaceLabel(props.changeSession.workspace_status)}
              tone={mapWorkspaceTone(props.changeSession.workspace_status)}
            />
            <span className="text-xs text-slate-500">
              创建时间：{formatDateTime(props.changeSession.created_at)}
            </span>
            <span className="text-xs text-slate-500">
              最近更新：{formatDateTime(props.changeSession.updated_at)}
            </span>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
            <SessionMetricCard
              label="当前分支"
              value={props.changeSession.current_branch}
            />
            <SessionMetricCard
              label="HEAD"
              value={buildRefSummary(
                props.changeSession.head_ref,
                props.changeSession.head_commit_sha,
              )}
            />
            <SessionMetricCard
              label="默认基线"
              value={props.changeSession.baseline_branch}
            />
            <SessionMetricCard
              label="基线引用"
              value={buildRefSummary(
                props.changeSession.baseline_ref,
                props.changeSession.baseline_commit_sha,
              )}
            />
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              启动条件
            </div>
            <div className="mt-3 grid gap-3 xl:grid-cols-2">
              {buildLaunchChecks(props.changeSession, props.latestSnapshot).map(
                (item) => (
                  <LaunchCheckCard
                    key={item.label}
                    label={item.label}
                    detail={item.detail}
                    isReady={item.isReady}
                  />
                ),
              )}
            </div>
            <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm leading-6 text-slate-300">
              {props.changeSession.guard_summary}
            </div>
            {props.changeSession.blocking_reasons.length > 0 ? (
              <ul className="mt-4 space-y-2 text-sm leading-6 text-amber-100">
                {props.changeSession.blocking_reasons.map((item) => (
                  <li
                    key={item}
                    className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                脏文件摘要
              </div>
              <StatusBadge
                label={`${props.changeSession.dirty_file_count} 项`}
                tone={
                  props.changeSession.workspace_status === "dirty"
                    ? "warning"
                    : "success"
                }
              />
            </div>

            {props.changeSession.dirty_file_count === 0 ? (
              <p className="mt-3 text-sm leading-6 text-slate-400">
                当前工作区是干净的，Day03 会把它标记为可复用的只读会话基线。
              </p>
            ) : (
              <div className="mt-3 space-y-2">
                {props.changeSession.dirty_files.map((item) => (
                  <DirtyFileRow key={`${item.git_status}-${item.path}`} item={item} />
                ))}
                {props.changeSession.dirty_files_truncated ? (
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs leading-5 text-slate-400">
                    仅展示前 {props.changeSession.dirty_files.length} 项脏文件摘要，
                    其余风险仍已计入总数但不会在 Day03 提前展开更多文件级视图。
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}

function SessionMetricCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}

function LaunchCheckCard(props: {
  label: string;
  detail: string;
  isReady: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge
          label={props.isReady ? "就绪" : "待处理"}
          tone={props.isReady ? "success" : "warning"}
        />
        <div className="text-sm font-medium text-slate-100">{props.label}</div>
      </div>
      <div className="mt-2 text-sm leading-6 text-slate-400">{props.detail}</div>
    </div>
  );
}

function DirtyFileRow(props: { item: ChangeSessionDirtyFile }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge
          label={mapDirtyScopeLabel(props.item.change_scope)}
          tone={mapDirtyScopeTone(props.item.change_scope)}
        />
        <span className="font-mono text-xs text-slate-400">{props.item.git_status}</span>
      </div>
      <div className="mt-2 break-all text-sm leading-6 text-slate-200">
        {props.item.path}
      </div>
    </div>
  );
}

function buildRefSummary(ref: string, commitSha: string | null): string {
  if (!commitSha) {
    return `${ref} · 未解析`;
  }

  return `${ref} · ${commitSha.slice(0, 12)}`;
}

function buildLaunchChecks(
  changeSession: ChangeSession,
  latestSnapshot: RepositorySnapshot | null,
) {
  return [
    {
      label: "Day02 快照可用",
      detail: latestSnapshot
        ? latestSnapshot.status === "success"
          ? `最近快照创建于 ${formatDateTime(latestSnapshot.scanned_at)}。`
          : "最近一次目录快照刷新失败，需先确认仓库路径与扫描状态。"
        : "还没有生成目录快照，建议先完成 Day02 手动刷新。",
      isReady: latestSnapshot?.status === "success",
    },
    {
      label: "当前 HEAD 可解析",
      detail: changeSession.head_commit_sha
        ? `已记录 ${changeSession.head_ref} -> ${changeSession.head_commit_sha.slice(0, 12)}。`
        : "当前 HEAD 还没有稳定提交引用。",
      isReady: changeSession.head_commit_sha !== null,
    },
    {
      label: "默认基线已解析",
      detail: changeSession.baseline_commit_sha
        ? `已记录 ${changeSession.baseline_ref} -> ${changeSession.baseline_commit_sha.slice(0, 12)}。`
        : `默认基线 ${changeSession.baseline_branch} 目前无法解析为提交引用。`,
      isReady: changeSession.baseline_commit_sha !== null,
    },
    {
      label: "工作区干净",
      detail:
        changeSession.workspace_status === "clean"
          ? "当前工作区无未提交改动或未跟踪文件。"
          : `当前工作区存在 ${changeSession.dirty_file_count} 项风险，Day03 只记录不清理。`,
      isReady: changeSession.workspace_status === "clean",
    },
  ];
}

function buildGuardLabel(status: ChangeSessionGuardStatus) {
  return status === "ready" ? "可复用会话" : "风险阻断";
}

function mapGuardTone(
  status: ChangeSessionGuardStatus,
): "success" | "warning" {
  return status === "ready" ? "success" : "warning";
}

function buildWorkspaceLabel(status: ChangeSessionWorkspaceStatus) {
  return status === "clean" ? "工作区干净" : "工作区脏";
}

function mapWorkspaceTone(
  status: ChangeSessionWorkspaceStatus,
): "success" | "warning" {
  return status === "clean" ? "success" : "warning";
}

function mapDirtyScopeLabel(scope: ChangeSessionDirtyFileScope) {
  switch (scope) {
    case "untracked":
      return "未跟踪";
    case "staged":
      return "已暂存";
    case "mixed":
      return "已暂存 + 未暂存";
    case "unstaged":
    default:
      return "未暂存";
  }
}

function mapDirtyScopeTone(
  scope: ChangeSessionDirtyFileScope,
): "info" | "warning" | "danger" {
  switch (scope) {
    case "staged":
      return "info";
    case "mixed":
      return "warning";
    case "untracked":
      return "warning";
    case "unstaged":
    default:
      return "danger";
  }
}
