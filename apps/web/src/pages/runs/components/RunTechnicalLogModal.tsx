import { useState, useCallback } from "react";
import type { TechnicalLogData, TechnicalLogSection } from "../lib/runTechnicalLog";

type RunTechnicalLogModalProps = {
  open: boolean;
  onClose: () => void;
  log: TechnicalLogData | null;
};

export function RunTechnicalLogModal({ open, onClose, log }: RunTechnicalLogModalProps) {
  const [activeSection, setActiveSection] = useState<string>("status-overview");
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedId, setCopiedId] = useState(false);

  const handleCopyAll = useCallback(async () => {
    if (!log) return;
    try {
      await navigator.clipboard.writeText(log.rawText);
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    } catch {}
  }, [log]);

  const handleCopyRunId = useCallback(async () => {
    if (!log) return;
    try {
      await navigator.clipboard.writeText(log.runId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch {}
  }, [log]);

  if (!open || !log) return null;

  return (
    <div
      data-testid="run-technical-log-modal"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      {/* backdrop */}
      <div
        data-testid="run-technical-log-modal-backdrop"
        className="absolute inset-0 bg-black/70"
        onClick={onClose}
      />

      {/* modal panel */}
      <div
        className="relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-lg border border-[#333333] bg-[#0c0c0c] shadow-2xl"
      >
        {/* ── Header ────────────────────────────────────────── */}
        <div className="shrink-0 border-b border-[#333333] px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-base font-semibold text-zinc-100">
                技术日志 · 运行详情
              </h2>
              <p className="mt-1 truncate text-sm text-zinc-400">
                任务：{log.taskTitle}
              </p>
              <p className="mt-0.5 truncate font-mono text-xs text-zinc-500">
                运行 ID：{log.runId}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                data-testid="copy-all-tech-log"
                onClick={handleCopyAll}
                className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-500 hover:bg-[#292929]"
              >
                {copiedAll ? "已复制" : "复制全部"}
              </button>
              <button
                type="button"
                data-testid="copy-run-id-tech-log"
                onClick={handleCopyRunId}
                className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-100"
              >
                {copiedId ? "已复制" : "复制运行 ID"}
              </button>
              <button
                type="button"
                data-testid="close-tech-log-modal"
                onClick={onClose}
                className="rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-100"
              >
                关闭
              </button>
            </div>
          </div>

          {/* section tabs */}
          <nav className="mt-3 flex flex-wrap gap-1">
            {log.sections.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => setActiveSection(section.id)}
                className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                  activeSection === section.id
                    ? "bg-zinc-700 text-zinc-100"
                    : "text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                }`}
              >
                {section.title}
              </button>
            ))}
          </nav>
        </div>

        {/* ── Body ───────────────────────────────────────────── */}
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {log.sections
            .filter((s) => s.id === activeSection)
            .map((section) => (
              <LogSectionView key={section.id} section={section} />
            ))}
        </div>
      </div>
    </div>
  );
}

function LogSectionView({ section }: { section: TechnicalLogSection }) {
  const [copiedSection, setCopiedSection] = useState(false);

  const handleCopySection = useCallback(async () => {
    let text = `--- ${section.title} ---\n`;
    for (const f of section.fields) {
      text += `${f.label}：${f.value}\n`;
    }
    if (section.content) {
      text += `\n${section.content}\n`;
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(true);
      setTimeout(() => setCopiedSection(false), 2000);
    } catch {}
  }, [section]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">{section.title}</h3>
        <button
          type="button"
          onClick={handleCopySection}
          className="text-xs text-zinc-500 transition hover:text-zinc-200"
        >
          {copiedSection ? "已复制" : "复制本段"}
        </button>
      </div>

      {/* field grid */}
      {section.fields.length > 0 ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          {section.fields.map((f, i) => (
            <div
              key={i}
              className="min-w-0 border-l border-[#333333] px-3 py-2"
            >
              <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">
                {f.label}
              </div>
              <div
                className={`mt-1 text-sm text-zinc-100 ${
                  f.mono ? "font-mono" : ""
                } ${f.long ? "break-all" : "truncate"}`}
                title={f.value}
              >
                {f.value}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {/* free text content */}
      {section.content ? (
        <div className="rounded border border-[#333333] bg-[#0a0a0a] p-3">
          <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-6 text-zinc-400 max-h-96 overflow-y-auto">
            {section.content}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
