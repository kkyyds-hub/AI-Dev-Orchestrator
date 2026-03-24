import { useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type {
  BossProjectItem,
  ChangePlanSummary,
  ProjectDetail,
  ProjectDetailTaskItem,
  RepositorySnapshot,
} from "../projects/types";
import { ChangePlanDrawer } from "../projects/ChangePlanDrawer";
import { useProjectChangePlans } from "../projects/hooks";
import { VerificationRunPanel } from "../run-log/VerificationRunPanel";
import { ChangeBatchBoard } from "./ChangeBatchBoard";
import { RepositoryVerificationPanel } from "./RepositoryVerificationPanel";
import { RepositoryHomeCard } from "./RepositoryHomeCard";
import { ChangeSessionPanel } from "./components/ChangeSessionPanel";
import { FileLocatorPanel } from "./components/FileLocatorPanel";
import {
  useCaptureProjectChangeSession,
  useProjectChangeSession,
  useRefreshProjectRepositorySnapshot,
} from "./hooks";
import { RepositoryTreePanel } from "./components/RepositoryTreePanel";
import type { CodeContextPack } from "./types";

type RepositoryOverviewPageProps = {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
};

export function RepositoryOverviewPage(props: RepositoryOverviewPageProps) {
  const projectId = props.detail?.id ?? props.project?.id ?? null;
  const [changePlanDrawerOpen, setChangePlanDrawerOpen] = useState(false);
  const [selectedChangePlanTaskId, setSelectedChangePlanTaskId] = useState<string | null>(
    null,
  );
  const [latestCodeContextPack, setLatestCodeContextPack] =
    useState<CodeContextPack | null>(null);
  const refreshMutation = useRefreshProjectRepositorySnapshot(projectId);
  const changeSessionQuery = useProjectChangeSession(projectId);
  const captureChangeSessionMutation = useCaptureProjectChangeSession(projectId);
  const changePlansQuery = useProjectChangePlans({ projectId });
  const workspace =
    props.detail?.repository_workspace ?? props.project?.repository_workspace ?? null;
  const tasks = props.detail?.tasks ?? [];
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
  const changePlans = changePlansQuery.data ?? [];
  const changePlanCountsByTask = useMemo(
    () =>
      changePlans.reduce<Record<string, number>>((mapping, item) => {
        mapping[item.task_id] = (mapping[item.task_id] ?? 0) + 1;
        return mapping;
      }, {}),
    [changePlans],
  );

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            仓库首页入口
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
            Day04 把 Day01 的仓库绑定、Day02 的目录快照和 Day03
            的变更会话整合到项目详情页；Day05 在此基础上新增最小文件定位与{" "}
            <code>CodeContextPack</code>，Day06 再把任务、交付件与候选文件集合整理成
            ChangePlan 草案；当前 Day07-Day10 已把多个草案合并成 ChangeBatch、补上执行前
            风险分类与人工确认、冻结 build / test / lint / typecheck 命令基线，并沉淀结构化
            <code>VerificationRun</code> 记录；但仍不进入 Day11+ 的差异视图、证据包或任何
            真实 Git 写操作。
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
            <RepositoryVerificationPanel
              projectId={projectId}
              repositoryRootPath={workspace.root_path}
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

          <div className="mt-4">
            <FileLocatorPanel
              projectId={projectId}
              workspaceRootPath={workspace.root_path}
              tasks={tasks}
              onCodeContextPackReady={setLatestCodeContextPack}
            />
          </div>

          <div className="mt-4">
            <ChangePlanMappingPanel
              tasks={tasks}
              changePlans={changePlans}
              changePlanCountsByTask={changePlanCountsByTask}
              isLoading={changePlansQuery.isLoading}
              errorMessage={
                changePlansQuery.isError ? changePlansQuery.error.message : null
              }
              latestCodeContextPack={latestCodeContextPack}
              onOpenTask={(taskId) => {
                setSelectedChangePlanTaskId(taskId);
                setChangePlanDrawerOpen(true);
              }}
            />
          </div>

          <div className="mt-4">
            <ChangeBatchBoard
              projectId={projectId}
              changePlans={changePlans}
              isLoadingChangePlans={changePlansQuery.isLoading}
              changePlanErrorMessage={
                changePlansQuery.isError ? changePlansQuery.error.message : null
              }
            />
          </div>

          <div className="mt-4">
            <VerificationRunPanel projectId={projectId} />
          </div>
        </>
      ) : null}

      <ChangePlanDrawer
        open={changePlanDrawerOpen}
        projectId={projectId}
        tasks={tasks}
        initialTaskId={selectedChangePlanTaskId}
        codeContextPack={latestCodeContextPack}
        changePlans={changePlans}
        onClose={() => setChangePlanDrawerOpen(false)}
      />
    </section>
  );
}

function ChangePlanMappingPanel(props: {
  tasks: ProjectDetailTaskItem[];
  changePlans: ChangePlanSummary[];
  changePlanCountsByTask: Record<string, number>;
  isLoading: boolean;
  errorMessage: string | null;
  latestCodeContextPack: CodeContextPack | null;
  onOpenTask: (taskId: string) => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Day06 变更计划草案
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            这里把项目任务、交付件与 Day05 的候选文件集合映射成结构化 ChangePlan，
            只记录“要改什么、为什么改、改完怎么验”；后续是否进入 ChangeBatch 与 Day08
            风险预检，仍在下方批次区单独处理。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`草案 ${props.changePlans.length}`}
            tone="info"
          />
          <StatusBadge
            label={
              props.latestCodeContextPack
                ? `CodeContextPack ${props.latestCodeContextPack.included_file_count} 文件`
                : "尚无 CodeContextPack"
            }
            tone={props.latestCodeContextPack ? "success" : "warning"}
          />
        </div>
      </div>

      {props.latestCodeContextPack ? (
        <div className="mt-4 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm leading-6 text-cyan-100">
          当前草案来源：{props.latestCodeContextPack.source_summary}
          <div className="mt-2 text-xs text-cyan-50/70">
            生成于 {formatDateTime(props.latestCodeContextPack.generated_at)}
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-400">
          先在上方 Day05 FileLocator 中生成 CodeContextPack，Day06 草案会直接消费该文件集合。
        </div>
      )}

      {props.isLoading ? (
        <div className="mt-4 text-sm leading-6 text-slate-400">
          正在加载变更计划映射...
        </div>
      ) : props.errorMessage ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          变更计划映射加载失败：{props.errorMessage}
        </div>
      ) : props.tasks.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.tasks.map((task) => {
            const plansForTask = props.changePlans.filter(
              (item) => item.task_id === task.id,
            );
            const latestPlan = plansForTask[0] ?? null;
            const canOpen =
              plansForTask.length > 0 || props.latestCodeContextPack !== null;

            return (
              <div
                key={task.id}
                className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium text-slate-100">
                        {task.title}
                      </div>
                      <StatusBadge
                        label={`草案 ${props.changePlanCountsByTask[task.id] ?? 0}`}
                        tone="info"
                      />
                      {latestPlan ? (
                        <StatusBadge
                          label={`最新 v${latestPlan.current_version_number}`}
                          tone="warning"
                        />
                      ) : null}
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-300">
                      {task.input_summary}
                    </div>
                    {latestPlan ? (
                      <div className="mt-2 text-xs leading-5 text-slate-500">
                        最新草案：{latestPlan.latest_version.intent_summary}
                      </div>
                    ) : null}
                  </div>

                  <button
                    type="button"
                    onClick={() => props.onOpenTask(task.id)}
                    disabled={!canOpen}
                    className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
                  >
                    {plansForTask.length > 0 ? "查看 / 追加草案" : "基于当前包创建草案"}
                  </button>
                </div>

                {latestPlan ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {latestPlan.latest_version.related_deliverables.map((deliverable) => (
                      <StatusBadge
                        key={`${task.id}-${deliverable.deliverable_id}`}
                        label={deliverable.title}
                        tone="neutral"
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-400">
          当前项目还没有任务，因此还不能生成 Day06 变更计划草案。
        </div>
      )}
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
