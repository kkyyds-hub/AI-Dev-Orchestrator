import type { ProjectDirectorWorkbenchResumableSession } from "../../project-director/types";
import type { BossProjectItem } from "../../projects/types";
import type {
  Conversation,
  ProjectGroup,
} from "../../ui-selection-lab/mockInteractions";

export function buildRealWorkbenchProjectGroups(input: {
  projects: BossProjectItem[];
  resumableSessions: ProjectDirectorWorkbenchResumableSession[];
}): ProjectGroup[] {
  const groups = input.projects.map((project) => {
    const conversations = input.resumableSessions
      .filter((session) => session.project_id === project.id)
      .map(mapResumableSessionToConversation);

    return {
      id: project.id,
      name: project.name,
      conversations:
        conversations.length > 0
          ? conversations
          : [
              {
                id: `project:${project.id}`,
                title: "继续 AI 主管对话",
                status: "pending" as const,
              },
            ],
    };
  });

  const unboundSessions = input.resumableSessions.filter(
    (session) => session.project_id === null,
  );

  if (unboundSessions.length > 0) {
    groups.unshift({
      id: "new-project",
      name: "新项目会话",
      conversations: unboundSessions.map(mapResumableSessionToConversation),
    });
  }

  return groups;
}

function mapResumableSessionToConversation(
  session: ProjectDirectorWorkbenchResumableSession,
): Conversation {
  return {
    id: session.session_id,
    title: compactText(session.goal_summary || session.goal_text || "未完成 AI 主管会话", 28),
    status: mapSessionStatus(session.status),
  };
}

function mapSessionStatus(
  status: ProjectDirectorWorkbenchResumableSession["status"],
): Conversation["status"] {
  if (status === "confirmed") {
    return "passed";
  }

  if (status === "ready_to_confirm") {
    return "partial";
  }

  if (status === "clarifying") {
    return "running";
  }

  return "pending";
}

function compactText(value: string, maxLength: number) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength)}...`;
}
