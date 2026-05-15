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
import { CommitDraftPanel } from "./CommitDraftPanel";
import { DiffSummaryPage } from "./DiffSummaryPage";
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
    <section
      id="repository-workspace"
      data-testid="repository-workspace"
      className="scroll-mt-24 space-y-5 border-l border-[#333333] pl-4"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            仓库工作区
          </div>
          <h2 className="mt-2 text-xl font-semibold text-zinc-100">
            仓库工作区
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            集中查看主仓库、目录快照、变更会话和提交前准备。
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            void refreshMutation.mutateAsync();
          }}
          disabled={!workspace || refreshMutation.isPending}
          className={`inline-flex items-center justify-center rounded border px-4 py-2 text-sm font-medium transition ${
            !workspace || refreshMutation.isPending
              ? "cursor-not-allowed border-[#333333] bg-transparent text-zinc-600"
              : "border-[#4a4a4a] bg-transparent text-zinc-100 hover:border-zinc-500 hover:bg-[#292929]"
          }`}
        >
          {refreshMutation.isPending ? "正在刷新快照..." : "手动刷新快照"}
        </button>
      </div>

      <section className="border-y border-[#333333] py-5">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
          工作流摘要
        </div>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="border-l border-[#333333] px-4 py-2">
            <div className="text-sm font-medium text-zinc-100">绑定仓库</div>
            <p className="mt-1 text-sm leading-6 text-zinc-400">
              确认当前项目的主仓库目录。
            </p>
          </div>
          <div className="border-l border-[#333333] px-4 py-2">
            <div className="text-sm font-medium text-zinc-100">刷新快照</div>
            <p className="mt-1 text-sm leading-6 text-zinc-400">
              获取最新目录结构和语言分布。
            </p>
          </div>
          <div className="border-l border-[#333333] px-4 py-2">
            <div className="text-sm font-medium text-zinc-100">定位文件</div>
            <p className="mt-1 text-sm leading-6 text-zinc-400">
              按任务定位相关文件。
            </p>
          </div>
          <div className="border-l border-[#333333] px-4 py-2">
            <div className="text-sm font-medium text-zinc-100">准备提交</div>
            <p className="mt-1 text-sm leading-6 text-zinc-400">
              整理变更计划、验证结果和提交草案。
            </p>
          </div>
        </div>
      </section>

      {props.isLoading && !props.detail ? (
        <p className="text-sm leading-6 text-zinc-500">
          正在加载项目仓库信息...
        </p>
      ) : null}

      {props.errorMessage ? (
        <div className="border-l border-rose-500/50 px-4 py-3 text-sm text-rose-100">
          项目详情加载失败：{props.errorMessage}
        </div>
      ) : null}

      {refreshMutation.isError ? (
        <div className="border-l border-rose-500/50 px-4 py-3 text-sm text-rose-100">
          快照刷新失败：{refreshMutation.error.message}
        </div>
      ) : null}

      {!props.isLoading || props.project || props.detail ? (
        <div>
          <RepositoryHomeCard
            workspace={workspace}
            snapshot={latestSnapshot}
            changeSession={activeChangeSession}
            title="首页仓库状态"
            actionLabel={!workspace && projectId ? "去设置绑定主仓库" : undefined}
            onAction={
              !workspace && projectId
                ? () => {
                    window.location.href = `/settings?projectId=${projectId}#repository-binding`;
                  }
                : undefined
            }
            variant="full"
          />
        </div>
      ) : null}

      {workspace ? (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
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

          <div className="border-l border-[#333333] px-4 py-1">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={buildSnapshotStatusLabel(latestSnapshot)}
                tone={mapSnapshotTone(latestSnapshot)}
              />
              <span className="text-xs text-zinc-600">
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
              <div className="mt-4 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
                扫描失败：{latestSnapshot.scan_error}
              </div>
            ) : null}

            {latestSnapshot && latestSnapshot.language_breakdown.length > 0 ? (
              <div className="mt-4">
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
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
              <p className="mt-4 text-sm leading-6 text-zinc-500">
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
            <div className="mb-3 text-xs uppercase tracking-[0.2em] text-zinc-600">
              目录快照
            </div>
            {latestSnapshot?.status === "success" ? (
              <RepositoryTreePanel nodes={latestSnapshot.tree} />
            ) : (
              <div className="border-l border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-500">
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

          <div className="mt-4">
            <DiffSummaryPage projectId={projectId} />
          </div>

          <div className="mt-4">
            <CommitDraftPanel projectId={projectId} />
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
    <section className="space-y-4 border-y border-[#333333] py-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            变更计划
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-400">
            将当前任务与文件定位结果整理为可检查的变更计划，明确修改范围、修改原因和验证方式。后续是否进入变更批次与提交前检查，仍在下方批次区单独处理。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`计划 ${props.changePlans.length}`}
            tone="info"
          />
          <StatusBadge
            label={
              props.latestCodeContextPack
                ? `已定位 ${props.latestCodeContextPack.included_file_count} 文件`
                : "尚未生成文件定位结果"
            }
            tone={props.latestCodeContextPack ? "success" : "warning"}
          />
        </div>
      </div>

      {props.latestCodeContextPack ? (
        <div className="border-l border-[#333333] px-4 py-3 text-sm leading-6 text-zinc-400">
          定位来源：{props.latestCodeContextPack.source_summary}
          <div className="mt-2 text-xs text-zinc-600">
            生成时间 {formatDateTime(props.latestCodeContextPack.generated_at)}
          </div>
        </div>
      ) : (
        <div className="border-l border-dashed border-[#3a3a3a] px-4 py-3 text-sm leading-6 text-zinc-500">
          先在上方完成文件定位，再创建变更计划。
        </div>
      )}

      {props.isLoading ? (
        <div className="text-sm leading-6 text-zinc-500">
          正在加载变更计划...
        </div>
      ) : props.errorMessage ? (
        <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          变更计划加载失败：{props.errorMessage}
        </div>
      ) : props.tasks.length > 0 ? (
        <div className="divide-y divide-[#333333] border-y border-[#333333]">
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
                className="border-l border-[#333333] px-4 py-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium text-zinc-100">
                        {task.title}
                      </div>
                      <StatusBadge
                        label={`计划 ${props.changePlanCountsByTask[task.id] ?? 0}`}
                        tone="info"
                      />
                      {latestPlan ? (
                        <StatusBadge
                          label={`最新 v${latestPlan.current_version_number}`}
                          tone="warning"
                        />
                      ) : null}
                    </div>
                    <div className="mt-2 text-sm leading-6 text-zinc-400">
                      {task.input_summary}
                    </div>
                    {latestPlan ? (
                      <div className="mt-2 text-xs leading-5 text-zinc-500">
                        最新计划：{latestPlan.latest_version.intent_summary}
                      </div>
                    ) : null}
                  </div>

                  <button
                    type="button"
                    onClick={() => props.onOpenTask(task.id)}
                    disabled={!canOpen}
                    className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600"
                  >
                    {plansForTask.length > 0 ? "查看 / 追加计划" : "根据定位结果创建计划"}
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
        <div className="border-l border-dashed border-[#3a3a3a] px-4 py-3 text-sm leading-6 text-zinc-500">
          当前项目还没有任务，暂时不能创建变更计划。
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
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm leading-6 text-zinc-100">
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
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-zinc-100">
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
