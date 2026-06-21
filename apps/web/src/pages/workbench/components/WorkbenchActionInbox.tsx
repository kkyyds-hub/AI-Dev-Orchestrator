import { ClipboardCheck, ExternalLink, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useProjectDirectorInbox } from "../../../features/project-director/hooks";
import type { ProjectDirectorInboxItem } from "../../../features/project-director/types";

type WorkbenchActionInboxProps = {
  projectId: string | null;
};

export function WorkbenchActionInbox({ projectId }: WorkbenchActionInboxProps) {
  const [expanded, setExpanded] = useState(false);
  const inboxQuery = useProjectDirectorInbox({
    project_id: projectId,
    limit: 12,
  });
  const items = inboxQuery.data?.items ?? [];
  const actionItems = items.filter((item) => item.requires_user_action);
  const visibleItems = actionItems.length > 0 ? actionItems : items.slice(0, 4);
  const actionCount = actionItems.length;
  const title = actionCount > 0 ? `需要你处理 ${actionCount} 项` : "需要你处理";
  const subtitle = useMemo(() => {
    if (inboxQuery.isLoading) {
      return "读取确认事项";
    }
    if (inboxQuery.isError) {
      return "暂时无法读取";
    }
    if (actionCount > 0) {
      return "影响项目推进";
    }
    return "暂无阻塞事项";
  }, [actionCount, inboxQuery.isError, inboxQuery.isLoading]);

  return (
    <section
      data-testid="workbench-action-inbox"
      className="relative w-full min-w-0 md:w-[min(42vw,460px)]"
    >
      <button
        type="button"
        className="flex h-11 w-full items-center justify-between gap-3 border-y border-[#2A2A2A] px-3 text-left transition-colors hover:bg-white/[0.03]"
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <ClipboardCheck className="h-4 w-4 shrink-0 text-[#C7C7C7]" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-white">
              {title}
            </span>
            <span className="mt-0.5 block truncate text-xs text-[#8A8A8A]">
              {subtitle}
            </span>
          </span>
        </span>
        <span className="shrink-0 text-xs text-[#C7C7C7]">
          {expanded ? "收起" : "展开"}
        </span>
      </button>

      <div
        className={`absolute right-0 top-[calc(100%+12px)] z-40 w-[min(540px,calc(100vw-32px))] overflow-hidden border border-[#2A2A2A] bg-[#050505] shadow-[0_24px_80px_rgba(0,0,0,0.72)] transition-[opacity,transform] duration-200 ${
          expanded
            ? "translate-y-0 opacity-100"
            : "pointer-events-none -translate-y-2 opacity-0"
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#1F1F1F] px-4 py-3">
          <div>
            <div className="text-sm font-semibold text-white">{title}</div>
            <div className="mt-1 text-xs text-[#8A8A8A]">
              来自 AI 主管收件箱；页面内操作入口仍保留。
            </div>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs text-[#8A8A8A] transition-colors hover:bg-[#1F1F1F] hover:text-white"
            onClick={() => {
              void inboxQuery.refetch();
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            刷新
          </button>
        </div>

        <div className="max-h-[420px] overflow-y-auto px-4 py-3">
          {inboxQuery.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="h-[76px] animate-pulse border border-[#1F1F1F] bg-[#111111]"
                />
              ))}
            </div>
          ) : null}

          {inboxQuery.isError ? (
            <div className="border border-[#2A2A2A] bg-[#0B0B0B] px-3 py-4 text-sm text-[#8A8A8A]">
              暂时无法读取需要处理事项。你仍可以在审批、成果或任务页面内处理。
            </div>
          ) : null}

          {!inboxQuery.isLoading && !inboxQuery.isError && visibleItems.length === 0 ? (
            <div className="border border-[#1F1F1F] bg-[#0B0B0B] px-3 py-4 text-sm text-[#8A8A8A]">
              当前没有需要你处理的事项。
            </div>
          ) : null}

          {visibleItems.length > 0 ? (
            <ul className="space-y-2">
              {visibleItems.map((item) => (
                <li key={item.id} className="border-b border-[#111111] pb-3 last:border-b-0">
                  <div className="flex items-start justify-between gap-4">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[#D7D7D7]">
                        {item.title || "未命名确认事项"}
                      </span>
                      <span className="mt-1 block line-clamp-2 text-xs leading-5 text-[#8A8A8A]">
                        {item.summary || "暂无摘要"}
                      </span>
                    </span>
                    <ActionLink item={item} />
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="border-t border-[#1F1F1F] px-4 py-3">
          <Link
            to="/delivery?tab=approvals"
            className="inline-flex items-center gap-2 text-xs text-[#C7C7C7] transition hover:text-white"
          >
            打开成果与确认
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}

function ActionLink({ item }: { item: ProjectDirectorInboxItem }) {
  if (item.related_run_id && item.related_task_id) {
    return (
      <Link
        to={buildSurfaceRoute("/execution", item.project_id)}
        className="shrink-0 rounded-full border border-[#333333] px-2.5 py-1 text-xs text-[#C7C7C7] transition hover:border-[#5A5A5A] hover:text-white"
      >
        查看
      </Link>
    );
  }

  if (item.related_task_id) {
    return (
      <Link
        to={buildSurfaceRoute("/execution", item.project_id)}
        className="shrink-0 rounded-full border border-[#333333] px-2.5 py-1 text-xs text-[#C7C7C7] transition hover:border-[#5A5A5A] hover:text-white"
      >
        处理
      </Link>
    );
  }

  if (item.related_approval_id) {
    return (
      <Link
        to={buildSurfaceRoute("/delivery", item.project_id, { tab: "approvals" })}
        className="shrink-0 rounded-full border border-[#333333] px-2.5 py-1 text-xs text-[#C7C7C7] transition hover:border-[#5A5A5A] hover:text-white"
      >
        处理
      </Link>
    );
  }

  return (
    <Link
      to="/delivery?tab=approvals"
      className="shrink-0 rounded-full border border-[#333333] px-2.5 py-1 text-xs text-[#C7C7C7] transition hover:border-[#5A5A5A] hover:text-white"
    >
      查看
    </Link>
  );
}

function buildSurfaceRoute(
  pathname: "/execution" | "/delivery",
  projectId: string | null,
  extraParams: Record<string, string> = {},
) {
  const params = new URLSearchParams(extraParams);
  if (projectId) {
    params.set("projectId", projectId);
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}
