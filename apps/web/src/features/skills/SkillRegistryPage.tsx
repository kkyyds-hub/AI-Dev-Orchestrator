import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../../components/MetricCard";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { ROLE_CODE_LABELS } from "../roles/types";
import { RoleSkillBindingPanel } from "./RoleSkillBindingPanel";
import { useProjectSkillBindings, useSkillRegistry, useUpsertSkill } from "./hooks";
import type { SkillRegistrySkill, SkillUpsertInput } from "./types";

const ROLE_OPTIONS = [
  "product_manager",
  "architect",
  "engineer",
  "reviewer",
] as const;

type SkillRegistryPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
};

type SkillDraft = {
  code: string;
  name: string;
  summary: string;
  purpose: string;
  applicable_role_codes: string[];
  enabled: boolean;
  version: string;
  change_note: string;
};

const EMPTY_DRAFT: SkillDraft = {
  code: "",
  name: "",
  summary: "",
  purpose: "",
  applicable_role_codes: [],
  enabled: true,
  version: "1.0.0",
  change_note: "",
};

const NEW_SKILL_SENTINEL = "__new__";

export function SkillRegistryPage(props: SkillRegistryPageProps) {
  const registryQuery = useSkillRegistry();
  const bindingQuery = useProjectSkillBindings(props.selectedProjectId);
  const upsertSkillMutation = useUpsertSkill();
  const [editingSkillCode, setEditingSkillCode] = useState<string | null>(null);
  const [draft, setDraft] = useState<SkillDraft>(EMPTY_DRAFT);
  const [formError, setFormError] = useState<string | null>(null);

  const registry = registryQuery.data;
  const skills = registry?.skills ?? [];
  const selectedSkill =
    skills.find((skill) => skill.code === editingSkillCode) ?? null;

  useEffect(() => {
    if (editingSkillCode !== null) {
      return;
    }

    if (skills.length === 0) {
      return;
    }

    setEditingSkillCode(skills[0].code);
    setDraft(buildSkillDraft(skills[0]));
  }, [editingSkillCode, skills]);

  const enabledSkillRatio = useMemo(() => {
    if (!registry || registry.total_skill_count === 0) {
      return "0 / 0";
    }

    return `${registry.enabled_skill_count} / ${registry.total_skill_count}`;
  }, [registry]);

  const handleSelectSkill = (skill: SkillRegistrySkill) => {
    setEditingSkillCode(skill.code);
    setDraft(buildSkillDraft(skill));
    setFormError(null);
  };

  const handleCreateSkill = () => {
    setEditingSkillCode(NEW_SKILL_SENTINEL);
    setDraft(EMPTY_DRAFT);
    setFormError(null);
  };

  const handleToggleRole = (roleCode: string) => {
    setDraft((currentDraft) => ({
      ...currentDraft,
      applicable_role_codes: currentDraft.applicable_role_codes.includes(roleCode)
        ? currentDraft.applicable_role_codes.filter((code) => code !== roleCode)
        : [...currentDraft.applicable_role_codes, roleCode],
    }));
  };

  const handleSave = async () => {
    const normalizedCode = normalizeSkillCode(draft.code);
    if (!normalizedCode) {
      setFormError("请先填写 Skill code。建议使用英文小写和下划线。");
      return;
    }

    if (draft.applicable_role_codes.length === 0) {
      setFormError("请至少选择一个适用角色。");
      return;
    }

    setFormError(null);

    const payload: SkillUpsertInput = {
      name: draft.name,
      summary: draft.summary,
      purpose: draft.purpose,
      applicable_role_codes: draft.applicable_role_codes,
      enabled: draft.enabled,
      version: draft.version,
      change_note: draft.change_note.trim() || null,
    };

    try {
      const savedSkill = await upsertSkillMutation.mutateAsync({
        skillCode: normalizedCode,
        payload,
      });
      setEditingSkillCode(savedSkill.code);
      setDraft(buildSkillDraft(savedSkill));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Skill 保存失败。");
    }
  };

  return (
    <section className="space-y-6 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day13 Skill Registry
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
            Skill 注册中心与角色绑定
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            Day13 把 Day05 的默认 Skill 槽位升级为正式注册中心：Skill 具备名称、版本、用途、适用角色和启停状态，并且可以在项目内绑定到具体角色。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <StatusBadge
            label={props.selectedProjectName ? `当前项目：${props.selectedProjectName}` : "当前未选项目"}
            tone={props.selectedProjectName ? "info" : "neutral"}
          />
          <StatusBadge
            label={registry ? `已加载 ${registry.total_skill_count} 个 Skill` : "注册中心加载中"}
            tone={registry ? "success" : "warning"}
          />
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Skill 总数"
          value={String(registry?.total_skill_count ?? 0)}
          hint="正式注册到 Day13 Skill 中心的能力条目"
          tone="info"
        />
        <MetricCard
          label="已启用"
          value={enabledSkillRatio}
          hint="当前可用于角色绑定的 Skill / 全部 Skill"
          tone="success"
        />
        <MetricCard
          label="版本记录"
          value={String(registry?.version_record_count ?? 0)}
          hint="用于回看 Skill 变更历史和项目所用版本"
          tone="warning"
        />
        <MetricCard
          label="当前项目绑定"
          value={String(bindingQuery.data?.total_bound_skills ?? 0)}
          hint={props.selectedProjectName ? "当前项目所有角色累计绑定的 Skill 数" : "选择项目后可查看角色绑定情况"}
        />
      </div>

      {registryQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          Skill 注册中心加载失败：{registryQuery.error.message}
        </div>
      ) : null}

      {formError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          {formError}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[1.08fr_0.92fr]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-slate-100">注册中的 Skill</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">
                在这里查看当前 Skill 的启停状态、适用角色和版本历史；需要新能力时可以新增 Skill 并立即纳入项目绑定面板。
              </div>
            </div>
            <button
              type="button"
              onClick={handleCreateSkill}
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
            >
              新建 Skill
            </button>
          </div>

          {registryQuery.isLoading && !registry ? (
            <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
              正在加载 Skill 注册中心...
            </div>
          ) : skills.length > 0 ? (
            <div className="mt-4 space-y-3">
              {skills.map((skill) => {
                const historyTail = skill.version_history.slice(-3).reverse();
                const isActive = selectedSkill?.code === skill.code;
                return (
                  <article
                    key={skill.id}
                    className={`rounded-2xl border px-4 py-4 transition ${
                      isActive
                        ? "border-cyan-500/40 bg-cyan-500/10"
                        : "border-slate-800 bg-slate-950/60"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-base font-medium text-slate-50">
                            {skill.name}
                          </div>
                          <StatusBadge
                            label={`v${skill.current_version}`}
                            tone="info"
                          />
                          <StatusBadge
                            label={skill.enabled ? "已启用" : "已停用"}
                            tone={skill.enabled ? "success" : "warning"}
                          />
                        </div>
                        <div className="mt-2 text-xs text-slate-500">{skill.code}</div>
                        <p className="mt-3 text-sm leading-6 text-slate-300">{skill.summary}</p>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleSelectSkill(skill)}
                        className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-100 transition hover:border-cyan-400/40 hover:text-cyan-100"
                      >
                        {isActive ? "正在编辑" : "编辑 Skill"}
                      </button>
                    </div>

                    <p className="mt-3 text-sm leading-6 text-slate-400">{skill.purpose}</p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {skill.applicable_role_codes.map((roleCode) => (
                        <StatusBadge
                          key={`${skill.code}-${roleCode}`}
                          label={ROLE_CODE_LABELS[roleCode] ?? roleCode}
                          tone="neutral"
                        />
                      ))}
                    </div>

                    <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                      <span>创建于 {formatDateTime(skill.created_at)}</span>
                      <span>更新于 {formatDateTime(skill.updated_at)}</span>
                      <span>历史版本 {skill.version_history.length} 条</span>
                    </div>

                    {historyTail.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        {historyTail.map((record) => (
                          <div
                            key={record.id}
                            className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-3 text-sm"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <StatusBadge label={`v${record.version}`} tone="info" />
                              <StatusBadge
                                label={record.enabled ? "启用" : "停用"}
                                tone={record.enabled ? "success" : "warning"}
                              />
                              <span className="text-xs text-slate-500">
                                {formatDateTime(record.created_at)}
                              </span>
                            </div>
                            {record.change_note ? (
                              <p className="mt-2 text-sm leading-6 text-slate-300">
                                {record.change_note}
                              </p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 px-4 py-8 text-center text-sm leading-6 text-slate-400">
              当前还没有 Skill；可以使用右侧编辑器创建第一条注册能力。
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-slate-100">
                {selectedSkill ? "编辑 Skill" : "创建新 Skill"}
              </div>
              <div className="mt-1 text-xs leading-5 text-slate-400">
                更新 version 时会新增版本记录；后续项目仍可回看自己绑定的是哪一版 Skill。
              </div>
            </div>
            {selectedSkill ? (
              <StatusBadge
                label={`当前编辑：${selectedSkill.name}`}
                tone="info"
              />
            ) : null}
          </div>

          <div className="mt-4 space-y-4">
            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">Skill Code</div>
              <input
                value={draft.code}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    code: event.target.value,
                  }))
                }
                placeholder="例如 quality_gate"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">名称</div>
              <input
                value={draft.name}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    name: event.target.value,
                  }))
                }
                placeholder="例如 质量闸门"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">当前版本</div>
              <input
                value={draft.version}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    version: event.target.value,
                  }))
                }
                placeholder="例如 1.0.0"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">摘要</div>
              <textarea
                value={draft.summary}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    summary: event.target.value,
                  }))
                }
                rows={3}
                placeholder="一句话说明这个 Skill 解决什么问题"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">用途说明</div>
              <textarea
                value={draft.purpose}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    purpose: event.target.value,
                  }))
                }
                rows={5}
                placeholder="描述这个 Skill 的用途、边界和适合在哪个阶段使用"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <div>
              <div className="text-sm font-medium text-slate-100">适用角色</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {ROLE_OPTIONS.map((roleCode) => {
                  const checked = draft.applicable_role_codes.includes(roleCode);
                  return (
                    <label
                      key={roleCode}
                      className={`flex items-center gap-3 rounded-xl border px-3 py-3 text-sm transition ${
                        checked
                          ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-100"
                          : "border-slate-800 bg-slate-950/40 text-slate-300"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => handleToggleRole(roleCode)}
                        className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
                      />
                      <span>{ROLE_CODE_LABELS[roleCode] ?? roleCode}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-3 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    enabled: event.target.checked,
                  }))
                }
                className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
              />
              <span>Skill 当前可用于角色绑定</span>
            </label>

            <label className="block text-sm text-slate-300">
              <div className="mb-2 font-medium text-slate-100">版本备注</div>
              <textarea
                value={draft.change_note}
                onChange={(event) =>
                  setDraft((currentDraft) => ({
                    ...currentDraft,
                    change_note: event.target.value,
                  }))
                }
                rows={3}
                placeholder="如果这次提升了版本，可以说明改动原因和影响面"
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </label>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleSave}
                disabled={upsertSkillMutation.isPending}
                className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {upsertSkillMutation.isPending ? "保存中..." : "保存 Skill"}
              </button>
              <button
                type="button"
                onClick={handleCreateSkill}
                className="rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500"
              >
                清空编辑器
              </button>
            </div>
          </div>
        </section>
      </div>

      <RoleSkillBindingPanel
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />
    </section>
  );
}

function buildSkillDraft(skill: SkillRegistrySkill): SkillDraft {
  return {
    code: skill.code,
    name: skill.name,
    summary: skill.summary,
    purpose: skill.purpose,
    applicable_role_codes: [...skill.applicable_role_codes],
    enabled: skill.enabled,
    version: skill.current_version,
    change_note: "",
  };
}

function normalizeSkillCode(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}
