import { useSearchParams } from "react-router-dom";

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
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            className={`shrink-0 px-4 py-2 text-sm transition border-b-2 -mb-[1px] ${
              activeTab === t.key
                ? "border-zinc-400 text-zinc-200"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {projectNotFound ? (
        <div className="rounded border border-zinc-700 px-4 py-3 text-sm text-zinc-400">
          项目不存在或已删除。{" "}
          <button onClick={() => setSelectedProjectId("all")} className="underline hover:text-zinc-200">
            切回全部项目
          </button>
        </div>
      ) : null}

      {/* Tab content */}
      <div className="min-h-[360px]">
        {activeTab === "team" && <TeamTab hasProject={hasProject} projectName={selectedProjectName} />}
        {activeTab === "roles" && <RoleTab hasProject={hasProject} />}
        {activeTab === "skills" && <SkillTab hasProject={hasProject} />}
        {activeTab === "policy" && <PolicyTab />}
        {activeTab === "cost-memory" && <CostMemoryTab hasProject={hasProject} />}
      </div>
    </div>
  );
}

/* ─── Tab: 本项目 AI 团队 ─── */

const AI_TEAM_ROLES = [
  { role: "AI 项目主管", code: "project_director", desc: "生成作战计划、拆分任务、分配 Agent、监督运行、识别阻塞", skills: 4 },
  { role: "前端体验 Agent", code: "frontend_agent", desc: "负责 UI 组件、布局、样式与前端交互闭环", skills: 3 },
  { role: "后端闭环 Agent", code: "backend_agent", desc: "负责 API 路由、数据模型、业务逻辑与状态机", skills: 3 },
  { role: "测试验收 Agent", code: "qa_agent", desc: "负责测试用例、验收检查、回归验证", skills: 2 },
  { role: "文档收口 Agent", code: "docs_agent", desc: "负责产品文档、技术文档、验收记录回填", skills: 2 },
  { role: "审查 Agent", code: "review_agent", desc: "负责代码审查、风险发现、预检评估", skills: 2 },
];

function TeamTab({ hasProject, projectName }: { hasProject: boolean; projectName: string }) {
  return (
    <div className="space-y-4">
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">
          请选择一个项目
        </div>
      ) : (
        <>
          <p className="text-sm text-zinc-400">
            {projectName} · AI 团队编队（基于角色目录静态基线，待接入真实运行时消费证据）
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {AI_TEAM_ROLES.map((r) => (
              <div key={r.code} className="rounded border border-[#333333] bg-[#1a1a1a] p-4">
                <h3 className="text-sm font-medium text-zinc-200">{r.role}</h3>
                <p className="mt-1 text-xs text-zinc-500">{r.desc}</p>
                <div className="mt-3 flex items-center justify-between text-[11px]">
                  <span className="text-zinc-600">绑定 {r.skills} 个 Skill</span>
                  <span className="text-zinc-700">暂无消费证据</span>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-zinc-600">
            数据来源：角色目录静态基线。运行时 Agent 消费证据与任务执行记录待后端接入。
          </p>
        </>
      )}
    </div>
  );
}

/* ─── Tab: 角色治理 ─── */

function RoleTab({ hasProject }: { hasProject: boolean }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        角色治理 · 区分角色模板与项目角色实例 · 生命周期管理
      </p>
      {/* Lifecycle legend */}
      <div className="flex flex-wrap gap-2 text-[11px]">
        {[
          ["project_local", "项目实例"],
          ["template_candidate", "候选模板"],
          ["template_stable", "稳定模板"],
          ["deprecated", "不推荐"],
          ["archived", "已归档"],
        ].map(([key, label]) => (
          <span key={key} className="rounded border border-[#333333] px-2 py-1 text-zinc-500">
            {label}
          </span>
        ))}
      </div>
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">
          请选择项目查看角色目录
        </div>
      ) : (
        <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4">
          <p className="text-sm text-zinc-300">项目角色目录</p>
          <p className="mt-2 text-xs text-zinc-500">
            角色目包含项目本地角色与系统模板，可通过角色工作台查看详情。
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled
              className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
            >
              打开角色工作台
            </button>
            <span className="text-[10px] text-zinc-700 self-center">
              角色保存接口已存在，建议沉淀功能待接入用户确认闭环
            </span>
          </div>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
            {AI_TEAM_ROLES.slice(0, 4).map((r) => (
              <div key={r.code} className="rounded border border-[#333333] px-3 py-2 text-xs">
                <span className="text-zinc-300">{r.role}</span>
                <span className="ml-2 text-zinc-600">{r.code}</span>
                <span className="ml-2 text-zinc-700">project_local</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-zinc-600">
            AI 建议沉淀仅生成建议，需用户确认后正式保存。当前建议沉淀后端待接入。
          </p>
        </div>
      )}
    </div>
  );
}

/* ─── Tab: Skill 治理 ─── */

function SkillTab({ hasProject }: { hasProject: boolean }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        Skill 治理 · 区分正式 Skill / 项目临时 Skill / Skill 迭代候选 · 生命周期管理
      </p>
      <div className="flex flex-wrap gap-2 text-[11px]">
        {[
          ["draft", "草案"],
          ["temporary", "临时"],
          ["candidate", "候选沉淀"],
          ["stable", "稳定"],
          ["deprecated", "不推荐"],
          ["archived", "已归档"],
        ].map(([key, label]) => (
          <span key={key} className="rounded border border-[#333333] px-2 py-1 text-zinc-500">
            {label}
          </span>
        ))}
      </div>
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">
          请选择项目查看 Skill 注册表
        </div>
      ) : (
        <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4">
          <p className="text-sm text-zinc-300">Skill 注册表</p>
          <p className="mt-2 text-xs text-zinc-500">
            包含正式 Skill、项目临时 Skill、迭代候选。最近消费证据待后端接入。
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled
              className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
            >
              打开 Skill 注册表
            </button>
            <span className="text-[10px] text-zinc-700 self-center">
              Skill upsert API 已存在，沉淀建议待接入用户确认闭环
            </span>
          </div>
          <div className="mt-3 space-y-1">
            {[
              { name: "PRD 生成 Skill", status: "stable", evidence: null },
              { name: "前后端接口联调 Skill", status: "candidate", evidence: null },
              { name: "代码规范审查 Skill", status: "temporary", evidence: null },
            ].map((s) => (
              <div key={s.name} className="flex items-center justify-between rounded border border-[#333333] px-3 py-2 text-xs">
                <span className="text-zinc-300">{s.name}</span>
                <span className="text-zinc-600">{s.status}</span>
                <span className="text-zinc-700">暂无消费证据</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-zinc-600">
            Skill 迭代候选来源：多次失败/成功复用后 AI 建议生成。
            临时 Skill 清理策略：按使用次数、绑定角色数、最近消费时间、版本替代关系综合判断。
          </p>
        </div>
      )}
    </div>
  );
}

/* ─── Tab: 策略与权限 ─── */

const POLICY_CATEGORIES = [
  {
    category: "可自动执行",
    items: ["Worker 单次调度", "运行观测状态读取", "交付物摘要生成", "成本数据读取"],
  },
  {
    category: "需要用户确认",
    items: ["生成作战计划", "调整任务优先级", "角色/Skill 沉淀建议", "项目阶段推进"],
  },
  {
    category: "禁止自动执行",
    items: [
      "git commit",
      "git push",
      "发布生产",
      "删除项目",
      "删除交付物",
      "覆盖 Provider Key",
      "删除运行证据",
      "永久删除稳定 Skill / 角色模板",
    ],
  },
];

function PolicyTab() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        策略与权限 · 区分 AI 可自动执行、需确认、禁止自动执行三类动作
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {POLICY_CATEGORIES.map((cat) => (
          <div key={cat.category} className="rounded border border-[#333333] bg-[#1a1a1a] p-4">
            <h3 className="text-sm font-medium text-zinc-200 mb-2">{cat.category}</h3>
            <ul className="space-y-1.5">
              {cat.items.map((item) => (
                <li key={item} className="text-xs text-zinc-500">{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-zinc-600">
        策略配置基于产品基线文档静态定义。动态权限引擎与实时策略覆盖待后端接入。
      </p>
    </div>
  );
}

/* ─── Tab: 成本与记忆 ─── */

function CostMemoryTab({ hasProject }: { hasProject: boolean }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        成本与记忆 · 成本来源可信度标注 · 记忆生命周期管理
      </p>
      {!hasProject ? (
        <div className="rounded border border-[#333333] px-4 py-6 text-sm text-zinc-500 text-center">
          请选择项目查看成本与记忆摘要
        </div>
      ) : (
        <div className="space-y-4">
          {/* Cost summary */}
          <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4">
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
              成本概览
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "来源可信度", value: "heuristic", note: "基于前端估算" },
                { label: "日预算", value: "$0.05", note: "默认配置" },
                { label: "会话预算", value: "$0.20", note: "默认配置" },
              ].map((c) => (
                <div key={c.label} className="rounded border border-[#333333] px-3 py-2 text-center">
                  <div className="text-[10px] text-zinc-500">{c.label}</div>
                  <div className="text-sm font-medium text-zinc-300 mt-0.5">{c.value}</div>
                  <div className="text-[10px] text-zinc-600 mt-0.5">{c.note}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-zinc-600">
              成本数据来源可信度：provider_reported（提供商上报）/ heuristic（启发估算）/ missing（缺失）。
              页面打开不触发 AI 生成。
            </p>
          </div>

          {/* Memory summary */}
          <div className="rounded border border-[#333333] bg-[#1a1a1a] p-4">
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
              记忆状态
            </h3>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled
                className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
              >
                Compact
              </button>
              <button
                type="button"
                disabled
                className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
              >
                Rehydrate
              </button>
              <button
                type="button"
                disabled
                className="rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-600 cursor-not-allowed"
              >
                Reset
              </button>
            </div>
            <p className="mt-2 text-[11px] text-zinc-600">
              Compact / Rehydrate / Reset 无真实后端闭环，按钮已禁用。记忆管理待后端接入。
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
