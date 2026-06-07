import { StatusBadge } from "../../../components/StatusBadge";
import { useProjectDirectorConversations } from "../../../features/project-director/hooks";
import type {
  ProjectDirectorConversationKind,
  ProjectDirectorConversationListItem,
  ProjectDirectorConversationStatus,
} from "../../../features/project-director/types";
import { formatDateTime } from "../../../lib/format";

interface ProjectDirectorConversationListProps {
  projectId: string | null;
  selectedConversationId: string | null;
  onSelectConversation: (conversation: ProjectDirectorConversationListItem) => void;
}

const KIND_LABELS: Record<ProjectDirectorConversationKind, string> = {
  project_onboarding: "目标澄清",
  general_discussion: "自由讨论",
  plan_review: "草案审核",
  follow_up: "后续跟进",
};

const STATUS_LABELS: Record<ProjectDirectorConversationStatus, string> = {
  active: "活跃",
  idle: "空闲",
  awaiting_user: "待用户",
  archived: "已归档",
  completed: "已完成",
};

export function ProjectDirectorConversationList({
  projectId,
  selectedConversationId,
  onSelectConversation,
}: ProjectDirectorConversationListProps) {
  const conversationsQuery = useProjectDirectorConversations({
    project_id: projectId,
    limit: 20,
  });
  const conversations = conversationsQuery.data?.conversations ?? [];

  return (
    <section
      data-testid="project-director-conversation-list"
      className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4"
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">主管会话列表</h2>
          <p className="mt-1 text-xs text-zinc-500">
            只读读取 ConversationList；点击会话仅恢复消息，不创建 session、不触发
            Provider。
          </p>
        </div>
        <span className="w-fit rounded border border-[#333333] px-2 py-1 text-[10px] text-zinc-500">
          {projectId ? `project ${projectId.slice(0, 8)}` : "全部 / 新项目会话"}
        </span>
      </div>

      {conversationsQuery.isLoading ? (
        <div className="space-y-2" data-testid="conversation-list-loading">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="h-[78px] animate-pulse rounded border border-[#333333] bg-[#171717]"
            />
          ))}
        </div>
      ) : null}

      {conversationsQuery.isError ? (
        <div
          data-testid="conversation-list-error"
          className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
        >
          会话列表读取失败：{conversationsQuery.error.message}
        </div>
      ) : null}

      {!conversationsQuery.isLoading &&
      !conversationsQuery.isError &&
      conversations.length === 0 ? (
        <div
          data-testid="conversation-list-empty"
          className="rounded border border-dashed border-[#333333] bg-[#111111] px-3 py-4 text-sm text-zinc-500"
        >
          还没有主管会话。点击下方“新建主管会话 / 开始新目标”后，再输入目标创建。
        </div>
      ) : null}

      {conversations.length > 0 ? (
        <ul className="space-y-2">
          {conversations.map((conversation) => {
            const isSelected =
              selectedConversationId === conversation.conversation_id;
            const activityAt =
              conversation.last_message_at ?? conversation.updated_at;

            return (
              <li key={conversation.conversation_id}>
                <button
                  type="button"
                  data-testid="conversation-list-item"
                  onClick={() => onSelectConversation(conversation)}
                  className={`w-full rounded border px-3 py-2 text-left transition ${
                    isSelected
                      ? "border-cyan-500/50 bg-cyan-500/10"
                      : "border-[#333333] bg-[#111111] hover:border-zinc-500 hover:bg-[#222222]"
                  }`}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-zinc-100">
                          {conversation.title || "未命名主管会话"}
                        </p>
                        {isSelected ? (
                          <span className="rounded border border-cyan-500/40 px-1.5 py-0.5 text-[10px] text-cyan-200">
                            当前选择
                          </span>
                        ) : null}
                        {conversation.requires_user_action ? (
                          <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                            需要你处理
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500">
                        {conversation.last_message_preview || "暂无消息预览"}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-1 sm:justify-end">
                      <StatusBadge
                        label={KIND_LABELS[conversation.kind] ?? conversation.kind}
                        tone="info"
                      />
                      <StatusBadge
                        label={
                          STATUS_LABELS[conversation.status] ??
                          conversation.status
                        }
                        tone={mapConversationStatusTone(conversation.status)}
                      />
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-zinc-600">
                    <span>{formatDateTime(activityAt)}</span>
                    <span>{conversation.message_count} 条消息</span>
                    <span>
                      {conversation.owner_scope}
                      {conversation.project_id
                        ? ` · ${conversation.project_id.slice(0, 8)}`
                        : " · project_id=null"}
                    </span>
                    {conversation.pending_challenge_count > 0 ? (
                      <span>{conversation.pending_challenge_count} 个待处理质疑</span>
                    ) : null}
                    {conversation.pending_proposal_count > 0 ? (
                      <span>{conversation.pending_proposal_count} 个待审批提案</span>
                    ) : null}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

function mapConversationStatusTone(
  status: ProjectDirectorConversationStatus,
): "neutral" | "info" | "success" | "warning" | "danger" {
  switch (status) {
    case "active":
      return "success";
    case "awaiting_user":
      return "warning";
    case "completed":
      return "info";
    case "archived":
      return "neutral";
    default:
      return "neutral";
  }
}
