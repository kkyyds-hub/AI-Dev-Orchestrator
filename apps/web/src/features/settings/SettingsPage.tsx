import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatusBadge } from "../../components/StatusBadge";
import { requestJson } from "../../lib/http";
import { formatDateTime } from "../../lib/format";
import { useBossProjectOverview } from "../projects/hooks";
import { buildProjectOverviewRoute } from "../projects/lib/overviewNavigation";
import type { RepositoryWorkspace } from "../projects/types";
import { PROJECT_STAGE_LABELS } from "../projects/types";

/* ─── types ─── */

type ProviderSource = "saved_config" | "env" | "none";
type ProviderModelPreset = "openai" | "deepseek" | "custom";
type ProviderType = "openai" | "deepseek" | "openai_compatible";
type TierModelNames = { economy: string; balanced: string; premium: string };

type ProviderSettingsSummary = {
  provider_key: string; configured: boolean; masked_api_key?: string | null;
  base_url: string; timeout_seconds: number; source: ProviderSource;
  detected_provider_type: ProviderType; model_preset: ProviderModelPreset;
  model_names: TierModelNames;
};

type ProviderTestResponse = {
  provider_key: string; configured: boolean; base_url: string;
  auth_valid: boolean; endpoint_reachable: boolean;
  api_family: string; model_name: string; model_usable: boolean;
  latency_ms: number; status: string; error_category: string | null;
  error_summary: string | null; tested_at: string | null;
};

type ProviderUpdateRequest = {
  api_key?: string; base_url: string; timeout_seconds: number;
  model_preset?: ProviderModelPreset; model_names?: TierModelNames;
};

type WorkspaceSettings = {
  allowed_workspace_roots: string[]; default_workspace_root: string; using_default: boolean;
};

type WorkspaceSettingsUpdate = { allowed_workspace_roots: string[] };

type WorkspaceBindRequest = {
  root_path: string; display_name?: string | null;
  access_mode: "read_only"; default_base_branch: string; ignore_rule_summary: string[];
};

type HealthStatus = { status: string; detail?: string };

/* ─── API ─── */

function fetchProvider(): Promise<ProviderSettingsSummary> {
  return requestJson("/provider-settings/openai");
}
function updateProvider(payload: ProviderUpdateRequest): Promise<ProviderSettingsSummary> {
  return requestJson("/provider-settings/openai", { method: "PUT", body: JSON.stringify(payload) });
}
function testProviderConnection(): Promise<ProviderTestResponse> {
  return requestJson("/provider-settings/openai/test", { method: "POST" });
}
function fetchHealth(): Promise<HealthStatus> {
  return requestJson("/health");
}
function fetchWorkspaceSettings(): Promise<WorkspaceSettings> {
  return requestJson("/repositories/workspace-settings");
}
function updateWorkspaceSettings(payload: WorkspaceSettingsUpdate): Promise<WorkspaceSettings> {
  return requestJson("/repositories/workspace-settings", { method: "PUT", body: JSON.stringify(payload) });
}
function bindProjectRepo(input: { projectId: string; payload: WorkspaceBindRequest }): Promise<RepositoryWorkspace> {
  return requestJson(`/repositories/projects/${input.projectId}`, { method: "PUT", body: JSON.stringify(input.payload) });
}

/* ─── constants ─── */

const PRESET_MODELS: Record<Exclude<ProviderModelPreset, "custom">, TierModelNames> = {
  deepseek: { economy: "deepseek-v4-pro", balanced: "deepseek-v4-pro", premium: "deepseek-v4-pro" },
  openai: { economy: "gpt-5.5", balanced: "gpt-5.5", premium: "gpt-5.5" },
};

const PRESET_LABELS: Record<ProviderModelPreset, string> = {
  deepseek: "DeepSeek", openai: "OpenAI", custom: "自定义",
};
const SOURCE_LABELS: Record<ProviderSource, string> = {
  saved_config: "已保存", env: "环境变量", none: "未配置",
};

const inputClass = "w-full border border-[#333333] bg-[#111111] px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500 rounded";
const btnClass = "rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600";
const btnPrimaryClass = "rounded border border-zinc-400 px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600";

/* ═══════════ Page ═══════════ */

export function SettingsPage() {
  return (
    <div className="relative min-w-0 space-y-6">
      <header className="border-b border-[#333333] pb-5">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">系统配置中心</h1>
        <p className="mt-1 text-sm text-zinc-500">Provider 连接、运行环境、安全边界与系统诊断</p>
      </header>

      {/* 当前访问状态摘要 */}
      <div className="rounded border border-[#333333] px-4 py-3 text-xs text-zinc-500">
        <span className="text-zinc-300">当前状态：直接访问</span>
        <span className="mx-2 text-zinc-700">|</span>
        账号登录尚未开放
        <span className="mx-2 text-zinc-700">|</span>
        账户体系待后端接入
        <span className="ml-2 text-zinc-600">— 系统级配置请使用下方四个区块</span>
      </div>

      <div className="space-y-8">
        <ProviderSection />
        <EnvironmentSection />
        <SecuritySection />
        <DiagnosticsSection />
      </div>
    </div>
  );
}

/* ═══════════ Section 1: Provider ═══════════ */

function ProviderSection() {
  return (
    <section className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-5 space-y-5">
      <SectionHeader title="Provider 与模型" desc="管理 AI 模型连接的 API 凭证、Base URL、超时与模型名配置" />
      <ProviderStatus />
      <ProviderEdit />
      <ProviderTest />
    </section>
  );
}

function ProviderStatus() {
  const q = useQuery({ queryKey: ["provider-settings", "openai"], queryFn: fetchProvider });
  const s = q.data;
  if (q.isLoading) return <p className="text-xs text-zinc-600">加载 Provider 配置...</p>;
  if (q.isError) return <p className="text-xs text-red-400">加载失败：{q.error.message}</p>;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatItem label="配置状态" value={s?.configured ? "已配置" : "未配置"} />
      <StatItem label="来源" value={s ? SOURCE_LABELS[s.source] : "未知"} />
      <StatItem label="检测到类型" value={s?.detected_provider_type ?? "—"} />
      <StatItem label="API Key" value={s?.masked_api_key || "未设置"} />
      <StatItem label="Base URL" value={s?.base_url ? truncateUrl(s.base_url) : "—"} />
      <StatItem label="超时" value={`${s?.timeout_seconds ?? 30} 秒`} />
      <StatItem label="预设" value={s ? PRESET_LABELS[s.model_preset] : "—"} />
      <StatItem label="模型等级" value={s ? `${s.model_names.economy} / ${s.model_names.balanced} / ${s.model_names.premium}` : "—"} />
    </div>
  );
}

function ProviderEdit() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["provider-settings", "openai"], queryFn: fetchProvider });
  const [expanded, setExpanded] = useState(false);
  const [secret, setSecret] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [timeoutSec, setTimeoutSec] = useState("30");
  const [preset, setPreset] = useState<ProviderModelPreset>("openai");
  const [models, setModels] = useState<TierModelNames>(PRESET_MODELS.openai);
  const [fb, setFb] = useState<string | null>(null);

  useEffect(() => {
    if (!q.data) return;
    setBaseUrl(q.data.base_url);
    setTimeoutSec(String(q.data.timeout_seconds));
    setPreset(q.data.model_preset);
    setModels(q.data.model_names);
  }, [q.data]);

  const m = useMutation({
    mutationFn: updateProvider,
    onSuccess: async (r) => {
      setSecret(""); setBaseUrl(r.base_url); setTimeoutSec(String(r.timeout_seconds));
      setPreset(r.model_preset); setModels(r.model_names);
      setFb("保存成功。"); await qc.invalidateQueries({ queryKey: ["provider-settings", "openai"] });
    },
  });

  const applyPreset = (p: Exclude<ProviderModelPreset, "custom">) => {
    setPreset(p); setModels(PRESET_MODELS[p]);
    setBaseUrl(p === "deepseek" ? "https://api.deepseek.com" : "https://api.openai.com/v1");
  };

  const canSave = !m.isPending && baseUrl.trim() && timeoutSec.trim() && Object.values(models).every((v) => v.trim());

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault(); setFb(null);
    const t = Number.parseInt(timeoutSec, 10);
    if (!Number.isFinite(t) || t < 1) { setFb("超时秒数必须是大于等于 1 的整数。"); return; }
    const p: ProviderUpdateRequest = { base_url: baseUrl.trim(), timeout_seconds: t, model_preset: preset };
    if (preset === "custom") p.model_names = { economy: models.economy.trim(), balanced: models.balanced.trim(), premium: models.premium.trim() };
    if (secret.trim()) p.api_key = secret.trim();
    void m.mutateAsync(p);
  };

  return (
    <div>
      <button type="button" onClick={() => setExpanded((v) => !v)} className={`${btnClass}`}>
        {expanded ? "收起编辑区" : "编辑 Provider 配置"}
      </button>
      {expanded && (
        <form className="mt-4 space-y-4 border-t border-[#333333] pt-4" onSubmit={handleSubmit}>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={btnClass} onClick={() => applyPreset("deepseek")}>DeepSeek 预设</button>
            <button type="button" className={btnClass} onClick={() => applyPreset("openai")}>OpenAI 预设</button>
            <span className="text-xs text-zinc-500 self-center">当前：{PRESET_LABELS[preset]}</span>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FieldL label="API Key"><input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="留空保留当前 Key" className={inputClass} /></FieldL>
            <FieldL label="超时（秒）"><input type="number" min={1} step={1} value={timeoutSec} onChange={(e) => setTimeoutSec(e.target.value)} className={inputClass} /></FieldL>
          </div>
          <FieldL label="Base URL"><input type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className={inputClass} /></FieldL>
          <div className="grid gap-4 md:grid-cols-3">
            <FieldL label="经济模型"><input value={models.economy} onChange={(e) => { setPreset("custom"); setModels((c) => ({ ...c, economy: e.target.value })); }} className={inputClass} /></FieldL>
            <FieldL label="平衡模型"><input value={models.balanced} onChange={(e) => { setPreset("custom"); setModels((c) => ({ ...c, balanced: e.target.value })); }} className={inputClass} /></FieldL>
            <FieldL label="高级模型"><input value={models.premium} onChange={(e) => { setPreset("custom"); setModels((c) => ({ ...c, premium: e.target.value })); }} className={inputClass} /></FieldL>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={!canSave} className={btnPrimaryClass}>{m.isPending ? "保存中..." : "保存配置"}</button>
            {fb && <span className="text-xs text-zinc-400">{fb}</span>}
            {m.isError && <span className="text-xs text-red-400">保存失败：{m.error.message}</span>}
          </div>
        </form>
      )}
    </div>
  );
}

function ProviderTest() {
  const [result, setResult] = useState<ProviderTestResponse | null>(null);
  const m = useMutation({
    mutationFn: testProviderConnection,
    onSuccess: (r) => setResult(r),
  });

  return (
    <div className="border-t border-[#333333] pt-4 space-y-3">
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => m.mutate()} disabled={m.isPending} className={btnClass}>
          {m.isPending ? "测试中..." : "测试连接"}
        </button>
        {m.isError && <span className="text-xs text-red-400">{m.error.message}</span>}
      </div>
      {result && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <TestStat label="状态" value={result.status} tone={result.status === "ok" ? "ok" : "warn"} />
          <TestStat label="已配置" value={result.configured ? "是" : "否"} />
          <TestStat label="认证有效" value={result.auth_valid ? "是" : "否"} tone={result.auth_valid ? "ok" : "warn"} />
          <TestStat label="端点可达" value={result.endpoint_reachable ? "是" : "否"} tone={result.endpoint_reachable ? "ok" : "warn"} />
          <TestStat label="模型可用" value={result.model_usable ? "是" : "否"} tone={result.model_usable ? "ok" : "warn"} />
          <TestStat label="延迟" value={`${result.latency_ms}ms`} />
          <TestStat label="API 类型" value={result.api_family} />
          <TestStat label="测试模型" value={result.model_name} />
          {result.error_summary && (
            <div className="col-span-full text-xs text-red-400 truncate" title={result.error_summary}>
              错误：{result.error_summary}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ═══════════ Section 2: Environment ═══════════ */

function EnvironmentSection() {
  const hq = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const h = hq.data;

  return (
    <section className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-5 space-y-4">
      <SectionHeader title="运行环境" desc="后端健康状态、数据库、Worker、Event Stream 基础检查" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatItem label="后端状态" value={hq.isLoading ? "加载中..." : h ? "在线" : "未知"} />
        <StatItem label="数据库" value="暂无专用诊断接口" />
        <StatItem label="Worker" value="暂无专用诊断接口" />
        <StatItem label="Event Stream" value="暂无专用诊断接口" />
      </div>
      {hq.isError && <p className="text-xs text-red-400">健康检查失败：{hq.error.message}</p>}
      <p className="text-[11px] text-zinc-600">
        数据库、Worker、Event Stream 暂无独立诊断 API。当前仅展示基础健康状态（GET /health）。
        后续后端补齐专用诊断接口后可获得细分状态。页面打开不触发 AI 生成。
      </p>
    </section>
  );
}

/* ═══════════ Section 3: Security ═══════════ */

function SecuritySection() {
  return (
    <section className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-5 space-y-5">
      <SectionHeader title="安全与权限" desc="系统级仓库访问安全边界与项目仓库绑定" />
      <WorkspaceSettingsBox />
      <RepositoryBindingBox />
    </section>
  );
}

function WorkspaceSettingsBox() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["repository-workspace-settings"], queryFn: fetchWorkspaceSettings });
  const [rootsInput, setRootsInput] = useState("");
  const [fb, setFb] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (q.data) setRootsInput(q.data.allowed_workspace_roots.join("\n"));
  }, [q.data]);

  const m = useMutation({
    mutationFn: updateWorkspaceSettings,
    onSuccess: async (r) => {
      setRootsInput(r.allowed_workspace_roots.join("\n"));
      setFb("安全边界已保存。");
      await qc.invalidateQueries({ queryKey: ["repository-workspace-settings"] });
    },
  });

  const s = q.data;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-medium text-zinc-200">仓库安全边界</h3>
        <StatusBadge label={s?.using_default ? "默认边界" : "已配置"} tone={s?.using_default ? "warning" : "success"} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <StatItem label="默认根目录" value={s?.default_workspace_root || "—"} />
        <StatItem label="生效根目录" value={(s?.allowed_workspace_roots ?? []).join("; ") || "—"} />
      </div>
      <p className="text-[11px] text-zinc-600">系统级仓库工作区根目录白名单。项目绑定仓库路径必须位于其中之一。当前 access_mode=read_only，不代表真实 git 写入。</p>
      <button type="button" onClick={() => setExpanded((v) => !v)} className={btnClass}>{expanded ? "收起" : "编辑安全边界"}</button>
      {expanded && (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void m.mutateAsync({ allowed_workspace_roots: parseLines(rootsInput) }); }}>
          <textarea rows={4} value={rootsInput} onChange={(e) => setRootsInput(e.target.value)} placeholder="每行一个本地目录" className={inputClass} />
          <div className="flex items-center gap-3">
            <button type="submit" disabled={m.isPending} className={btnPrimaryClass}>{m.isPending ? "保存中..." : "保存"}</button>
            {fb && <span className="text-xs text-zinc-400">{fb}</span>}
          </div>
        </form>
      )}
    </div>
  );
}

function RepositoryBindingBox() {
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const qc = useQueryClient();
  const oq = useBossProjectOverview({ enablePolling: false });
  const projects = oq.data?.projects ?? [];
  const reqId = sp.get("projectId") ?? "";
  const [pid, setPid] = useState(reqId);
  const sel = projects.find((p) => p.id === pid) ?? null;
  const [rootPath, setRootPath] = useState("");
  const [dispName, setDispName] = useState("");
  const [baseBranch, setBaseBranch] = useState("main");
  const [ignoreRules, setIgnoreRules] = useState(".git\nnode_modules\ndist\nbuild");
  const [fb, setFb] = useState<string | null>(null);

  useEffect(() => {
    if (!sel) return;
    const w = sel.repository_workspace;
    setRootPath(w?.root_path ?? "");
    setDispName(w?.display_name ?? sel.name);
    setBaseBranch(w?.default_base_branch ?? "main");
    setIgnoreRules((w?.ignore_rule_summary.length ? w.ignore_rule_summary : [".git", "node_modules", "dist", "build"]).join("\n"));
  }, [sel]);

  const m = useMutation({
    mutationFn: bindProjectRepo,
    onSuccess: async (w) => {
      setFb("绑定已保存。");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        qc.invalidateQueries({ queryKey: ["project-detail"] }),
        qc.invalidateQueries({ queryKey: ["project-detail", w.project_id] }),
      ]);
      navigate(buildProjectOverviewRoute({ projectId: w.project_id, view: "repository-workspace" }));
    },
  });

  return (
    <div className="border-t border-[#333333] pt-4 space-y-3">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-medium text-zinc-200">项目仓库绑定</h3>
        <StatusBadge label={sel?.repository_workspace ? "已绑定" : "待绑定"} tone={sel?.repository_workspace ? "success" : "warning"} />
      </div>
      <p className="text-[11px] text-zinc-600">为项目绑定主仓库根目录。access_mode=read_only。绑定后可进入仓库工作区查看文件。</p>
      {oq.isLoading ? <p className="text-xs text-zinc-600">加载项目列表...</p> : oq.isError ? <p className="text-xs text-red-400">加载失败</p> : (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (!sel) return; void m.mutateAsync({ projectId: sel.id, payload: { root_path: rootPath.trim(), display_name: dispName.trim() || null, access_mode: "read_only", default_base_branch: baseBranch.trim(), ignore_rule_summary: parseLines(ignoreRules) } }); }}>
          <select value={pid} onChange={(e) => { setPid(e.target.value); setSp((c) => { const n = new URLSearchParams(c); e.target.value ? n.set("projectId", e.target.value) : n.delete("projectId"); return n; }, { replace: true }); }} className={inputClass}>
            <option value="">选择项目</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          {sel && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <StatItem label="当前状态" value={sel.repository_workspace ? "已绑定" : "未绑定"} />
                <StatItem label="阶段" value={PROJECT_STAGE_LABELS[sel.stage] ?? "—"} />
                <StatItem label="最近更新" value={formatDateTime(sel.updated_at)} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <FieldL label="显示名"><input value={dispName} onChange={(e) => setDispName(e.target.value)} className={inputClass} /></FieldL>
                <FieldL label="基线分支"><input value={baseBranch} onChange={(e) => setBaseBranch(e.target.value)} className={inputClass} /></FieldL>
              </div>
              <FieldL label="仓库根目录"><input value={rootPath} onChange={(e) => setRootPath(e.target.value)} placeholder="本地 Git 仓库路径" className={inputClass} /></FieldL>
              <FieldL label="忽略目录"><textarea rows={3} value={ignoreRules} onChange={(e) => setIgnoreRules(e.target.value)} className={inputClass} /></FieldL>
              <div className="flex items-center gap-3">
                <button type="submit" disabled={!sel || !rootPath.trim() || m.isPending} className={btnPrimaryClass}>{m.isPending ? "保存中..." : "保存绑定"}</button>
                <Link to={buildProjectOverviewRoute({ projectId: sel.id, view: "repository-workspace" })} className={btnClass}>仓库工作区</Link>
                {fb && <span className="text-xs text-zinc-400">{fb}</span>}
                {m.isError && <span className="text-xs text-red-400">{buildBindError(m.error, rootPath)}</span>}
              </div>
            </>
          )}
        </form>
      )}
    </div>
  );
}

/* ═══════════ Section 4: Diagnostics ═══════════ */

function DiagnosticsSection() {
  const pq = useQuery({ queryKey: ["provider-settings", "openai"], queryFn: fetchProvider });
  const hq = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const wq = useQuery({ queryKey: ["repository-workspace-settings"], queryFn: fetchWorkspaceSettings });

  const [testResult, setTestResult] = useState<ProviderTestResponse | null>(null);
  const tm = useMutation({
    mutationFn: testProviderConnection,
    onSuccess: (r) => setTestResult(r),
  });

  const buildDiagnostics = () => {
    const p = pq.data;
    const h = hq.data;
    const w = wq.data;
    const t = testResult;
    const lines = [
      "=== 系统诊断信息 ===",
      `时间: ${new Date().toISOString()}`,
      "",
      "-- Provider 配置 --",
      `配置状态: ${p?.configured ? "已配置" : "未配置"}`,
      `来源: ${p ? SOURCE_LABELS[p.source] : "未知"}`,
      `检测类型: ${p?.detected_provider_type ?? "—"}`,
      `Base URL: ${p?.base_url ?? "—"}`,
      `超时: ${p?.timeout_seconds ?? "?"}s`,
      `预设: ${p ? PRESET_LABELS[p.model_preset] : "—"}`,
      `模型: ${p ? `${p.model_names.economy} / ${p.model_names.balanced} / ${p.model_names.premium}` : "—"}`,
      "",
      "-- Provider 测试 --",
      ...(t ? [
        `状态: ${t.status}`, `认证: ${t.auth_valid}`, `端点: ${t.endpoint_reachable}`,
        `模型可用: ${t.model_usable}`, `延迟: ${t.latency_ms}ms`, `API: ${t.api_family}`,
        t.error_summary ? `错误: ${t.error_summary}` : null,
      ].filter(Boolean) : ["未执行测试。请先点击测试连接。"]),
      "",
      "-- 运行环境 --",
      `健康状态: ${h?.status ?? "未知"}`,
      `数据库: 暂无专用诊断接口`,
      `Worker: 暂无专用诊断接口`,
      `Event Stream: 暂无专用诊断接口`,
      "",
      "-- 安全边界 --",
      `默认根目录: ${w?.default_workspace_root ?? "—"}`,
      `生效根目录: ${(w?.allowed_workspace_roots ?? []).join("; ") || "—"}`,
      `使用默认: ${w?.using_default ? "是" : "否"}`,
      "",
      "-- 缺失接口 --",
      "数据库诊断: 无",
      "Worker 诊断: 无",
      "Event Stream 诊断: 无",
      "运行日志: 请前往运行观测页",
    ];
    return lines.join("\n");
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildDiagnostics());
    } catch { /* clipboard unavailable */ }
  };

  return (
    <section className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-5 space-y-4">
      <SectionHeader title="系统诊断" desc="一键复制系统配置摘要与诊断信息，用于问题排查" />
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => tm.mutate()} disabled={tm.isPending} className={btnClass}>
          {tm.isPending ? "测试中..." : "执行测试连接"}
        </button>
        <button type="button" onClick={handleCopy} className={btnPrimaryClass}>复制诊断信息</button>
      </div>
      {tm.isError && <p className="text-xs text-red-400">测试失败：{tm.error.message}</p>}
      <div className="rounded border border-[#333333] bg-[#111111] p-3 max-h-[240px] overflow-y-auto">
        <pre className="text-[10px] text-zinc-400 whitespace-pre-wrap break-all font-mono">{buildDiagnostics()}</pre>
      </div>
      <p className="text-[11px] text-zinc-600">诊断信息不含 API Key 明文。完整运行日志请前往运行观测页。</p>
    </section>
  );
}

/* ─── shared ─── */

function SectionHeader({ title, desc }: { title: string; desc: string }) {
  return (
    <div>
      <h2 className="text-base font-semibold text-zinc-200">{title}</h2>
      <p className="mt-0.5 text-xs text-zinc-500">{desc}</p>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[#333333] px-3 py-2">
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className="text-sm text-zinc-300 mt-0.5 truncate" title={value}>{value}</div>
    </div>
  );
}

function TestStat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" }) {
  return (
    <div className={`rounded border px-3 py-2 ${tone === "ok" ? "border-zinc-600" : tone === "warn" ? "border-zinc-700" : "border-[#333333]"}`}>
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className={`text-sm mt-0.5 truncate ${tone === "ok" ? "text-zinc-300" : tone === "warn" ? "text-zinc-500" : "text-zinc-300"}`}>{value}</div>
    </div>
  );
}

function FieldL({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><div className="text-xs text-zinc-500 mb-1">{label}</div>{children}</label>;
}

function parseLines(v: string) {
  return Array.from(new Set(v.split(/[\n,]/).map((s) => s.trim()).filter(Boolean)));
}

function truncateUrl(url: string) {
  return url.length > 42 ? url.slice(0, 42) + "..." : url;
}

function buildBindError(error: Error, _rootPath: string) {
  const msg = error.message;
  if (msg.includes("exceeds")) return `保存失败：仓库路径不在允许边界内。请先在安全边界中添加该路径的上级目录。`;
  if (msg.includes("does not exist")) return "保存失败：仓库路径不存在。";
  if (msg.includes("must be a directory")) return "保存失败：路径不是目录。";
  if (msg.includes("Git")) return "保存失败：目录不像 Git 仓库。";
  return `保存失败：${msg}`;
}
