import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { useProjectDirectorInbox } from "../../../features/project-director/hooks";
import type {
  ProjectDirectorInboxItem,
  ProjectDirectorInboxItemKind,
  ProjectDirectorInboxItemPriority,
  ProjectDirectorInboxItemStatus,
} from "../../../features/project-director/types";
import { formatDateTime } from "../../../lib/format";

interface ProjectDirectorInboxPanelProps {
  projectId: string | null;
  onSelectConversation: (conversation: {
    conversation_id: string;
    project_id: string | null;
  }) => void;
  onNavigateToTask: (taskId: string, projectId?: string | null) => void;
  onNavigateToRun: (
    runId: string,
    taskId: string,
    projectId?: string | null,
  ) => void;
}

type InboxFilter = "all" | "needs_response" | "critical";

const KIND_LABELS: Record<ProjectDirectorInboxItemKind, string> = {
  note: "备注",
  user_challenge_seed: "质疑种子",
  plan_question: "计划问题",
  dispatch_question: "调度建议",
  approval_attention: "审批关注",
  run_blocker: "运行阻塞",
  failure_recovery_attention: "失败处理",
  proposal_attention: "提案关注",
  governance_warning: "治理警告",
  system_notice: "系统通知",
};

const STATUS_LABELS: Record<ProjectDirectorInboxItemStatus, string> = {
  unread: "未读",
  read: "已读",
  needs_response: "需要处理",
  linked_to_conversation: "已关联会话",
  converted_to_challenge: "已转质疑",
  converted_to_proposal: "已转提案",
  resolved: "已处理",
  archived: "已归档",
};

const PRIORITY_LABELS: Record<ProjectDirectorInboxItemPriority, string> = {
  low: "低",
  normal: "普通",
  high: "高",
  critical: "紧急",
};

export function ProjectDirectorInboxPanel({
  projectId,
  onSelectConversation,
  onNavigateToTask,
  onNavigateToRun,
}: ProjectDirectorInboxPanelProps) {
  const [filter, setFilter] = useState<InboxFilter>("all");
  const inboxQuery = useProjectDirectorInbox({
    project_id: projectId,
    status: filter === "needs_response" ? "needs_response" : null,
    priority: filter === "critical" ? "critical" : null,
    limit: 20,
  });
  const items = inboxQuery.data?.items ?? [];
  const criticalCount = items.filter((item) => item.priority === "critical").length;
  const actionCount = items.filter((item) => item.requires_user_action).length;

  return (
    <section
      data-testid="project-director-inbox-panel"
      className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4"
    >
      <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-zinc-100">主管收件箱</h2>
            {actionCount > 0 ? (
              <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                {actionCount} 项需要你处理
              </span>
            ) : null}
            {criticalCount > 0 ? (
              <span className="rounded border border-rose-500/40 bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-200">
                {criticalCount} 项紧急
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-5 text-zinc-500">
            这里汇总需要 AI 项目主管关注的事项。这里只能查看和跳转，
            不会修改任务、运行记录或项目。
          </p>
          <p className="mt-1 text-xs leading-5 text-cyan-100/70">
            P9 fake runtime readback 已接入：仅观察 fake session，不代表真实执行器已启动。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-500">
            {projectId
              ? `当前项目：${projectId.slice(0, 8)}`
              : "全部项目 / 新项目会话"}
          </span>
          <button
            type="button"
            onClick={() => {
              void inboxQuery.refetch();
            }}
            className="rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222]"
          >
            {inboxQuery.isFetching ? "刷新中..." : "刷新"}
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <InboxFilterButton
          active={filter === "all"}
          label="全部"
          onClick={() => setFilter("all")}
        />
        <InboxFilterButton
          active={filter === "needs_response"}
          label="只看需要处理"
          onClick={() => setFilter("needs_response")}
        />
        <InboxFilterButton
          active={filter === "critical"}
          label="只看紧急"
          onClick={() => setFilter("critical")}
        />
      </div>

      {inboxQuery.isLoading ? (
        <div className="space-y-2" data-testid="director-inbox-loading">
          {Array.from({ length: 2 }).map((_, index) => (
            <div
              key={index}
              className="h-[96px] animate-pulse rounded border border-[#333333] bg-[#171717]"
            />
          ))}
        </div>
      ) : null}

      {inboxQuery.isError ? (
        <div
          data-testid="director-inbox-error"
          className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
        >
          主管收件箱读取失败：{inboxQuery.error.message}
        </div>
      ) : null}

      {!inboxQuery.isLoading && !inboxQuery.isError && items.length === 0 ? (
        <div
          data-testid="director-inbox-empty"
          className="rounded border border-dashed border-[#333333] bg-[#111111] px-3 py-4 text-sm text-zinc-500"
        >
          暂无需要 AI 项目主管关注的提醒。
        </div>
      ) : null}

      {items.length > 0 ? (
        <ul className="max-h-72 space-y-2 overflow-y-auto pr-1">
          {items.map((item) => (
            <li
              key={item.id}
              className={`rounded border px-3 py-2 ${
                item.priority === "critical"
                  ? "border-rose-500/40 bg-rose-500/10"
                  : item.priority === "high"
                    ? "border-amber-500/30 bg-amber-500/10"
                    : "border-[#333333] bg-[#111111]"
              }`}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-medium text-zinc-100">
                      {item.title || "未命名收件箱事项"}
                    </p>
                    {item.requires_user_action ? (
                      <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                        需要你处理
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500">
                    {item.summary || "暂无摘要"}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-1 sm:justify-end">
                  <StatusBadge
                    label={KIND_LABELS[item.kind] ?? item.kind}
                    tone="info"
                  />
                  <StatusBadge
                    label={STATUS_LABELS[item.status] ?? item.status}
                    tone={mapStatusTone(item.status)}
                  />
                  <StatusBadge
                    label={PRIORITY_LABELS[item.priority] ?? item.priority}
                    tone={mapPriorityTone(item.priority)}
                  />
                </div>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-zinc-600">
                <span>来源：{formatSourcePage(item.source_page)}</span>
                <span>关联内容：{formatSourceEntityType(item.source_entity_type)}</span>
                <span>创建：{formatDateTime(item.created_at)}</span>
                <span>更新：{formatDateTime(item.updated_at)}</span>
              </div>

              <InboxReferences item={item} />

              <div className="mt-2 flex flex-wrap gap-2">
                {item.conversation_id ? (
                  <button
                    type="button"
                    onClick={() =>
                      onSelectConversation({
                        conversation_id: item.conversation_id as string,
                        project_id: item.project_id,
                      })
                    }
                    className="rounded border border-cyan-500/40 px-2 py-1 text-[10px] text-cyan-200 transition hover:bg-cyan-500/10"
                  >
                    查看相关对话
                  </button>
                ) : null}
                {item.related_task_id ? (
                  <button
                    type="button"
                    onClick={() =>
                      onNavigateToTask(item.related_task_id as string, item.project_id)
                    }
                    className="rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222]"
                  >
                    查看任务
                  </button>
                ) : null}
                {item.related_run_id && item.related_task_id ? (
                  <button
                    type="button"
                    onClick={() =>
                      onNavigateToRun(
                        item.related_run_id as string,
                        item.related_task_id as string,
                        item.project_id,
                      )
                    }
                    className="rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222]"
                  >
                    查看运行记录
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function InboxFilterButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded border px-2 py-1 text-[10px] transition ${
        active
          ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-200"
          : "border-[#333333] text-zinc-400 hover:border-zinc-500 hover:bg-[#222222]"
      }`}
    >
      {label}
    </button>
  );
}

function InboxReferences({ item }: { item: ProjectDirectorInboxItem }) {
  const refs = [
    ["对话消息", item.related_message_id],
    ["项目草案", item.related_plan_version_id],
    ["任务", item.related_task_id],
    ["运行记录", item.related_run_id],
  ].filter(([, value]) => Boolean(value));

  if (refs.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-zinc-600">
      {refs.map(([label, value]) => (
        <span key={`${label}-${value}`} className="rounded bg-[#171717] px-1.5 py-0.5">
          {label}:{shortId(value as string)}
        </span>
      ))}
    </div>
  );
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function formatSourcePage(value: string) {
  const labels: Record<string, string> = {
    workbench: "工作台",
    task_detail: "任务详情",
    run_detail: "运行详情",
    worker_timeline: "执行记录",
  };
  return labels[value] ?? "系统整理";
}

function formatSourceEntityType(value: string) {
  const labels: Record<string, string> = {
    message: "对话消息",
    plan_version: "项目草案",
    task: "任务",
    run: "运行记录",
    agent_message: "调度记录",
  };
  return labels[value] ?? "相关记录";
}

function mapStatusTone(
  status: ProjectDirectorInboxItemStatus,
): "neutral" | "info" | "success" | "warning" | "danger" {
  switch (status) {
    case "needs_response":
    case "unread":
      return "warning";
    case "resolved":
    case "linked_to_conversation":
      return "success";
    case "archived":
      return "neutral";
    default:
      return "info";
  }
}

function mapPriorityTone(
  priority: ProjectDirectorInboxItemPriority,
): "neutral" | "info" | "success" | "warning" | "danger" {
  switch (priority) {
    case "critical":
      return "danger";
    case "high":
      return "warning";
    case "low":
      return "neutral";
    default:
      return "info";
  }
}
