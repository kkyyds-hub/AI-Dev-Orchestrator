import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useProjectRoleCatalog, useProjectRoleSkillConsumption, useSystemRoleCatalog } from "../../features/roles/hooks";
import { useProjectSkillBindings, useSkillRegistry } from "../../features/skills/hooks";
import { useProjectCostDashboardSnapshot } from "../../features/costs/hooks";
import { GitWriteReadbackPanel } from "../../features/git-write/GitWriteReadbackPanel";
import { useProjectScope } from "../shared/useProjectScope";

const TABS = [
  { key: "team", label: "本项目 AI 团队" },
  { key: "roles", label: "角色治理" },
  { key: "skills", label: "Skill 治理" },
  { key: "policy", label: "策略与权限" },
  { key: "cost-memory", label: "成本与记忆" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export function GovernancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName, projectNotFound } =
    useProjectScope();

  const rawTab = searchParams.get("tab") ?? "";
  const activeTab: TabKey = TABS.some((t) => t.key === rawTab) ? rawTab as TabKey : "team";

  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    if (selectedProjectId !== "all") next.set("projectId", selectedProjectId);
    else next.delete("projectId");
    setSearchParams(next, { replace: true });
  };

  const hasProject = selectedProjectId !== "all";

  return (
    <div className="relative min-w-0 space-y-5">
      {/* Header */}
      <header className="border-b border-[#333333] pb-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              AI 团队资产治理中心
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              {hasProject ? `当前项目：${selectedProjectName}` : "全部项目"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-zinc-500">项目</label>
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="rounded border border-[#333333] bg-[#1a1a1a] px-2.5 py-1 text-xs text-zinc-300 outline-none focus:border-zinc-500"
            >
              <option value="all">全部项目</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#333333] overflow-x-auto">
        {TABS.map((t) => (
          <button key={t.key} type="button" onClick={() => setActiveTab(t.key)}
            className={`shrink-0 px-4 py-2 text-sm transition border-b-2 -mb-[1px] ${
              activeTab === t.key ? "border-zinc-400 text-zinc-200" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >{t.label}</button>
        ))}
      </div>

      {projectNotFound ? (
        <div className="rounded border border-zinc-700 px-4 py-3 text-sm text-zinc-400">
          项目不存在或已删除。{" "}
          <button onClick={() => setSelectedProjectId("all")} className="underline hover:text-zinc-200">切回全部项目</button>
        </div>
      ) : null}

      <div className="min-h-[400px]">
        {activeTab === "team" && <TeamTab hasProject={hasProject} projectId={hasProject ? selectedProjectId : null} projectName={selectedProjectName} />}
        {activeTab === "roles" && <RolesTab hasProject={hasProject} projectId={hasProject ? selectedProjectId : null} />}
        {activeTab === "skills" && <SkillsTab hasProject={hasProject} projectId={hasProject ? selectedProjectId : null} />}
        {activeTab === "policy" && <PolicyTab />}
        {activeTab === "cost-memory" && <CostMemoryTab hasProject={hasProject} projectId={hasProject ? selectedProjectId : null} />}
      </div>
    </div>
  );
}

/* ─── Shared layout: left list + right panel ─── */

function TwoPanel({ left, right }: { left: React.ReactNode; right: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-5">
      <div className="min-h-0 overflow-y-auto space-y-1">{left}</div>
      <div className="min-h-0">{right}</div>
    </div>
  );
}

/* ═══════════ Tab: 本项目 AI 团队 ═══════════ */

const AI_TEAM_ROLES = [
  { code: "project_director", role: "AI 项目主管", desc: "生成作战计划、拆分任务、分配 Agent、监督运行、识别阻塞", skills: 4 },
  { code: "frontend_agent", role: "前端体验 Agent", desc: "负责 UI 组件、布局、样式与前端交互闭环", skills: 3 },
  { code: "backend_agent", role: "后端闭环 Agent", desc: "负责 API 路由、数据模型、业务逻辑与状态机", skills: 3 },
  { code: "qa_agent", role: "测试验收 Agent", desc: "负责测试用例、验收检查、回归验证", skills: 2 },
  { code: "docs_agent", role: "文档收口 Agent", desc: "负责产品文档、技术文档、验收记录回填", skills: 2 },
  { code: "review_agent", role: "审查 Agent", desc: "负责代码审查、风险发现、预检评估", skills: 2 },
];

function formatShortId(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : "-";
}

function formatRuntimeDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function formatRoleConsumptionEvidence(
  item:
    | {
        run_count: number;
        succeeded_run_count: number;
        failed_run_count: number;
        total_tokens: number;
        latest_run_id: string | null;
        latest_run_status: string | null;
        latest_run_created_at: string | null;
      }
    | null
    | undefined,
  isLoading: boolean,
): string {
  if (isLoading) return "正在读取运行时消费证据...";
  if (!item) return "暂无运行时消费证据（已接入消费聚合 API）";
  return `${item.run_count} 次运行；成功 ${item.succeeded_run_count} / 失败 ${item.failed_run_count}；最近 ${item.latest_run_status ?? "-"} · ${formatRuntimeDate(item.latest_run_created_at)} · run ${formatShortId(item.latest_run_id)}；tokens ${item.total_tokens}`;
}

function formatSkillConsumptionEvidence(
  item:
    | {
        run_count: number;
        succeeded_run_count: number;
        failed_run_count: number;
        total_tokens: number;
        latest_run_id: string | null;
        latest_owner_role_code: string | null;
        latest_run_status: string | null;
        latest_run_created_at: string | null;
      }
    | null
    | undefined,
  isLoading: boolean,
): string {
  if (isLoading) return "正在读取运行时消费证据...";
  if (!item) return "暂无运行时消费证据（已接入消费聚合 API）";
  return `${item.run_count} 次被选用；成功 ${item.succeeded_run_count} / 失败 ${item.failed_run_count}；最近 ${item.latest_run_status ?? "-"} · ${formatRuntimeDate(item.latest_run_created_at)} · role ${item.latest_owner_role_code ?? "-"} · run ${formatShortId(item.latest_run_id)}；tokens ${item.total_tokens}`;
}

function TeamTab({ hasProject, projectId, projectName }: { hasProject: boolean; projectId: string | null; projectName: string }) {
  const consumptionQuery = useProjectRoleSkillConsumption(projectId);
  const consumption = consumptionQuery.data;
  const [selected, setSelected] = useState<string | null>(null);
  const role = AI_TEAM_ROLES.find((r) => r.code === selected);

  if (!hasProject) {
    return <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择一个项目</div>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">
        {projectName} · AI 团队编队。运行时消费证据来自 GET /roles/projects/:id/consumption：
        {consumptionQuery.isLoading
          ? " 正在读取..."
          : consumption
          ? ` ${consumption.total_run_count} 次 Run，${consumption.role_consumption_count} 个角色，${consumption.skill_consumption_count} 个 Skill。`
          : " 暂无运行时消费证据。"}
      </p>
      <TwoPanel
        left={
          AI_TEAM_ROLES.map((r) => (
            <button key={r.code} type="button" onClick={() => setSelected(r.code)}
              className={`w-full text-left rounded border px-3 py-2.5 text-xs transition ${
                selected === r.code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
              }`}
            >
              <span className="text-zinc-200 block">{r.role}</span>
              <span className="text-zinc-600">{r.code} · {r.skills} Skill</span>
            </button>
          ))
        }
        right={
          role ? (
            <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
              <h3 className="text-base font-medium text-zinc-200">{role.role}</h3>
              <div className="space-y-2 text-xs">
                <DetailRow label="职责" value={role.desc} />
                <DetailRow label="来源" value="角色目录静态基线 + 运行时消费聚合 API（真实读取）" />
                <DetailRow label="绑定 Skill" value={`${role.skills} 个`} />
                <DetailRow label="当前任务状态" value={consumptionQuery.isLoading ? "正在读取运行时消费证据..." : consumption ? `${consumption.total_run_count} 次 Run 已进入治理聚合` : "暂无运行时消费证据"} />
                <DetailRow label="最近消费证据" value={consumption ? `角色消费 ${consumption.role_consumption_count} 项，Skill 消费 ${consumption.skill_consumption_count} 项；生成于 ${formatRuntimeDate(consumption.generated_at)}` : "暂无运行时消费证据（已接入消费聚合 API）"} />
                <DetailRow label="是否建议沉淀" value="建议沉淀（需用户确认，暂不提供假保存）" />
              </div>
              <button type="button" disabled
                className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
              >建议沉淀（待确认闭环）</button>
            </div>
          ) : (
            <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">选择左侧角色查看详情</div>
          )
        }
      />
    </div>
  );
}

/* ═══════════ Tab: 角色治理 ═══════════ */

const ROLE_LIFECYCLE = [
  { key: "project_local", label: "项目实例" },
  { key: "template_candidate", label: "候选模板" },
  { key: "template_stable", label: "稳定模板" },
  { key: "deprecated", label: "不推荐" },
  { key: "archived", label: "已归档" },
];

function RolesTab({ hasProject, projectId }: { hasProject: boolean; projectId: string | null }) {
  const systemQuery = useSystemRoleCatalog();
  const projectQuery = useProjectRoleCatalog(projectId);
  const consumptionQuery = useProjectRoleSkillConsumption(projectId);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<{ source: "system" | "project"; code: string } | null>(null);

  const systemRoles = systemQuery.data ?? [];
  const projectRoles = projectQuery.data?.roles ?? [];
  const projectSummary = projectQuery.data;
  const roleConsumptionByCode = new Map(
    (consumptionQuery.data?.roles ?? []).map((item) => [item.role_code, item]),
  );

  const lowerSearch = search.toLowerCase().trim();

  const filteredSystem = useMemo(() => {
    if (!lowerSearch) return systemRoles;
    return systemRoles.filter((r) =>
      (r.code + r.name + r.summary).toLowerCase().includes(lowerSearch));
  }, [systemRoles, lowerSearch]);

  const filteredProject = useMemo(() => {
    if (!lowerSearch) return projectRoles;
    return projectRoles.filter((r) =>
      (r.role_code + r.name + r.summary).toLowerCase().includes(lowerSearch));
  }, [projectRoles, lowerSearch]);

  const hasResults = filteredSystem.length > 0 || filteredProject.length > 0;

  const selectedRole =
    selected?.source === "system"
      ? systemRoles.find((r) => r.code === selected.code)
      : selected?.source === "project"
      ? projectRoles.find((r) => r.role_code === selected.code)
      : null;

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">角色治理 · 区分角色模板与项目角色实例 · 生命周期管理</p>

      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择项目查看角色目录</div>
      ) : (
        <TwoPanel
          left={
            <div className="space-y-3">
              <input
                type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索角色（名称 / code / 摘要）..."
                className="w-full rounded border border-[#333333] bg-[#111111] px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
              />
              {!hasResults && lowerSearch ? (
                <div className="text-xs text-zinc-600 px-3 py-4 text-center">
                  未找到匹配角色，请调整关键词。
                </div>
              ) : (
                <>
              {/* 系统角色模板 */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500 mb-2">
                  系统角色模板{lowerSearch ? `（${filteredSystem.length} 条）` : ""}
                </p>
                <p className="text-[10px] text-zinc-600 mb-2">来自 GET /roles/catalog</p>
                {systemQuery.isLoading ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">加载中...</div>
                ) : filteredSystem.length > 0 ? (
                  filteredSystem.map((r) => (
                    <button key={r.code} type="button" onClick={() => setSelected({ source: "system", code: r.code })}
                      className={`w-full text-left rounded border px-3 py-2.5 text-xs transition mb-1 ${
                        selected?.source === "system" && selected.code === r.code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
                      }`}
                    >
                      <span className="text-zinc-200 block truncate">{r.name || r.code}</span>
                      <span className="text-zinc-600 truncate">{r.code}</span>
                    </button>
                  ))
                ) : systemRoles.length === 0 ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">系统目录为空</div>
                ) : null}
              </div>
              {/* 项目角色实例 */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500 mb-2">
                  项目角色实例{lowerSearch ? `（${filteredProject.length} 条）` : ""}
                </p>
                <p className="text-[10px] text-zinc-600 mb-2">来自 GET /roles/projects/:id</p>
                {!projectId ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">待选择项目</div>
                ) : projectQuery.isLoading ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">加载中...</div>
                ) : filteredProject.length > 0 ? (
                  filteredProject.map((r) => (
                    <button key={r.role_code} type="button" onClick={() => setSelected({ source: "project", code: r.role_code })}
                      className={`w-full text-left rounded border px-3 py-2.5 text-xs transition mb-1 ${
                        selected?.source === "project" && selected.code === r.role_code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
                      }`}
                    >
                      <span className="text-zinc-200 block truncate">{r.name || r.role_code}</span>
                      <span className="text-zinc-600 truncate">{r.role_code} · project_local</span>
                    </button>
                  ))
                ) : projectRoles.length === 0 ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">当前项目暂无角色实例（使用系统角色基线）</div>
                ) : null}
              </div>
                </>
              )}
            </div>
          }
          right={
            selectedRole ? (
              <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
                <h3 className="text-base font-medium text-zinc-200 truncate">{selectedRole.name || getRoleCode(selectedRole)}</h3>
                <div className="space-y-2 text-xs">
                  <DetailRow label="角色代码" value={getRoleCode(selectedRole)} />
                  <DetailRow label="来源" value={selected?.source === "system" ? "系统角色目录 API（真实读取）" : "项目角色实例 API（真实读取）"} />
                  <DetailRow label="角色类型" value={selected?.source === "system" ? "系统角色模板" : "项目角色实例"} />
                  <DetailRow label="最近消费证据" value={formatRoleConsumptionEvidence(roleConsumptionByCode.get(getRoleCode(selectedRole)), consumptionQuery.isLoading)} />
                  <div>
                    <p className="text-zinc-500 mb-1">生命周期</p>
                    <div className="flex flex-wrap gap-1">
                      {ROLE_LIFECYCLE.map((lc) => (
                        <span key={lc.key} className={`text-[10px] rounded border px-1.5 py-0.5 ${
                          (selected?.source === "project" && lc.key === "project_local") || (selected?.source === "system" && lc.key === "template_stable")
                            ? "border-zinc-400 text-zinc-300" : "border-[#333333] text-zinc-600"
                        }`}>{lc.label}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <button type="button" disabled
                  className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
                >保存为模板（待确认闭环）</button>
                <p className="text-[10px] text-zinc-600">AI 只能建议沉淀角色，需用户确认后正式保存。当前确认闭环后端待接入。</p>
              </div>
            ) : (
              <div className="rounded border border-[#333333] px-4 py-3 text-sm text-zinc-600">
                <p className="text-zinc-400 mb-2">角色生命周期说明</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {ROLE_LIFECYCLE.map((lc) => (
                    <span key={lc.key} className="text-[11px] rounded border border-[#333333] px-2 py-1 text-zinc-500">{lc.label}</span>
                  ))}
                </div>
                <p className="text-xs">
                  选择左侧角色查看详情。系统角色 {systemRoles.length} 个{projectId ? `，项目角色 ${projectSummary?.available_role_count ?? 0} 个` : ""}。
                </p>
              </div>
            )
          }
        />
      )}
    </div>
  );
}

/* ═══════════ Tab: Skill 治理 ═══════════ */

const SKILL_LIFECYCLE = [
  { key: "draft", label: "草案" },
  { key: "temporary", label: "临时" },
  { key: "candidate", label: "候选沉淀" },
  { key: "stable", label: "稳定" },
  { key: "deprecated", label: "不推荐" },
  { key: "archived", label: "已归档" },
];

function SkillsTab({ hasProject, projectId }: { hasProject: boolean; projectId: string | null }) {
  const registryQuery = useSkillRegistry();
  const bindingsQuery = useProjectSkillBindings(projectId);
  const consumptionQuery = useProjectRoleSkillConsumption(projectId);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<{ source: "registry" | "binding"; code: string } | null>(null);

  const registry = registryQuery.data;
  const registrySkills = registry?.skills ?? [];
  const bindings = bindingsQuery.data;
  const bindingRoles = bindings?.roles ?? [];
  const roleConsumptionByCode = new Map(
    (consumptionQuery.data?.roles ?? []).map((item) => [item.role_code, item]),
  );
  const skillConsumptionByCode = new Map(
    (consumptionQuery.data?.skills ?? []).map((item) => [item.skill_code, item]),
  );

  const lowerSearch = search.toLowerCase().trim();

  const filteredRegistry = useMemo(() => {
    if (!lowerSearch) return registrySkills;
    return registrySkills.filter((s) =>
      (s.code + s.name + (s.summary ?? "") + (s.purpose ?? "")).toLowerCase().includes(lowerSearch));
  }, [registrySkills, lowerSearch]);

  const filteredBindings = useMemo(() => {
    if (!lowerSearch) return bindingRoles;
    return bindingRoles.filter((r) => {
      const skillText = r.skills?.map((s) => s.skill_code + s.skill_name + (s.summary ?? "")).join(" ") ?? "";
      return (r.role_code + r.role_name + skillText).toLowerCase().includes(lowerSearch);
    });
  }, [bindingRoles, lowerSearch]);

  const hasResults = filteredRegistry.length > 0 || filteredBindings.length > 0;

  const selectedSkill =
    selected?.source === "registry"
      ? registrySkills.find((s) => s.code === selected.code)
      : null;
  const selectedBindingRole =
    selected?.source === "binding"
      ? bindingRoles.find((r) => r.role_code === selected.code)
      : null;

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">Skill 治理 · 区分正式 Skill / 项目临时 Skill / Skill 迭代候选（生命周期基于静态基线，API 无 status 字段）</p>
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择项目查看 Skill 注册表</div>
      ) : (
        <TwoPanel
          left={
            <div className="space-y-3">
              <input
                type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索 Skill（名称 / code / 摘要 / 用途）..."
                className="w-full rounded border border-[#333333] bg-[#111111] px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none"
              />
              {!hasResults && lowerSearch ? (
                <div className="text-xs text-zinc-600 px-3 py-4 text-center">
                  未找到匹配 Skill 或绑定，请调整关键词。
                </div>
              ) : (
                <>
              {/* 正式 Skill 注册表 */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500 mb-2">
                  Skill 注册表{lowerSearch ? `（${filteredRegistry.length} 条）` : ""}
                </p>
                <p className="text-[10px] text-zinc-600 mb-2">来自 GET /skills/registry</p>
                {registryQuery.isLoading ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">加载中...</div>
                ) : filteredRegistry.length > 0 ? (
                  filteredRegistry.map((s) => (
                    <button key={s.code} type="button" onClick={() => setSelected({ source: "registry", code: s.code })}
                      className={`w-full text-left rounded border px-3 py-2.5 text-xs transition mb-1 ${
                        selected?.source === "registry" && selected.code === s.code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
                      }`}
                    >
                      <span className="text-zinc-200 block truncate">{s.name || s.code}</span>
                      <span className="text-zinc-600 truncate">{s.code} · {s.enabled ? "enabled" : "disabled"}</span>
                    </button>
                  ))
                ) : registrySkills.length === 0 ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">注册表为空</div>
                ) : null}
              </div>
              {/* 项目 Skill 绑定 */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500 mb-2">
                  项目 Skill 绑定{lowerSearch ? `（${filteredBindings.length} 条）` : ""}
                </p>
                <p className="text-[10px] text-zinc-600 mb-2">来自 GET /skills/projects/:id/bindings</p>
                {!projectId ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">待选择项目</div>
                ) : bindingsQuery.isLoading ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">加载中...</div>
                ) : filteredBindings.length > 0 ? (
                  filteredBindings.map((r) => (
                    <button key={r.role_code} type="button" onClick={() => setSelected({ source: "binding", code: r.role_code })}
                      className={`w-full text-left rounded border px-3 py-2.5 text-xs transition mb-1 ${
                        selected?.source === "binding" && selected.code === r.role_code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
                      }`}
                    >
                      <span className="text-zinc-200 block truncate">{r.role_name}</span>
                      <span className="text-zinc-600 truncate">{r.bound_skill_count} 个 Skill</span>
                    </button>
                  ))
                ) : bindingRoles.length === 0 ? (
                  <div className="text-xs text-zinc-600 px-3 py-2">当前项目暂无 Skill 绑定记录</div>
                ) : null}
              </div>
                </>
              )}
            </div>
          }
          right={
            selectedSkill ? (
              <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
                <h3 className="text-base font-medium text-zinc-200 truncate">{selectedSkill.name || selectedSkill.code}</h3>
                <div className="space-y-2 text-xs">
                  <DetailRow label="Skill 代码" value={selectedSkill.code} />
                  <DetailRow label="来源" value="Skill 注册表 API（真实读取）" />
                  <DetailRow label="启用状态" value={selectedSkill.enabled ? "已启用" : "未启用"} />
                  <DetailRow label="生命周期" value="API 未返回 status 字段，基于静态基线判断" />
                  <DetailRow label="最近消费证据" value={formatSkillConsumptionEvidence(skillConsumptionByCode.get(selectedSkill.code), consumptionQuery.isLoading)} />
                  <div>
                    <p className="text-zinc-500 mb-1">生命周期（静态基线）</p>
                    <div className="flex flex-wrap gap-1">
                      {SKILL_LIFECYCLE.map((lc) => (
                        <span key={lc.key} className="text-[10px] rounded border border-[#333333] px-1.5 py-0.5 text-zinc-600">{lc.label}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" disabled className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed">提升为正式 Skill</button>
                  <button type="button" disabled className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed">生成新版本</button>
                  <button type="button" disabled className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed">删除</button>
                </div>
                <p className="text-[10px] text-zinc-600">AI 只能建议沉淀 Skill，需用户确认。合并/升级/删除操作待确认闭环后端接入。</p>
              </div>
            ) : selectedBindingRole ? (
              <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
                <h3 className="text-base font-medium text-zinc-200 truncate">{selectedBindingRole.role_name}</h3>
                <div className="space-y-2 text-xs">
                  <DetailRow label="角色代码" value={selectedBindingRole.role_code} />
                  <DetailRow label="来源" value="项目 Skill 绑定 API（真实读取）" />
                  <DetailRow label="绑定 Skill 数" value={`${selectedBindingRole.bound_skill_count} 个`} />
                  <DetailRow label="角色启用" value={selectedBindingRole.role_enabled ? "是" : "否"} />
                  <DetailRow label="最近消费证据" value={formatRoleConsumptionEvidence(roleConsumptionByCode.get(selectedBindingRole.role_code), consumptionQuery.isLoading)} />
                </div>
              </div>
            ) : (
              <div className="rounded border border-[#333333] px-4 py-3 text-sm text-zinc-600">
                <p className="text-zinc-400 mb-2">Skill 生命周期说明</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {SKILL_LIFECYCLE.map((lc) => (
                    <span key={lc.key} className="text-[11px] rounded border border-[#333333] px-2 py-1 text-zinc-500">{lc.label}</span>
                  ))}
                </div>
                <p className="text-xs">
                  选择左侧 Skill 查看详情。注册表 {registrySkills.length} 个{projectId ? `，项目绑定 ${bindings?.total_bound_skills ?? 0} 个 Skill（${bindingRoles.length} 个角色）` : ""}。
                </p>
                <p className="mt-2 text-xs text-zinc-600">临时 Skill 清理策略：按使用次数、绑定角色数、最近消费时间、版本替代关系综合判断。</p>
              </div>
            )
          }
        />
      )}
    </div>
  );
}

/* ═══════════ Tab: 策略与权限 ═══════════ */

const POLICIES = [
  { id: "auto", category: "可自动执行", items: ["Worker 单次调度", "运行观测状态读取", "交付物摘要生成", "成本数据读取"], why: "低风险，不需要修改系统状态或资产", backend: "部分已接入（Worker/观测），部分待接入" },
  { id: "confirm", category: "需要用户确认", items: ["生成作战计划", "调整任务优先级", "角色/Skill 沉淀建议", "项目阶段推进"], why: "中高风险，涉及项目方向、资源分配和资产变更", backend: "待接入用户确认闭环后端" },
  { id: "forbid", category: "禁止自动执行", items: ["生成本地提交", "推送远程仓库", "发布生产", "删除项目", "删除交付物", "覆盖 Provider Key", "删除运行证据", "永久删除稳定 Skill / 角色模板"], why: "不可逆操作，必须人工决策", backend: "静态基线策略定义，动态策略引擎待后端接入" },
];

function PolicyTab() {
  const [selected, setSelected] = useState<string | null>(null);
  const policy = POLICIES.find((p) => p.id === selected);

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">策略与权限 · 区分 AI 可自动执行、需确认、禁止自动执行三类</p>
      <GitWriteReadbackPanel />
      <TwoPanel
        left={
          POLICIES.map((p) => (
            <button key={p.id} type="button" onClick={() => setSelected(p.id)}
              className={`w-full text-left rounded border px-3 py-2.5 text-xs transition ${
                selected === p.id ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
              }`}
            >
              <span className="text-zinc-200 block">{p.category}</span>
              <span className="text-zinc-600">{p.items.length} 项</span>
            </button>
          ))
        }
        right={
          policy ? (
            <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
              <h3 className="text-base font-medium text-zinc-200">{policy.category}</h3>
              <div className="space-y-2 text-xs">
                <DetailRow label="策略说明" value={policy.why} />
                <DetailRow label="后端状态" value={policy.backend} />
                <DetailRow label="数据来源" value="静态基线（基于产品基线文档定义，动态权限引擎待后端接入）" />
                <div>
                  <p className="text-zinc-500 mb-1">包含项</p>
                  <ul className="space-y-1">
                    {policy.items.map((item) => (
                      <li key={item} className="text-zinc-400">{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded border border-[#333333] px-4 py-3 text-sm text-zinc-500 text-center">选择左侧策略类别查看详情</div>
          )
        }
      />
    </div>
  );
}

/* ═══════════ Tab: 成本与记忆 ═══════════ */

function CostMemoryTab({ hasProject, projectId }: { hasProject: boolean; projectId: string | null }) {
  const costQuery = useProjectCostDashboardSnapshot(projectId);
  const costData = costQuery.data;

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">成本与记忆 · 成本来源可信度标注 · 记忆生命周期管理 · 本页签为摘要卡片区，Phase1 不采用资产列表结构</p>
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择项目查看成本与记忆摘要</div>
      ) : (
        <div className="space-y-4">
          {/* Cost */}
          <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">成本概览</h3>
            <div className="grid grid-cols-3 gap-3">
              {costQuery.isLoading ? (
                <div className="col-span-3 text-xs text-zinc-600">加载成本数据...</div>
              ) : costData ? (
                <>
                  <CostStat label="累计费用" value={`$${costData.total_estimated_cost_usd.toFixed(4)}`} />
                  <CostStat label="运行次数" value={String(costData.run_count)} />
                  <CostStat label="Token 总数" value={String(costData.total_tokens)} />
                </>
              ) : (
                <>
                  <CostStat label="累计费用" value="未接入" />
                  <CostStat label="运行次数" value="未接入" />
                  <CostStat label="Token 总数" value="未接入" />
                </>
              )}
            </div>
            <p className="text-[11px] text-zinc-600">
              成本数据来源可信度：provider_reported / heuristic / missing。
              {costData ? " 当前读取自成本仪表板 API（真实数据）。" : " 旧 API 已存在（GET /projects/:id/cost-dashboard），Phase1 未获取到数据。"}
              页面打开不触发 AI 生成。
            </p>
          </div>

          {/* Memory */}
          <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">记忆状态</h3>
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed">Compact</button>
              <button type="button" disabled className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed">Rehydrate</button>
              <button type="button" disabled className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed">Reset</button>
            </div>
            <p className="text-[11px] text-zinc-600">
              Compact / Rehydrate / Reset 无真实后端闭环，按钮已禁用。不会修改记忆，不会触发 AI 生成。
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function CostStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[#333333] px-3 py-2 text-center">
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className="text-sm font-medium text-zinc-300 mt-0.5">{value}</div>
    </div>
  );
}

/* ─── shared ─── */

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-zinc-500 mb-0.5">{label}</p>
      <p className="text-zinc-300">{value}</p>
    </div>
  );
}

function getRoleCode(r: { code?: string; role_code?: string }): string {
  return (r as { code: string }).code ?? (r as { role_code: string }).role_code ?? "";
}
