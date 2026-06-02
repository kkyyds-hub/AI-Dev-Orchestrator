import { useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { PROJECT_STAGE_LABELS } from "../../projects/types";
import { ROLE_CODE_LABELS } from "../../roles/types";
import { DeliverableVersionEmptyState } from "./DeliverableVersionEmptyState";
import {
  DELIVERABLE_CONTENT_FORMAT_LABELS,
  DELIVERABLE_STATUS_LABELS,
  DELIVERABLE_STATUS_TONES,
  DELIVERABLE_TYPE_LABELS,
  type DeliverableDetail,
  type DeliverableEvidenceRef,
  type DeliverableSummary,
  type DeliverableVersion,
} from "../types";

type DrawerKind = "body" | "evidence" | "versions";

type DeliverableSummaryPanelProps = {
  deliverable: DeliverableSummary | null;
  detail: DeliverableDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

const PANEL_TITLE = "\u4ea4\u4ed8\u7269\u6458\u8981\u9762\u677f";
const PANEL_DESC = "\u5e38\u9a7b\u533a\u53ea\u5c55\u793a\u6458\u8981\u548c\u51b3\u7b56\u524d\u4fe1\u606f\uff1b\u6b63\u6587\u3001\u8bc1\u636e\u94fe\u548c\u7248\u672c\u8bb0\u5f55\u901a\u8fc7\u5f39\u7a97\u67e5\u770b\u3002";
const SUMMARY_LABEL = "\u6458\u8981";
const BODY_BUTTON = "\u67e5\u770b\u6b63\u6587";
const EVIDENCE_BUTTON = "\u67e5\u770b\u8bc1\u636e";
const VERSION_BUTTON = "\u7248\u672c\u8bb0\u5f55";
const NO_SUMMARY = "\u6682\u65e0\u4ea4\u4ed8\u6458\u8981\u3002";
const NO_BODY = "\u6682\u65e0\u53ef\u5c55\u793a\u7684\u4ea4\u4ed8\u7269\u6b63\u6587\u3002";
const NO_EVIDENCE = "\u540e\u7aef\u5f53\u524d\u8fd4\u56de\u7684 evidence_refs \u4e3a\u7a7a\uff1b\u4fdd\u7559\u8bc1\u636e\u94fe\u5165\u53e3\uff0c\u7b49\u540e\u7eed\u6301\u4e45\u5316\u8865\u9f50\u540e\u76f4\u63a5\u6d88\u8d39\u3002";
const LOADING_DETAIL = "\u6b63\u5728\u52a0\u8f7d\u4ea4\u4ed8\u7269\u8be6\u60c5...";
const DETAIL_FAILED_PREFIX = "\u4ea4\u4ed8\u7269\u8be6\u60c5\u52a0\u8f7d\u5931\u8d25\uff1a";
const LATEST_VERSION = "\u6700\u65b0\u7248\u672c";
const CREATED_BY = "\u521b\u5efa\u8005";
const UPDATED_AT = "\u66f4\u65b0\u65f6\u95f4";
const SOURCE_LABEL = "\u6765\u6e90";
const SOURCE_DRAFT_ID = "source_draft_id";
const REPOSITORY_CHANGE_ID = "repository_change_id";
const TASK_LINK = "\u67e5\u770b\u6765\u6e90\u4efb\u52a1";
const RUN_LINK = "\u67e5\u770b\u6765\u6e90\u8fd0\u884c";
const CLOSE = "\u5173\u95ed";
const BODY_TITLE = "\u4ea4\u4ed8\u7269\u6b63\u6587";
const EVIDENCE_TITLE = "\u8bc1\u636e\u94fe";
const VERSIONS_TITLE = "\u7248\u672c\u8bb0\u5f55";
const VERSION_COUNT = "\u4e2a\u7248\u672c";
const EVIDENCE_COUNT = "\u6761\u8bc1\u636e";

export function DeliverableSummaryPanel(props: DeliverableSummaryPanelProps) {
  const [drawerKind, setDrawerKind] = useState<DrawerKind | null>(null);

  if (!props.deliverable) {
    return <DeliverableVersionEmptyState />;
  }

  const deliverable = props.deliverable;
  const body = props.detail?.content_markdown ?? deliverable.content_markdown ?? "";
  const versions = props.detail?.versions ?? [];
  const evidenceRefs = props.detail?.evidence_refs ?? deliverable.evidence_refs ?? [];
  const latestVersion = props.detail?.versions[0] ?? null;
  const sourceTaskId = props.detail?.task_id ?? deliverable.task_id;
  const sourceRunId = props.detail?.run_id ?? deliverable.run_id;
  const sourceLabel = props.detail?.source_label ?? deliverable.source_label;
  const sourceDraftId =
    props.detail?.source_draft_id ?? deliverable.source_draft_id;
  const repositoryChangeId =
    props.detail?.repository_change_id ?? deliverable.repository_change_id;

  return (
    <section
      className="space-y-5 border-b border-[#333333] pb-5"
      data-testid="deliverable-summary-panel"
    >
      <header className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">
            {PANEL_TITLE}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h3 className="text-xl font-semibold text-zinc-100">{deliverable.title}</h3>
            <StatusBadge
              label={DELIVERABLE_STATUS_LABELS[deliverable.status] ?? deliverable.status}
              tone={DELIVERABLE_STATUS_TONES[deliverable.status] ?? "neutral"}
            />
            <StatusBadge
              label={DELIVERABLE_TYPE_LABELS[deliverable.type] ?? deliverable.type}
              tone="info"
            />
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            {PANEL_DESC}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge label={`v${deliverable.version_no}`} tone="success" />
          <StatusBadge
            label={PROJECT_STAGE_LABELS[deliverable.stage] ?? deliverable.stage}
            tone="neutral"
          />
        </div>
      </header>

      {props.isLoading ? (
        <div className="border border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-400">
          {LOADING_DETAIL}
        </div>
      ) : null}

      {props.errorMessage ? (
        <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          {DETAIL_FAILED_PREFIX}{props.errorMessage}
        </div>
      ) : null}

      <section className="border-y border-[#333333] py-5">
        <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">
          {SUMMARY_LABEL}
        </div>
        <p className="mt-3 text-sm leading-7 text-zinc-200">
          {deliverable.summary || deliverable.latest_version.summary || NO_SUMMARY}
        </p>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <MiniInfo label={LATEST_VERSION} value={`v${deliverable.version_no}`} />
        <MiniInfo
          label={CREATED_BY}
          value={
            ROLE_CODE_LABELS[deliverable.created_by] ??
            ROLE_CODE_LABELS[deliverable.created_by_role_code] ??
            deliverable.created_by
          }
        />
        <MiniInfo label={UPDATED_AT} value={formatDateTime(deliverable.updated_at)} />
        <MiniInfo label={SOURCE_LABEL} value={sourceLabel ?? deliverable.source_type ?? "-"} />
        <MiniInfo label={SOURCE_DRAFT_ID} value={sourceDraftId ?? "-"} />
        <MiniInfo label={REPOSITORY_CHANGE_ID} value={repositoryChangeId ?? "-"} />
      </div>

      <div className="grid gap-3 sm:grid-cols-3" data-testid="deliverable-detail-entrypoints">
        <PanelButton label={BODY_BUTTON} meta={body ? "Markdown" : "-"} onClick={() => setDrawerKind("body")} />
        <PanelButton label={EVIDENCE_BUTTON} meta={`${evidenceRefs.length} ${EVIDENCE_COUNT}`} onClick={() => setDrawerKind("evidence")} />
        <PanelButton label={VERSION_BUTTON} meta={`${deliverable.total_versions} ${VERSION_COUNT}`} onClick={() => setDrawerKind("versions")} />
      </div>

      {(sourceTaskId || sourceRunId) && props.onNavigateToTask ? (
        <div className="flex flex-wrap gap-3">
          {sourceTaskId ? (
            <button
              type="button"
              onClick={() => props.onNavigateToTask?.(sourceTaskId, { runId: null })}
              className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm text-zinc-100 transition hover:bg-[#292929]"
            >
              {TASK_LINK}
            </button>
          ) : null}
          {sourceTaskId && sourceRunId ? (
            <button
              type="button"
              onClick={() => props.onNavigateToTask?.(sourceTaskId, { runId: sourceRunId })}
              className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm text-zinc-100 transition hover:bg-[#292929]"
            >
              {RUN_LINK}
            </button>
          ) : null}
        </div>
      ) : null}

      {drawerKind ? (
        <DeliverableDrawer
          kind={drawerKind}
          title={drawerKind === "body" ? BODY_TITLE : drawerKind === "evidence" ? EVIDENCE_TITLE : VERSIONS_TITLE}
          body={body}
          versions={versions}
          evidenceRefs={evidenceRefs}
          latestVersion={latestVersion}
          onClose={() => setDrawerKind(null)}
        />
      ) : null}
    </section>
  );
}

function PanelButton(props: { label: string; meta: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="border border-[#333333] px-4 py-3 text-left transition hover:border-[#555555] hover:bg-white/[0.02]"
    >
      <div className="text-sm font-medium text-zinc-100">{props.label}</div>
      <div className="mt-1 text-xs text-zinc-500">{props.meta}</div>
    </button>
  );
}

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-2 break-words text-sm text-zinc-100">{props.value}</div>
    </div>
  );
}

function DeliverableDrawer(props: {
  kind: DrawerKind;
  title: string;
  body: string;
  versions: DeliverableVersion[];
  evidenceRefs: DeliverableEvidenceRef[];
  latestVersion: DeliverableVersion | null;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 px-4 py-6 sm:items-center">
      <section
        className="max-h-[86vh] w-full max-w-4xl overflow-hidden border border-[#333333] bg-[#161616] shadow-2xl"
        data-testid={`deliverable-${props.kind}-drawer`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-[#333333] px-5 py-4">
          <div>
            <h4 className="text-lg font-semibold text-zinc-100">{props.title}</h4>
            {props.latestVersion ? (
              <p className="mt-1 text-xs text-zinc-500">
                v{props.latestVersion.version_no} · {formatDateTime(props.latestVersion.created_at)}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={props.onClose}
            className="rounded border border-[#4a4a4a] px-3 py-2 text-sm text-zinc-100 transition hover:bg-[#292929]"
          >
            {CLOSE}
          </button>
        </header>

        <div className="max-h-[72vh] overflow-auto px-5 py-5">
          {props.kind === "body" ? <BodyContent body={props.body} /> : null}
          {props.kind === "evidence" ? <EvidenceContent refs={props.evidenceRefs} /> : null}
          {props.kind === "versions" ? <VersionContent versions={props.versions} /> : null}
        </div>
      </section>
    </div>
  );
}

function BodyContent(props: { body: string }) {
  if (!props.body) {
    return <p className="text-sm leading-6 text-zinc-400">{NO_BODY}</p>;
  }

  return (
    <pre className="whitespace-pre-wrap break-words text-sm leading-7 text-zinc-200">
      {props.body}
    </pre>
  );
}

function EvidenceContent(props: { refs: DeliverableEvidenceRef[] }) {
  if (!props.refs.length) {
    return <p className="text-sm leading-6 text-zinc-400">{NO_EVIDENCE}</p>;
  }

  return (
    <div className="space-y-3">
      {props.refs.map((ref, index) => (
        <div key={`${index}-${String(ref.ref ?? ref.label ?? "evidence")}`} className="border border-[#333333] px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={String(ref.kind ?? "evidence")} tone="info" />
            <span className="text-sm font-medium text-zinc-100">
              {String(ref.label ?? ref.ref ?? `#${index + 1}`)}
            </span>
          </div>
          {ref.url ? (
            <a className="mt-2 block break-all text-sm text-zinc-300 underline underline-offset-4" href={String(ref.url)} target="_blank" rel="noreferrer">
              {String(ref.url)}
            </a>
          ) : null}
          <code className="mt-3 block whitespace-pre-wrap break-words text-xs leading-5 text-zinc-500">
            {JSON.stringify(ref, null, 2)}
          </code>
        </div>
      ))}
    </div>
  );
}

function VersionContent(props: { versions: DeliverableVersion[] }) {
  const versions = useMemo(
    () => [...props.versions].sort((a, b) => b.version_no - a.version_no),
    [props.versions],
  );

  if (!versions.length) {
    return <p className="text-sm leading-6 text-zinc-400">{NO_BODY}</p>;
  }

  return (
    <div className="divide-y divide-[#333333] border-y border-[#333333]">
      {versions.map((version) => (
        <article key={version.id} className="py-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={`v${version.version_no}`} tone="success" />
            <StatusBadge
              label={DELIVERABLE_CONTENT_FORMAT_LABELS[version.content_format] ?? version.content_format}
              tone="neutral"
            />
            <span className="text-xs text-zinc-500">{formatDateTime(version.created_at)}</span>
          </div>
          <p className="mt-3 text-sm leading-6 text-zinc-300">{version.summary}</p>
          {(version.task_id || version.run_id) ? (
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-500">
              {version.task_id ? <span>task {version.task_id}</span> : null}
              {version.run_id ? <span>run {version.run_id}</span> : null}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}
