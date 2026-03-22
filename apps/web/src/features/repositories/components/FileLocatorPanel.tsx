import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ProjectDetailTaskItem } from "../../projects/types";
import {
  useBuildProjectCodeContextPack,
  useProjectFileLocatorSearch,
} from "../hooks";
import type {
  CodeContextPack,
  FileLocatorCandidate,
  FileLocatorResult,
} from "../types";

type FileLocatorPanelProps = {
  projectId: string | null;
  workspaceRootPath: string;
  tasks: ProjectDetailTaskItem[];
};

const DEFAULT_LOCATOR_LIMIT = 12;
const DEFAULT_CONTEXT_MAX_TOTAL_BYTES = 12_000;
const DEFAULT_CONTEXT_MAX_BYTES_PER_FILE = 4_000;

export function FileLocatorPanel(props: FileLocatorPanelProps) {
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [pathPrefixesInput, setPathPrefixesInput] = useState("");
  const [moduleNamesInput, setModuleNamesInput] = useState("");
  const [fileTypesInput, setFileTypesInput] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LOCATOR_LIMIT);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [maxTotalBytes, setMaxTotalBytes] = useState(
    DEFAULT_CONTEXT_MAX_TOTAL_BYTES,
  );
  const [maxBytesPerFile, setMaxBytesPerFile] = useState(
    DEFAULT_CONTEXT_MAX_BYTES_PER_FILE,
  );

  const fileLocatorSearchMutation = useProjectFileLocatorSearch(props.projectId);
  const codeContextPackMutation = useBuildProjectCodeContextPack(props.projectId);
  const locatorResult = fileLocatorSearchMutation.data ?? null;
  const codeContextPack = codeContextPackMutation.data ?? null;

  const parsedKeywords = useMemo(() => parseListInput(keywordsInput), [keywordsInput]);
  const parsedPathPrefixes = useMemo(
    () => parseListInput(pathPrefixesInput),
    [pathPrefixesInput],
  );
  const parsedModuleNames = useMemo(
    () => parseListInput(moduleNamesInput),
    [moduleNamesInput],
  );
  const parsedFileTypes = useMemo(
    () => parseListInput(fileTypesInput),
    [fileTypesInput],
  );

  const hasLocatorSignals = Boolean(
    selectedTaskId ||
      taskQuery.trim() ||
      parsedKeywords.length ||
      parsedPathPrefixes.length ||
      parsedModuleNames.length ||
      parsedFileTypes.length,
  );

  useEffect(() => {
    if (!props.tasks.length || !selectedTaskId) {
      return;
    }

    if (!props.tasks.some((task) => task.id === selectedTaskId)) {
      setSelectedTaskId("");
    }
  }, [props.tasks, selectedTaskId]);

  useEffect(() => {
    if (!locatorResult) {
      return;
    }

    setSelectedPaths(
      locatorResult.candidates
        .slice(0, Math.min(3, locatorResult.candidates.length))
        .map((candidate) => candidate.relative_path),
    );
  }, [locatorResult]);

  const handleSearch = async () => {
    if (!hasLocatorSignals) {
      return;
    }

    codeContextPackMutation.reset();
    try {
      const result = await fileLocatorSearchMutation.mutateAsync({
        task_id: selectedTaskId || null,
        task_query: taskQuery.trim() || null,
        keywords: parsedKeywords,
        path_prefixes: parsedPathPrefixes,
        module_names: parsedModuleNames,
        file_types: parsedFileTypes,
        limit,
      });
      setSelectedPaths(
        result.candidates
          .slice(0, Math.min(3, result.candidates.length))
          .map((candidate) => candidate.relative_path),
      );
    } catch {
      setSelectedPaths([]);
    }
  };

  const handleBuildContextPack = async () => {
    if (!locatorResult || !selectedPaths.length) {
      return;
    }

    await codeContextPackMutation.mutateAsync({
      task_id: locatorResult.query.task_id,
      task_query: locatorResult.query.task_query,
      keywords: locatorResult.query.keywords,
      path_prefixes: locatorResult.query.path_prefixes,
      module_names: locatorResult.query.module_names,
      file_types: locatorResult.query.file_types,
      selected_paths: selectedPaths,
      max_total_bytes: maxTotalBytes,
      max_bytes_per_file: maxBytesPerFile,
      selection_reasons_by_path: buildSelectionReasonMap(locatorResult.candidates),
    });
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Day05 文件定位索引
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            这里先把任务或规划摘要落到候选文件集合，再由你选择需要进入{" "}
            <code>CodeContextPack</code> 的最小文件片段。当前只做文件定位与上下文包，
            不生成 Day06 变更计划草案，也不触发任何真实 Git 写操作。
          </p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-xs leading-6 text-slate-400">
          <div>仓库根：{props.workspaceRootPath}</div>
          <div>已有任务：{props.tasks.length} 个</div>
          <div>默认上文包预算：{DEFAULT_CONTEXT_MAX_TOTAL_BYTES} bytes</div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
              绑定项目任务
            </span>
            <select
              value={selectedTaskId}
              onChange={(event) => setSelectedTaskId(event.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
            >
              <option value="">不绑定任务，使用手动过滤</option>
              {props.tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
              候选上限
            </span>
            <input
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(event) =>
                setLimit(clampNumber(Number(event.target.value) || DEFAULT_LOCATOR_LIMIT, 1, 50))
              }
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
            />
          </label>

          <label className="space-y-2 md:col-span-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
              规划摘要 / 补充说明
            </span>
            <textarea
              value={taskQuery}
              onChange={(event) => setTaskQuery(event.target.value)}
              rows={4}
              className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-500"
              placeholder="用于还没落成任务的规划摘要，例如：定位 repositories 路由、服务层和前端面板的最小相关文件。"
            />
          </label>

          <FilterInput
            label="关键词"
            value={keywordsInput}
            onChange={setKeywordsInput}
            placeholder="例如 locator, context pack, repositories"
          />
          <FilterInput
            label="路径前缀"
            value={pathPrefixesInput}
            onChange={setPathPrefixesInput}
            placeholder="例如 runtime/orchestrator/app/services"
          />
          <FilterInput
            label="模块名"
            value={moduleNamesInput}
            onChange={setModuleNamesInput}
            placeholder="例如 repositories, services, components"
          />
          <FilterInput
            label="文件类型"
            value={fileTypesInput}
            onChange={setFileTypesInput}
            placeholder="例如 py, tsx, md, yaml"
          />
        </div>

        <aside className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              当前过滤摘要
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedTaskId ? (
                <StatusBadge label="已绑定任务" tone="info" />
              ) : null}
              {parsedKeywords.map((item) => (
                <StatusBadge key={`keyword-${item}`} label={`关键词 ${item}`} tone="neutral" />
              ))}
              {parsedPathPrefixes.map((item) => (
                <StatusBadge key={`path-${item}`} label={`路径 ${item}`} tone="info" />
              ))}
              {parsedModuleNames.map((item) => (
                <StatusBadge key={`module-${item}`} label={`模块 ${item}`} tone="success" />
              ))}
              {parsedFileTypes.map((item) => (
                <StatusBadge key={`type-${item}`} label={`类型 ${item}`} tone="warning" />
              ))}
              {!hasLocatorSignals ? (
                <div className="text-sm leading-6 text-slate-400">
                  先选择任务，或至少填写一项过滤条件。
                </div>
              ) : null}
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              void handleSearch();
            }}
            disabled={!hasLocatorSignals || fileLocatorSearchMutation.isPending}
            className={`inline-flex w-full items-center justify-center rounded-xl border px-4 py-2 text-sm font-medium transition ${
              !hasLocatorSignals || fileLocatorSearchMutation.isPending
                ? "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-500"
                : "border-cyan-500/30 bg-cyan-500/10 text-cyan-100 hover:border-cyan-400/50 hover:bg-cyan-500/20"
            }`}
          >
            {fileLocatorSearchMutation.isPending ? "正在定位候选文件..." : "生成候选文件集合"}
          </button>

          <div className="text-xs leading-6 text-slate-500">
            默认排除 <code>.git</code>、<code>.venv</code>、<code>node_modules</code>、
            <code>dist</code>、<code>build</code> 等噪声目录，并跳过超大或明显二进制文件。
          </div>
        </aside>
      </div>

      {fileLocatorSearchMutation.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          文件定位失败：{fileLocatorSearchMutation.error.message}
        </div>
      ) : null}

      {locatorResult ? (
        <div className="mt-4 space-y-4">
          <LocatorSummaryCard result={locatorResult} />

          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  候选文件列表
                </div>
                <div className="mt-2 text-sm leading-6 text-slate-300">
                  当前已选 {selectedPaths.length} / {locatorResult.candidates.length} 个文件进入
                  上下文包。
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setSelectedPaths(
                      locatorResult.candidates
                        .slice(0, Math.min(3, locatorResult.candidates.length))
                        .map((candidate) => candidate.relative_path),
                    )
                  }
                  className="rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-cyan-500 hover:text-cyan-100"
                >
                  选前 3 个
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setSelectedPaths(
                      locatorResult.candidates.map((candidate) => candidate.relative_path),
                    )
                  }
                  className="rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-cyan-500 hover:text-cyan-100"
                >
                  全选当前候选
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPaths([])}
                  className="rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-rose-400/50 hover:text-rose-100"
                >
                  清空选择
                </button>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {locatorResult.candidates.map((candidate) => (
                <CandidateRow
                  key={candidate.relative_path}
                  candidate={candidate}
                  selected={selectedPaths.includes(candidate.relative_path)}
                  onToggle={() =>
                    setSelectedPaths((currentSelection) =>
                      currentSelection.includes(candidate.relative_path)
                        ? currentSelection.filter((item) => item !== candidate.relative_path)
                        : [...currentSelection, candidate.relative_path],
                    )
                  }
                />
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    上下文包总预算（bytes）
                  </span>
                  <input
                    type="number"
                    min={512}
                    max={80_000}
                    value={maxTotalBytes}
                    onChange={(event) =>
                      setMaxTotalBytes(
                        clampNumber(Number(event.target.value) || DEFAULT_CONTEXT_MAX_TOTAL_BYTES, 512, 80_000),
                      )
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                  />
                </label>

                <label className="space-y-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    单文件预算（bytes）
                  </span>
                  <input
                    type="number"
                    min={256}
                    max={20_000}
                    value={maxBytesPerFile}
                    onChange={(event) =>
                      setMaxBytesPerFile(
                        clampNumber(Number(event.target.value) || DEFAULT_CONTEXT_MAX_BYTES_PER_FILE, 256, 20_000),
                      )
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
                  />
                </label>
              </div>

              <button
                type="button"
                onClick={() => {
                  void handleBuildContextPack();
                }}
                disabled={!selectedPaths.length || codeContextPackMutation.isPending}
                className={`inline-flex items-center justify-center rounded-xl border px-4 py-2 text-sm font-medium transition ${
                  !selectedPaths.length || codeContextPackMutation.isPending
                    ? "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-500"
                    : "border-emerald-500/30 bg-emerald-500/10 text-emerald-100 hover:border-emerald-400/50 hover:bg-emerald-500/20"
                }`}
              >
                {codeContextPackMutation.isPending
                  ? "正在生成 CodeContextPack..."
                  : "生成 CodeContextPack"}
              </button>
            </div>

            <div className="mt-3 text-xs leading-6 text-slate-500">
              Day05 只保留最小可控上下文，供后续 Day06 输入使用；当前不会生成任何具体改动方案。
            </div>
          </div>
        </div>
      ) : null}

      {codeContextPackMutation.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          上下文包生成失败：{codeContextPackMutation.error.message}
        </div>
      ) : null}

      {codeContextPack ? <CodeContextPackCard pack={codeContextPack} /> : null}
    </section>
  );
}

function FilterInput(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="space-y-2">
      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </span>
      <input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
        placeholder={props.placeholder}
      />
    </label>
  );
}

function LocatorSummaryCard(props: { result: FileLocatorResult }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            定位结果摘要
          </div>
          <div className="mt-2 text-sm leading-6 text-slate-200">
            {props.result.query.summary}
          </div>
          <div className="mt-2 text-xs leading-6 text-slate-500">
            生成时间：{formatDateTime(props.result.generated_at)}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`候选 ${props.result.candidate_count}`}
            tone="info"
          />
          <StatusBadge
            label={`总命中 ${props.result.total_match_count}`}
            tone={props.result.truncated ? "warning" : "success"}
          />
          <StatusBadge
            label={`扫描文本文件 ${props.result.scanned_file_count}`}
            tone="neutral"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {props.result.ignored_directory_names.map((item) => (
          <StatusBadge key={item} label={`忽略 ${item}`} tone="neutral" />
        ))}
      </div>

      {props.result.truncated ? (
        <div className="mt-3 text-sm leading-6 text-amber-200">
          当前命中结果已按上限裁剪，仅保留得分最高的候选文件。
        </div>
      ) : null}
    </div>
  );
}

function CandidateRow(props: {
  candidate: FileLocatorCandidate;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="block cursor-pointer rounded-2xl border border-slate-800 bg-slate-900/60 p-4 transition hover:border-cyan-500/40">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={props.selected}
            onChange={props.onToggle}
            className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400 focus:ring-cyan-500"
          />
          <div>
            <div className="break-all text-sm font-medium text-slate-100">
              {props.candidate.relative_path}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <StatusBadge label={`Score ${props.candidate.score}`} tone="info" />
              <StatusBadge label={props.candidate.language} tone="success" />
              <StatusBadge label={props.candidate.file_type} tone="warning" />
              <StatusBadge
                label={`${props.candidate.line_count} lines`}
                tone="neutral"
              />
              <StatusBadge
                label={formatBytes(props.candidate.byte_size)}
                tone="neutral"
              />
            </div>
          </div>
        </div>

        {props.selected ? <StatusBadge label="已入选" tone="success" /> : null}
      </div>

      {props.candidate.preview ? (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-3 text-sm leading-6 text-slate-300">
          {props.candidate.preview}
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {props.candidate.match_reasons.map((reason) => (
          <StatusBadge key={`${props.candidate.relative_path}-${reason}`} label={reason} tone={mapReasonTone(reason)} />
        ))}
      </div>
    </label>
  );
}

function CodeContextPackCard(props: { pack: CodeContextPack }) {
  return (
    <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            CodeContextPack
          </div>
          <div className="mt-2 text-sm leading-6 text-slate-200">
            {props.pack.source_summary}
          </div>
          <div className="mt-2 text-xs leading-6 text-slate-500">
            生成时间：{formatDateTime(props.pack.generated_at)}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`文件 ${props.pack.included_file_count}`}
            tone="success"
          />
          <StatusBadge
            label={`已收录 ${formatBytes(props.pack.total_included_bytes)}`}
            tone="info"
          />
          <StatusBadge
            label={`预算 ${formatBytes(props.pack.max_total_bytes)}`}
            tone="neutral"
          />
          <StatusBadge
            label={props.pack.truncated ? "已裁剪" : "未裁剪"}
            tone={props.pack.truncated ? "warning" : "success"}
          />
        </div>
      </div>

      {props.pack.focus_terms.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {props.pack.focus_terms.map((term) => (
            <StatusBadge key={term} label={`焦点 ${term}`} tone="neutral" />
          ))}
        </div>
      ) : null}

      {props.pack.omitted_paths.length > 0 ? (
        <div className="mt-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-100">
          由于预算上限，以下文件未进入上下文包：
          <div className="mt-2 flex flex-wrap gap-2">
            {props.pack.omitted_paths.map((item) => (
              <StatusBadge key={item} label={item} tone="warning" />
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 space-y-4">
        {props.pack.entries.map((entry) => (
          <div
            key={entry.relative_path}
            className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="break-all text-sm font-medium text-slate-100">
                  {entry.relative_path}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <StatusBadge label={entry.language} tone="success" />
                  <StatusBadge label={entry.file_type} tone="warning" />
                  <StatusBadge
                    label={`${entry.start_line}-${entry.end_line}`}
                    tone="info"
                  />
                  <StatusBadge
                    label={`片段 ${formatBytes(entry.included_bytes)}`}
                    tone="neutral"
                  />
                  <StatusBadge
                    label={entry.truncated ? "已裁剪" : "完整片段"}
                    tone={entry.truncated ? "warning" : "success"}
                  />
                </div>
              </div>

              {entry.match_reasons.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {entry.match_reasons.map((reason) => (
                    <StatusBadge key={`${entry.relative_path}-${reason}`} label={reason} tone={mapReasonTone(reason)} />
                  ))}
                </div>
              ) : null}
            </div>

            <pre className="mt-3 overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-4 whitespace-pre-wrap break-all text-xs leading-6 text-slate-200">
              {entry.excerpt || "(empty file)"}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildSelectionReasonMap(candidates: FileLocatorCandidate[]) {
  return Object.fromEntries(
    candidates.map((candidate) => [candidate.relative_path, candidate.match_reasons]),
  );
}

function parseListInput(value: string) {
  const segments = value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

  return Array.from(new Set(segments));
}

function clampNumber(value: number, min: number, max: number) {
  if (Number.isNaN(value)) {
    return min;
  }

  return Math.min(max, Math.max(min, value));
}

function formatBytes(value: number) {
  if (value >= 1024) {
    return `${(value / 1024).toFixed(value >= 10 * 1024 ? 0 : 1)} KB`;
  }

  return `${value} B`;
}

function mapReasonTone(reason: string): "neutral" | "info" | "success" | "warning" {
  if (reason.startsWith("路径前缀") || reason.startsWith("路径命中")) {
    return "info";
  }
  if (reason.startsWith("模块") || reason.startsWith("文件名/模块")) {
    return "success";
  }
  if (reason.startsWith("文件类型")) {
    return "warning";
  }

  return "neutral";
}
