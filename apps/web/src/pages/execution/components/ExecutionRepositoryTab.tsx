import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { RepositoryPreflightPanel } from "../../../features/approvals/RepositoryPreflightPanel";
import { RepositoryReleaseGatePanel } from "../../../features/approvals/RepositoryReleaseGatePanel";
import {
  useProjectChangeBatches,
  useProjectChangeSession,
  useProjectCommitCandidates,
  useProjectRepositorySnapshot,
} from "../../../features/repositories/hooks";
import { useProjectScope } from "../../shared/useProjectScope";

const CHANGE_CHAIN_STEPS = [
  { key: "change_request",  label: "变更需求" },
  { key: "ai_assess",       label: "AI 主管评估" },
  { key: "file_locate",     label: "文件定位" },
  { key: "context_pack",    label: "上下文包" },
  { key: "change_plan",     label: "变更方案" },
  { key: "change_batch",    label: "变更批次" },
  { key: "preflight",       label: "预检" },
  { key: "commit_draft",    label: "提交草案" },
  { key: "release_judge",   label: "放行判断" },
] as const;

export function ExecutionRepositoryTab() {
  const navigate = useNavigate();
  const { selectedProjectId, selectedProjectName } = useProjectScope();

  const hasProject = selectedProjectId !== "all";

  // Repository data hooks
  const snapshotQuery = useProjectRepositorySnapshot(hasProject ? selectedProjectId : null);
  const sessionQuery = useProjectChangeSession(hasProject ? selectedProjectId : null);
  const batchesQuery = useProjectChangeBatches(hasProject ? selectedProjectId : null);
  const candidatesQuery = useProjectCommitCandidates(hasProject ? selectedProjectId : null);

  const snapshot = snapshotQuery.data;
  const session = sessionQuery.data;
  const batches = batchesQuery.data ?? [];
  const candidates = candidatesQuery.data ?? [];
  const candidateSignature = useMemo(
    () => candidates.map((candidate) => candidate.id).sort().join("|"),
    [candidates],
  );
  const [commitDraftAcknowledged, setCommitDraftAcknowledged] = useState(false);

  useEffect(() => {
    setCommitDraftAcknowledged(false);
  }, [selectedProjectId, candidateSignature]);

  // Determine current step for the indicator
  const activeStepIndex = useMemo(() => {
    if (!hasProject) return -1;
    if (!snapshot) return 0; // change_request
    if (!session) return 1;  // ai_assess
    // session exists → at least at change_session step (step 1)
    if (batches.length > 0) {
      const hasPreflight = batches.some((b) => b.preflight.status !== "not_started");
      if (hasPreflight) {
        if (candidates.length > 0) {
          return commitDraftAcknowledged ? 8 : 7; // commit_draft -> release_judge
        }
        return 6; // preflight
      }
      return 5; // change_batch
    }
    // Has session but no batches → between file_locate and context_pack
    return 2; // file_locate (early stage)
  }, [hasProject, snapshot, session, batches, candidates, commitDraftAcknowledged]);

  const handleOpenFullRepo = () => {
    if (hasProject) {
      navigate(`/projects/${selectedProjectId}/repository`);
    }
  };

  const activeStep = CHANGE_CHAIN_STEPS[Math.max(activeStepIndex, 0)].key;

  if (!hasProject) {
    return (
      <div className="space-y-3">
        <button
          type="button"
          disabled
          className="rounded border border-[#333333] px-4 py-2 text-sm text-zinc-600 cursor-not-allowed"
        >
          打开仓库工作区
        </button>
        <p className="text-xs text-zinc-600">需先选择具体项目</p>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="execution-repository-tab">
      {/* ── 顶部仓库状态条 ── */}
      <div className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
          仓库状态
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatusItem
            label="仓库快照"
            value={snapshotQuery.isLoading ? "加载中..." : snapshot ? "已绑定" : "未生成"}
            tone={snapshot ? "ok" : "muted"}
          />
          <StatusItem
            label="变更会话"
            value={sessionQuery.isLoading ? "加载中..." : session ? session.workspace_status === "clean" ? "干净" : "有变更" : "未创建"}
            tone={session ? (session.workspace_status === "clean" ? "ok" : "warn") : "muted"}
          />
          <StatusItem
            label="变更批次"
            value={`${batches.length} 个`}
            tone={batches.length > 0 ? "ok" : "muted"}
          />
          <StatusItem
            label="提交草案"
            value={`${candidates.length} 个`}
            tone={candidates.length > 0 ? "ok" : "muted"}
          />
        </div>
        {session && (
          <div className="mt-2 text-[11px] text-zinc-600 truncate">
            分支 {session.current_branch} · {session.dirty_file_count} 个变更文件
          </div>
        )}
      </div>

      {/* ── 变更链路步骤条 ── */}
      <div className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
          变更链路
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {CHANGE_CHAIN_STEPS.map((step, idx) => {
            const isActive = idx === activeStepIndex;
            const isPast = idx < activeStepIndex;
            return (
              <span
                key={step.key}
                className={`text-[11px] rounded border px-2 py-1 ${
                  isActive
                    ? "border-zinc-400 text-zinc-200 bg-[#222222]"
                    : isPast
                    ? "border-[#333333] text-zinc-500"
                    : "border-[#333333] text-zinc-700"
                }`}
              >
                {step.label}
              </span>
            );
          })}
        </div>
      </div>

      {/* ── 当前步骤面板 ── */}
      <CurrentStepPanel
        activeStep={activeStep}
        snapshot={snapshot}
        session={session}
        batchCount={batches.length}
        candidateCount={candidates.length}
        hasPreflight={batches.some((b) => b.preflight.status !== "not_started")}
      />

      {activeStep === "preflight" ? (
        <section data-testid="execution-repository-preflight-panel">
          <RepositoryPreflightPanel
            projectId={selectedProjectId}
            projectName={selectedProjectName}
          />
        </section>
      ) : null}

      {activeStep === "commit_draft" ? (
        <section
          className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4"
          data-testid="execution-repository-commit-draft-panel"
        >
          <div className="text-sm font-semibold text-zinc-100">提交草案确认</div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            已检测到 {candidates.length} 个提交草案。提交草案仅记录候选版本与证据，
            不是本地提交，不会推送远程仓库。确认这条边界后，再进入放行判断。
          </p>
          <button
            type="button"
            onClick={() => setCommitDraftAcknowledged(true)}
            className="mt-4 rounded border border-[#444444] px-4 py-2 text-sm text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
            data-testid="execution-repository-open-release-judge"
          >
            查看放行判断
          </button>
        </section>
      ) : null}

      {activeStep === "release_judge" ? (
        <section data-testid="execution-repository-release-gate-panel">
          <RepositoryReleaseGatePanel
            projectId={selectedProjectId}
            projectName={selectedProjectName}
          />
        </section>
      ) : null}

      {/* ── 提交草案说明 ── */}
      {candidates.length > 0 && (
        <div className="rounded border border-[#333333] px-3 py-2 text-[11px] text-zinc-500">
          提交草案仅记录候选版本与证据，不是本地提交，不会推送远程仓库。
        </div>
      )}

      {/* ── 完整入口 ── */}
      <div className="border-t border-[#333333] pt-4">
        <button
          type="button"
          onClick={handleOpenFullRepo}
          className="rounded border border-[#444444] px-4 py-2 text-sm text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
        >
          打开完整仓库工作区
        </button>
        <p className="mt-1 text-[11px] text-zinc-600">
          完整仓库页包含文件定位、上下文包、变更批次、预检、提交草案、仓库树等完整能力
        </p>
      </div>
    </div>
  );
}

/* ─── Status Item ─── */

function StatusItem({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "muted";
}) {
  const textColor =
    tone === "ok" ? "text-zinc-300" : tone === "warn" ? "text-zinc-400" : "text-zinc-600";
  return (
    <div className="rounded border border-[#333333] px-3 py-2">
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className={`text-sm font-medium mt-0.5 ${textColor}`}>{value}</div>
    </div>
  );
}

/* ─── Current Step Panel ─── */

function CurrentStepPanel({
  activeStep,
  snapshot,
  session,
  batchCount,
  candidateCount,
  hasPreflight,
}: {
  activeStep: string;
  snapshot: unknown;
  session: unknown;
  batchCount: number;
  candidateCount: number;
  hasPreflight: boolean;
}) {
  const message = getStepMessage(activeStep, { snapshot, session, batchCount, candidateCount, hasPreflight });

  return (
    <div className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4">
      <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-2">
        当前阶段
      </h3>
      <p className="text-sm text-zinc-300">{message.title}</p>
      <p className="mt-1 text-xs text-zinc-500">{message.detail}</p>
    </div>
  );
}

function getStepMessage(
  step: string,
  ctx: { snapshot: unknown; session: unknown; batchCount: number; candidateCount: number; hasPreflight: boolean },
): { title: string; detail: string } {
  switch (step) {
    case "change_request":
      return {
        title: "变更需求阶段",
        detail: "仓库快照尚未生成。请先通过 AI 项目主管发起仓库绑定与变更需求。",
      };
    case "ai_assess":
      return {
        title: "AI 主管评估阶段",
        detail: "仓库快照已绑定。AI 项目主管待评估变更需求并创建变更会话。",
      };
    case "file_locate":
      return {
        title: "文件定位阶段",
        detail: "变更会话已创建。可通过文件定位器搜索与任务关联的文件。",
      };
    case "context_pack":
      return {
        title: "上下文包阶段",
        detail: "文件定位完成后，可生成代码上下文包供 Agent 使用。",
      };
    case "change_plan":
      return {
        title: "变更方案阶段",
        detail: "可基于上下文包和文件定位结果创建变更方案。",
      };
    case "change_batch":
      return {
        title: `变更批次阶段（${ctx.batchCount} 个批次）`,
        detail: ctx.hasPreflight
          ? "已有批次完成预检。可进入提交草案或放行判断。"
          : "变更批次已创建，可执行预检评估风险。",
      };
    case "preflight":
      return {
        title: "预检阶段",
        detail: "预检已完成，可查看风险发现并决定是否放行。",
      };
    case "commit_draft":
      return {
        title: `提交草案阶段（${ctx.candidateCount} 个草案）`,
        detail: "提交草案已生成。这不是本地提交，不会推送远程仓库。仅记录候选版本与证据。",
      };
    case "release_judge":
      return {
        title: "放行判断阶段",
        detail: "所有草案和预检结果就绪，待人工进行最终放行判断。",
      };
    default:
      return { title: "仓库工作区", detail: "查看仓库状态与变更链路。" };
  }
}
