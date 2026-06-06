import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { AgentTimelineMessage } from "../types";

type AgentDeliveryDiffEventPanelProps = {
  messages: AgentTimelineMessage[];
};

type DeliveryDiffEventDetail = Record<string, unknown>;

type DeliveryDiffParseResult =
  | { parseState: "ok"; detail: DeliveryDiffEventDetail }
  | { parseState: "empty"; detail: null }
  | { parseState: "invalid"; detail: null };

type DeliveryDiffTone = "neutral" | "info" | "success" | "warning" | "danger";

const DELIVERY_DIFF_EVENT_LABELS: Record<string, string> = {
  delivery_diff_dry_run_collected: "代码改动预览已完成",
  delivery_diff_dry_run_skipped: "代码改动预览已跳过",
  delivery_diff_dry_run_failed: "代码改动预览失败",
};

const DELIVERY_DIFF_EVENT_TONES: Record<string, DeliveryDiffTone> = {
  delivery_diff_dry_run_collected: "success",
  delivery_diff_dry_run_skipped: "warning",
  delivery_diff_dry_run_failed: "danger",
};

const STATE_LABELS: Record<string, string> = {
  none: "未开始",
  diff_dirty: "检测到代码改动",
  diff_clean: "没有代码改动",
  diff_skipped: "已跳过改动预览",
  diff_failed: "改动预览失败",
};

const REASON_LABELS: Record<string, string> = {
  worktree_path_unavailable: "当前没有可检查的工作区",
  worktree_path_missing: "工作区路径缺失",
  worktree_path_not_found: "工作区路径不存在",
  worktree_path_not_directory: "工作区路径不是目录",
  worktree_path_outside_allowed_root: "工作区路径不在允许范围内",
  git_diff_dry_run_command_failed: "只读检查命令失败",
  git_diff_dry_run_command_timed_out: "只读检查命令超时",
  git_diff_dry_run_failed: "代码改动预览失败",
};

const SAFETY_FLAG_LABELS: Record<string, string> = {
  runs_git: "只读代码检查",
  runs_write_git: "提交或推送等写操作",
  git_add_triggered: "加入待提交区",
  git_commit_triggered: "生成本地提交",
  git_push_triggered: "推送远程仓库",
  pr_opened: "创建代码合并请求",
  ci_triggered: "触发自动检查",
  execution_enabled: "开启真实提交",
};

const FORBIDDEN_FALSE_TEXT: Record<string, string> = {
  runs_write_git: "未执行提交或推送等写操作",
  git_add_triggered: "未加入待提交区",
  git_commit_triggered: "未生成本地提交",
  git_push_triggered: "未推送到远程仓库",
  pr_opened: "未创建代码合并请求",
  ci_triggered: "未触发自动检查",
  execution_enabled: "未开启真实提交",
};

export function AgentDeliveryDiffEventPanel(
  props: AgentDeliveryDiffEventPanelProps,
) {
  const deliveryDiffMessages = props.messages
    .filter(isDeliveryDiffEvent)
    .sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    )
    .slice(0, 3);

  if (!deliveryDiffMessages.length) {
    return null;
  }

  return (
    <section
      className="rounded-3xl border border-[#333333] bg-slate-950/25 p-4"
      data-testid="agent-delivery-diff-event-panel"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">
            最近代码改动预览事件
          </h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            从当前会话时间线只读筛选代码改动预览事件；这里只展示审计结果，不加入待提交区、不生成本地提交、不推送远程仓库，也不创建代码合并请求。
          </p>
        </div>
        <span className="text-xs text-slate-500">
          {deliveryDiffMessages.length} 条
        </span>
      </div>

      <ul className="mt-4 space-y-3">
        {deliveryDiffMessages.map((message) => (
          <DeliveryDiffEventItem key={message.message_id} message={message} />
        ))}
      </ul>
    </section>
  );
}

function DeliveryDiffEventItem(props: { message: AgentTimelineMessage }) {
  const message = props.message;
  const parseResult = parseDeliveryDiffDetail(message.content_detail);
  const detail = parseResult.parseState === "ok" ? parseResult.detail : null;
  const evidence = objectField(detail, "evidence");
  const safetyFlags = objectField(detail, "safety_flags");
  const summaryCn = stringField(detail, "summary_cn");
  const reasonCode =
    stringField(detail, "reason_code") ?? stringField(evidence, "reason_code");
  const nextDeliveryState = stringField(detail, "next_delivery_state");
  const changedFiles = stringListField(evidence, "changed_files");
  const addedFiles = stringListField(evidence, "added_files");
  const modifiedFiles = stringListField(evidence, "modified_files");
  const deletedFiles = stringListField(evidence, "deleted_files");
  const renamedFiles = stringListField(evidence, "renamed_files");
  const detailMessage =
    parseResult.parseState === "empty"
      ? "事件详情未记录。"
      : parseResult.parseState === "invalid"
        ? "事件详情无法解析。"
        : null;

  return (
    <li
      className="rounded-2xl border border-[#333333] bg-black/15 p-3"
      data-testid="agent-delivery-diff-event-item"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
            <span>{formatDateTime(message.created_at)}</span>
            <span>{DELIVERY_DIFF_EVENT_LABELS[message.event_type]}</span>
          </div>
          <p
            className="mt-2 line-clamp-3 break-words text-sm leading-6 text-slate-100"
            title={summaryCn ?? message.content_summary}
          >
            {summaryCn ?? message.content_summary}
          </p>
          {detailMessage ? (
            <p className="mt-2 rounded-2xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs leading-5 text-amber-200">
              {detailMessage}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <StatusBadge
            label={DELIVERY_DIFF_EVENT_LABELS[message.event_type]}
            tone={DELIVERY_DIFF_EVENT_TONES[message.event_type] ?? "neutral"}
          />
          <StatusBadge label="只读审计，未交付" tone="info" />
        </div>
      </div>

      <dl className="mt-3 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
        <DeliveryDiffDetail
          label="预览状态"
          value={localizeDeliveryState(nextDeliveryState)}
          title={nextDeliveryState ?? undefined}
        />
        <DeliveryDiffDetail
          label="未就绪原因"
          value={localizeReason(reasonCode)}
          title={reasonCode ?? undefined}
        />
        <DeliveryDiffDetail
          label="改动摘要"
          value={stringField(evidence, "status_summary_cn") ?? "未记录"}
        />
        <DeliveryDiffDetail
          label="改动文件数量"
          value={formatCount(numberField(evidence, "changed_files_count"))}
        />
        <DeliveryDiffDetail
          label="当前分支"
          value={stringField(evidence, "branch_name") ?? "未记录"}
        />
        <DeliveryDiffDetail
          label="对比分支"
          value={stringField(evidence, "compare_branch") ?? "未记录"}
        />
        <DeliveryDiffDetail
          label="检查工作区"
          value={stringField(evidence, "worktree_path") ?? "未记录"}
        />
        <DeliveryDiffDetail
          label="是否有改动"
          value={formatBoolean(booleanField(evidence, "has_changes"))}
        />
      </dl>

      <div className="mt-3 grid gap-3">
        <CompactFileList label="全部改动文件" files={changedFiles} />
        <CompactFileList
          label="分类文件"
          files={[
            ...prefixFiles("新增", addedFiles),
            ...prefixFiles("修改", modifiedFiles),
            ...prefixFiles("删除", deletedFiles),
            ...prefixFiles("重命名", renamedFiles),
          ]}
        />
      </div>

      <div className="mt-3 rounded-2xl border border-[#333333] bg-slate-950/30 p-3">
        <div className="text-xs font-medium text-slate-300">只读安全标记</div>
        <dl className="mt-2 grid gap-x-4 gap-y-2 text-xs text-slate-500 sm:grid-cols-2">
          {Object.entries(SAFETY_FLAG_LABELS).map(([key, label]) => (
            <DeliveryDiffDetail
              key={key}
              label={label}
              value={formatSafetyFlag(key, booleanField(safetyFlags, key))}
            />
          ))}
        </dl>
      </div>
    </li>
  );
}

function isDeliveryDiffEvent(message: AgentTimelineMessage) {
  return Object.prototype.hasOwnProperty.call(
    DELIVERY_DIFF_EVENT_LABELS,
    message.event_type,
  );
}

function parseDeliveryDiffDetail(
  contentDetail: string | null,
): DeliveryDiffParseResult {
  if (!contentDetail) {
    return { parseState: "empty", detail: null };
  }

  try {
    const parsed = JSON.parse(contentDetail) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return { parseState: "ok", detail: parsed as DeliveryDiffEventDetail };
    }
  } catch {
    return { parseState: "invalid", detail: null };
  }

  return { parseState: "invalid", detail: null };
}

function objectField(
  detail: DeliveryDiffEventDetail | null,
  key: "evidence" | "safety_flags",
): Record<string, unknown> | null {
  const value = detail?.[key];
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function stringField(
  detail: Record<string, unknown> | null | undefined,
  key: string,
): string | null {
  const value = detail?.[key];
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function numberField(
  detail: Record<string, unknown> | null | undefined,
  key: string,
): number | null {
  const value = detail?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringListField(
  detail: Record<string, unknown> | null | undefined,
  key: string,
): string[] {
  const value = detail?.[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .filter((item) => item.trim().length > 0);
}

function booleanField(
  detail: Record<string, unknown> | null | undefined,
  key: string,
): boolean | null {
  const value = detail?.[key];
  return typeof value === "boolean" ? value : null;
}

function localizeDeliveryState(value: string | null) {
  if (!value) {
    return "未记录";
  }
  return STATE_LABELS[value] ?? "未识别状态";
}

function localizeReason(value: string | null) {
  if (!value) {
    return "无";
  }
  return REASON_LABELS[value] ?? "未识别原因";
}

function formatBoolean(value: boolean | null) {
  if (value === null) {
    return "未记录";
  }
  return value ? "是" : "否";
}

function formatCount(value: number | null) {
  return value === null ? "未记录" : `${value} 个`;
}

function formatSafetyFlag(key: string, value: boolean | null) {
  if (key === "runs_git") {
    if (value === true) {
      return "已执行只读代码检查";
    }
    if (value === false) {
      return "未执行代码检查";
    }
    return "未记录";
  }

  if (value === true) {
    return "安全标记异常";
  }
  if (value === false) {
    return FORBIDDEN_FALSE_TEXT[key] ?? "未执行写操作";
  }
  return "未记录";
}

function prefixFiles(label: string, files: string[]) {
  return files.map((file) => `${label}：${file}`);
}

function CompactFileList(props: { label: string; files: string[] }) {
  return (
    <div className="rounded-2xl border border-[#333333] bg-slate-950/30 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-medium text-slate-300">{props.label}</div>
        <span className="text-xs text-slate-500">{props.files.length} 个</span>
      </div>
      {props.files.length ? (
        <ul className="mt-2 max-h-28 space-y-1 overflow-auto pr-2 text-xs leading-5 text-slate-400">
          {props.files.map((file) => (
            <li key={`${props.label}-${file}`} className="break-all">
              {file}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs leading-5 text-slate-500">暂无记录。</p>
      )}
    </div>
  );
}

function DeliveryDiffDetail(props: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="min-w-0" title={props.title}>
      <dt className="text-slate-500">{props.label}</dt>
      <dd className="mt-1 break-words text-slate-300">{props.value}</dd>
    </div>
  );
}
