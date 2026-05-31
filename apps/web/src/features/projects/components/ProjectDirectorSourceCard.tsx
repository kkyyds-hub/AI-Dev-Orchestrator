import { StatusBadge } from "../../../components/StatusBadge";
import {
  collectProjectDirectorSource,
  type ProjectDirectorSourceReadback,
} from "../lib/projectDirectorSource";
import type { BossProjectItem, ProjectDetail } from "../types";

type ProjectDirectorSourceCardProps = {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  compact?: boolean;
};

export function ProjectDirectorSourceCard({
  project,
  detail,
  compact = false,
}: ProjectDirectorSourceCardProps) {
  const readback = collectProjectDirectorSource({
    items: [project, detail, ...(detail?.tasks ?? [])],
  });

  if (!readback) {
    return null;
  }

  return (
    <section
      data-testid="project-director-source-card"
      className={`rounded-lg border border-cyan-500/25 bg-cyan-500/5 ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-cyan-100">
              AI 主管创建
            </h4>
            <StatusBadge label="只读来源" tone="info" />
          </div>
          <p className="mt-1 text-xs leading-5 text-cyan-100/75">
            该项目读回到 AI 项目主管创建来源；这里只展示正式项目与任务队列的来源映射。
          </p>
        </div>
      </div>

      <SourceIdGrid readback={readback} compact={compact} />

      <div className="mt-3 rounded border border-cyan-500/20 bg-[#111111]/70 px-3 py-2">
        <p className="text-xs font-medium text-cyan-100">
          草案建议尚未真实落地
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-cyan-100/80">
          <li>Agent/Skill/仓库/验证机制仅来自草案建议，仍未自动创建或绑定。</li>
          <li>正式项目创建不会自动创建 Agent Session、Skill 绑定、仓库绑定或 Run。</li>
          <li>未触发 provider、Worker、planning/apply、apply-local 或产品内 git-commit。</li>
        </ul>
      </div>
    </section>
  );
}

function SourceIdGrid({
  readback,
  compact,
}: {
  readback: ProjectDirectorSourceReadback;
  compact: boolean;
}) {
  const visibleDraftIds = compact
    ? readback.sourceDraftIds.slice(0, 3)
    : readback.sourceDraftIds.slice(0, 8);
  const hiddenDraftCount = Math.max(
    0,
    readback.sourceDraftIds.length - visibleDraftIds.length,
  );

  return (
    <div className={`mt-3 grid gap-2 ${compact ? "" : "sm:grid-cols-2"}`}>
      <SourceIdBlock
        label="草案版本 ID"
        value={readback.sourcePlanVersionId}
      />
      <div className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2">
        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-600">
          任务草案追溯 ID
        </div>
        {visibleDraftIds.length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-1">
            {visibleDraftIds.map((draftId) => (
              <span
                key={draftId}
                title={draftId}
                className="max-w-full break-all rounded border border-[#333333] bg-[#171717] px-2 py-0.5 font-mono text-[11px] text-zinc-300"
              >
                {draftId}
              </span>
            ))}
            {hiddenDraftCount > 0 ? (
              <span className="rounded border border-[#333333] bg-[#171717] px-2 py-0.5 text-[11px] text-zinc-500">
                +{hiddenDraftCount}
              </span>
            ) : null}
          </div>
        ) : (
          <div className="mt-1 text-xs text-zinc-500">后端未返回任务草案 ID</div>
        )}
      </div>
    </div>
  );
}

function SourceIdBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-600">
        {label}
      </div>
      <div className="mt-1 break-all font-mono text-xs text-zinc-300">
        {value}
      </div>
    </div>
  );
}
