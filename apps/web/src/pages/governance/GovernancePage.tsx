import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useSystemRoleCatalog } from "../../features/roles/hooks";
import { useSkillRegistry } from "../../features/skills/hooks";
import { useProjectCostDashboardSnapshot } from "../../features/costs/hooks";
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
        {activeTab === "team" && <TeamTab hasProject={hasProject} projectName={selectedProjectName} />}
        {activeTab === "roles" && <RolesTab hasProject={hasProject} />}
        {activeTab === "skills" && <SkillsTab hasProject={hasProject} />}
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

function TeamTab({ hasProject, projectName }: { hasProject: boolean; projectName: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const role = AI_TEAM_ROLES.find((r) => r.code === selected);

  if (!hasProject) {
    return <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择一个项目</div>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">{projectName} · AI 团队编队（基于角色目录静态基线，待接入真实运行时消费证据）</p>
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
                <DetailRow label="来源" value="静态基线（角色目录定义，非运行时数据）" />
                <DetailRow label="绑定 Skill" value={`${role.skills} 个`} />
                <DetailRow label="当前任务状态" value="待接入" />
                <DetailRow label="最近消费证据" value="暂无消费证据" />
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

function RolesTab({ hasProject }: { hasProject: boolean }) {
  const catalogQuery = useSystemRoleCatalog();
  const [selected, setSelected] = useState<string | null>(null);

  const catalog = catalogQuery.data;
  const selectedRole = catalog?.find((r: { code: string }) => r.code === selected);

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">角色治理 · 区分角色模板与项目角色实例 · 生命周期管理</p>

      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择项目查看角色目录</div>
      ) : (
        <TwoPanel
          left={
            catalogQuery.isLoading ? (
              <div className="text-sm text-zinc-600 px-3 py-6">加载角色目录...</div>
            ) : catalog && catalog.length > 0 ? (
              catalog.map((r: { code: string; name: string; summary: string }) => (
                <button key={r.code} type="button" onClick={() => setSelected(r.code)}
                  className={`w-full text-left rounded border px-3 py-2.5 text-xs transition ${
                    selected === r.code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
                  }`}
                >
                  <span className="text-zinc-200 block">{r.name || r.code}</span>
                  <span className="text-zinc-600">{r.code} · {r.summary ? r.summary.slice(0, 40) : "系统角色"}</span>
                </button>
              ))
            ) : (
              <div className="text-sm text-zinc-600 px-3 py-6">系统角色目录为空，使用静态基线</div>
            )
          }
          right={
            selectedRole ? (
              <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
                <h3 className="text-base font-medium text-zinc-200">{selectedRole.name || selectedRole.code}</h3>
                <div className="space-y-2 text-xs">
                  <DetailRow label="角色代码" value={selectedRole.code} />
                  <DetailRow label="来源" value={catalog && catalog.length > 0 ? "角色目录 API（真实读取）" : "静态基线"} />
                  <DetailRow label="角色类型" value="系统角色（可派生项目实例）" />
                  <DetailRow label="生命周期" value="project_local" />
                  <div>
                    <p className="text-zinc-500 mb-1">生命周期状态</p>
                    <div className="flex flex-wrap gap-1">
                      {ROLE_LIFECYCLE.map((lc) => (
                        <span key={lc.key} className={`text-[10px] rounded border px-1.5 py-0.5 ${
                          lc.key === "project_local" ? "border-zinc-400 text-zinc-300" : "border-[#333333] text-zinc-600"
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
                <p className="text-xs">选择左侧角色查看详情。{catalogQuery.isLoading ? "正在从角色目录 API 加载数据..." : catalog && catalog.length > 0 ? `已读取 ${catalog.length} 个系统角色。` : "当前使用静态基线。"}</p>
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

function SkillsTab({ hasProject }: { hasProject: boolean }) {
  const registryQuery = useSkillRegistry();
  const [selected, setSelected] = useState<string | null>(null);

  const registry = registryQuery.data;
  const skills = registry?.skills ?? [];
  const selectedSkill = skills.find((s: { code: string }) => s.code === selected);

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">Skill 治理 · 区分正式 Skill / 项目临时 Skill / Skill 迭代候选（生命周期状态基于静态基线，API 无 status 字段）</p>
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">请选择项目查看 Skill 注册表</div>
      ) : (
        <TwoPanel
          left={
            registryQuery.isLoading ? (
              <div className="text-sm text-zinc-600 px-3 py-6">加载 Skill 注册表...</div>
            ) : skills.length > 0 ? (
              skills.map((s: { code: string; name: string; summary: string; enabled: boolean }) => (
                <button key={s.code} type="button" onClick={() => setSelected(s.code)}
                  className={`w-full text-left rounded border px-3 py-2.5 text-xs transition ${
                    selected === s.code ? "border-zinc-400 bg-[#222222]" : "border-[#333333] bg-[#1a1a1a] hover:border-zinc-600"
                  }`}
                >
                  <span className="text-zinc-200 block">{s.name || s.code}</span>
                  <span className="text-zinc-600">{s.code} · {s.enabled ? "enabled" : "disabled"}</span>
                </button>
              ))
            ) : (
              <div className="text-sm text-zinc-600 px-3 py-6">Skill 注册表为空，使用静态基线</div>
            )
          }
          right={
            selectedSkill ? (
              <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4 space-y-3">
                <h3 className="text-base font-medium text-zinc-200">{selectedSkill.name || selectedSkill.code}</h3>
                <div className="space-y-2 text-xs">
                  <DetailRow label="Skill 代码" value={selectedSkill.code} />
                  <DetailRow label="来源" value={skills.length > 0 ? "Skill 注册表 API（真实读取）" : "静态基线"} />
                  <DetailRow label="启用状态" value={selectedSkill.enabled ? "已启用" : "未启用"} />
                  <DetailRow label="生命周期" value="API 未返回 status 字段，基于静态基线判断" />
                  <DetailRow label="最近消费证据" value="暂无消费证据" />
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
                <p className="text-[10px] text-zinc-600">AI 只能建议沉淀 Skill，需用户确认。合并/升级/删除操作待用户确认闭环后端接入。</p>
              </div>
            ) : (
              <div className="rounded border border-[#333333] px-4 py-3 text-sm text-zinc-600">
                <p className="text-zinc-400 mb-2">Skill 生命周期说明</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {SKILL_LIFECYCLE.map((lc) => (
                    <span key={lc.key} className="text-[11px] rounded border border-[#333333] px-2 py-1 text-zinc-500">{lc.label}</span>
                  ))}
                </div>
                <p className="text-xs">选择左侧 Skill 查看详情。{registryQuery.isLoading ? "正在从 Skill 注册表 API 加载..." : skills.length > 0 ? `已读取 ${skills.length} 个 Skill。` : "当前使用静态基线。"}</p>
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
  { id: "forbid", category: "禁止自动执行", items: ["git commit", "git push", "发布生产", "删除项目", "删除交付物", "覆盖 Provider Key", "删除运行证据", "永久删除稳定 Skill / 角色模板"], why: "不可逆操作，必须人工决策", backend: "静态基线策略定义，动态策略引擎待后端接入" },
];

function PolicyTab() {
  const [selected, setSelected] = useState<string | null>(null);
  const policy = POLICIES.find((p) => p.id === selected);

  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400">策略与权限 · 区分 AI 可自动执行、需确认、禁止自动执行三类</p>
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
      <p className="text-sm text-zinc-400">成本与记忆 · 成本来源可信度标注 · 记忆生命周期管理</p>
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
