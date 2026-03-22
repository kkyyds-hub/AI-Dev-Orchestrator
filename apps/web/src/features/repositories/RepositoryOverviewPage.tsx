import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type {
  BossProjectItem,
  ProjectDetail,
  RepositorySnapshot,
} from "../projects/types";
import { RepositoryHomeCard } from "./RepositoryHomeCard";
import { ChangeSessionPanel } from "./components/ChangeSessionPanel";
import {
  useCaptureProjectChangeSession,
  useProjectChangeSession,
  useRefreshProjectRepositorySnapshot,
} from "./hooks";
import { RepositoryTreePanel } from "./components/RepositoryTreePanel";

type RepositoryOverviewPageProps = {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
};

export function RepositoryOverviewPage(props: RepositoryOverviewPageProps) {
  const projectId = props.detail?.id ?? props.project?.id ?? null;
  const refreshMutation = useRefreshProjectRepositorySnapshot(projectId);
  const changeSessionQuery = useProjectChangeSession(projectId);
  const captureChangeSessionMutation = useCaptureProjectChangeSession(projectId);
  const workspace =
    props.detail?.repository_workspace ?? props.project?.repository_workspace ?? null;
  const latestSnapshot =
    refreshMutation.data ??
    props.detail?.latest_repository_snapshot ??
    props.project?.latest_repository_snapshot ??
    null;
  const activeChangeSession =
    captureChangeSessionMutation.data ??
    changeSessionQuery.data ??
    props.detail?.current_change_session ??
    props.project?.current_change_session ??
    null;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            仓库首页入口
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
            Day04 把 Day01 的仓库绑定、Day02 的目录快照和 Day03
            的变更会话整合到项目详情页，作为 V4 第一层可见仓库能力；这里仍只展示入口摘要，不扩展到文件级编辑、代码上下文包、验证证据视图或真实 Git 写操作。
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            void refreshMutation.mutateAsync();
          }}
          disabled={!workspace || refreshMutation.isPending}
          className={`inline-flex items-center justify-center rounded-xl border px-4 py-2 text-sm font-medium transition ${
            !workspace || refreshMutation.isPending
              ? "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-500"
              : "border-cyan-500/30 bg-cyan-500/10 text-cyan-100 hover:border-cyan-400/50 hover:bg-cyan-500/20"
          }`}
        >
          {refreshMutation.isPending ? "正在刷新快照..." : "手动刷新快照"}
        </button>
      </div>

      {props.isLoading && !props.detail ? (
        <p className="mt-4 text-sm leading-6 text-slate-400">
          正在加载项目仓库信息...
        </p>
      ) : null}

      {props.errorMessage ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          项目详情加载失败：{props.errorMessage}
        </div>
      ) : null}

      {refreshMutation.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          快照刷新失败：{refreshMutation.error.message}
        </div>
      ) : null}

      {!props.isLoading || props.project || props.detail ? (
        <div className="mt-4">
          <RepositoryHomeCard
            workspace={workspace}
            snapshot={latestSnapshot}
            changeSession={activeChangeSession}
            title="仓库首页摘要"
            variant="full"
          />
        </div>
      ) : null}

      {workspace ? (
        <>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <RepositoryFieldCard label="显示名" value={workspace.display_name} />
            <RepositoryFieldCard label="仓库根目录" value={workspace.root_path} />
            <RepositoryFieldCard
              label="默认基线分支"
              value={workspace.default_base_branch}
            />
            <RepositoryFieldCard
              label="允许工作区根"
              value={workspace.allowed_workspace_root}
            />
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={buildSnapshotStatusLabel(latestSnapshot)}
                tone={mapSnapshotTone(latestSnapshot)}
              />
              <span className="text-xs text-slate-500">
                最近扫描：{formatDateTime(latestSnapshot?.scanned_at ?? null)}
              </span>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <RepositoryMetricCard
                label="目录数"
                value={String(latestSnapshot?.directory_count ?? 0)}
              />
              <RepositoryMetricCard
                label="文件数"
                value={String(latestSnapshot?.file_count ?? 0)}
              />
              <RepositoryMetricCard
                label="忽略目录"
                value={String(
                  latestSnapshot?.ignored_directory_names.length ??
                    workspace.ignore_rule_summary.length,
                )}
              />
              <RepositoryMetricCard
                label="扫描结果"
                value={
                  latestSnapshot
                    ? latestSnapshot.status === "success"
                      ? "成功"
                      : "失败"
                    : "未扫描"
                }
              />
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {(latestSnapshot?.ignored_directory_names ??
                workspace.ignore_rule_summary
              ).map((item) => (
                <StatusBadge key={item} label={item} tone="neutral" />
              ))}
            </div>

            {latestSnapshot?.status === "failed" && latestSnapshot.scan_error ? (
              <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
                扫描失败：{latestSnapshot.scan_error}
              </div>
            ) : null}

            {latestSnapshot && latestSnapshot.language_breakdown.length > 0 ? (
              <div className="mt-4">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  语言分布
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {latestSnapshot.language_breakdown.map((item) => (
                    <StatusBadge
                      key={item.language}
                      label={`${item.language} · ${item.file_count}`}
                      tone="info"
                    />
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-slate-400">
                {latestSnapshot?.status === "failed"
                  ? "最近一次刷新失败，因此当前不展示语言分布摘要。"
                  : "还没有生成语言分布摘要；可点击上方按钮手动刷新。"}
              </p>
            )}
          </div>

          <div className="mt-4">
            <ChangeSessionPanel
              workspace={workspace}
              latestSnapshot={latestSnapshot}
              changeSession={activeChangeSession}
              isLoading={changeSessionQuery.isLoading && activeChangeSession === null}
              isCapturing={captureChangeSessionMutation.isPending}
              errorMessage={
                changeSessionQuery.isError
                  ? changeSessionQuery.error.message
                  : captureChangeSessionMutation.isError
                    ? captureChangeSessionMutation.error.message
                    : null
              }
              onCapture={() => {
                void captureChangeSessionMutation.mutateAsync();
              }}
            />
          </div>

          <div className="mt-4">
            <div className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">
              目录快照
            </div>
            {latestSnapshot?.status === "success" ? (
              <RepositoryTreePanel nodes={latestSnapshot.tree} />
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-6 text-sm leading-6 text-slate-400">
                {latestSnapshot
                  ? "最近一次扫描失败，目录快照已保留失败状态但不展开旧树摘要。"
                  : "尚未生成目录快照；点击“手动刷新快照”后可查看最新结构化摘要。"}
              </div>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}

function RepositoryFieldCard(props: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm leading-6 text-slate-100">
        {props.value}
      </div>
    </div>
  );
}

function RepositoryMetricCard(props: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}

function mapSnapshotTone(
  snapshot: RepositorySnapshot | null,
): "neutral" | "success" | "danger" | "warning" {
  if (!snapshot) {
    return "warning";
  }

  return snapshot.status === "success" ? "success" : "danger";
}

function buildSnapshotStatusLabel(
  snapshot: RepositorySnapshot | null,
): string {
  if (!snapshot) {
    return "未扫描";
  }

  return snapshot.status === "success" ? "扫描成功" : "扫描失败";
}
