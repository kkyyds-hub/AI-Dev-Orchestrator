import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../../components/MetricCard";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { ROLE_CODE_LABELS } from "../roles/types";
import {
  useProjectSkillBindings,
  useSkillRegistry,
  useUpdateProjectRoleSkillBindings,
} from "./hooks";
import type { ProjectRoleSkillBindingGroup } from "./types";
import { SKILL_BINDING_SOURCE_LABELS } from "./types";

type RoleSkillBindingPanelProps = {
  projectId: string | null;
  projectName: string | null;
};

export function RoleSkillBindingPanel(props: RoleSkillBindingPanelProps) {
  const bindingQuery = useProjectSkillBindings(props.projectId);
  const registryQuery = useSkillRegistry();
  const updateBindingMutation = useUpdateProjectRoleSkillBindings(props.projectId);
  const [editingRoleCode, setEditingRoleCode] = useState<string | null>(null);
  const [draftSkillCodes, setDraftSkillCodes] = useState<string[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setEditingRoleCode(null);
    setDraftSkillCodes([]);
    setLocalError(null);
  }, [props.projectId]);

  const bindingSnapshot = bindingQuery.data ?? null;
  const registrySkills = registryQuery.data?.skills ?? [];

  const applicableSkillMap = useMemo(() => {
    const nextMap = new Map<string, typeof registrySkills>();
    for (const role of bindingSnapshot?.roles ?? []) {
      nextMap.set(
        role.role_code,
        registrySkills.filter((skill) =>
          skill.applicable_role_codes.includes(role.role_code),
        ),
      );
    }

    return nextMap;
  }, [bindingSnapshot?.roles, registrySkills]);

  const handleEditRole = (role: ProjectRoleSkillBindingGroup) => {
    setEditingRoleCode(role.role_code);
    setDraftSkillCodes(role.skills.map((skill) => skill.skill_code));
    setLocalError(null);
  };

  const handleToggleSkillCode = (skillCode: string) => {
    setDraftSkillCodes((currentCodes) =>
      currentCodes.includes(skillCode)
        ? currentCodes.filter((code) => code !== skillCode)
        : [...currentCodes, skillCode],
    );
  };

  const handleSaveRoleBindings = async () => {
    if (!editingRoleCode) {
      return;
    }

    setLocalError(null);
    try {
      await updateBindingMutation.mutateAsync({
        roleCode: editingRoleCode,
        payload: { skill_codes: draftSkillCodes },
      });
      setEditingRoleCode(null);
      setDraftSkillCodes([]);
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "角色 Skill 绑定保存失败。",
      );
    }
  };

  if (!props.projectId) {
    return (
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">角色 Skill 绑定</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          先选择项目，再查看当前项目里每个角色绑定了哪些 Skill。
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day13 Role Skill Binding
          </p>
          <h3 className="text-2xl font-semibold tracking-tight text-slate-50">
            项目详情中的角色 Skill 绑定
          </h3>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            每个角色都可以绑定一个或多个 Skill，并保留自己当前使用的版本；当注册中心里的 Skill 升级后，这里也会标出哪些绑定需要手动同步到最新版。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="当前项目"
            value={props.projectName ?? bindingSnapshot?.project_name ?? "未命名项目"}
            hint="当前展示的项目详情"
            tone="info"
          />
          <MetricCard
            label="角色数"
            value={String(bindingSnapshot?.total_roles ?? 0)}
            hint="项目角色目录中的总角色数"
          />
          <MetricCard
            label="绑定 Skill"
            value={String(bindingSnapshot?.total_bound_skills ?? 0)}
            hint="当前项目所有角色累计绑定的 Skill 数量"
            tone="success"
          />
          <MetricCard
            label="待升级绑定"
            value={String(bindingSnapshot?.outdated_binding_count ?? 0)}
            hint="当前绑定版本落后于注册中心最新版本的 Skill 数量"
            tone="warning"
          />
        </div>
      </header>

      {bindingQuery.isLoading && !bindingSnapshot ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          正在加载项目角色 Skill 绑定...
        </div>
      ) : null}

      {bindingQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          项目 Skill 绑定加载失败：{bindingQuery.error.message}
        </div>
      ) : null}

      {registryQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          Skill 注册中心加载失败：{registryQuery.error.message}
        </div>
      ) : null}

      {localError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          {localError}
        </div>
      ) : null}

      {bindingSnapshot ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {bindingSnapshot.roles.map((role) => {
            const isEditing = editingRoleCode === role.role_code;
            const applicableSkills = applicableSkillMap.get(role.role_code) ?? [];
            return (
              <article
                key={role.role_code}
                className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-lg font-medium text-slate-50">
                        {role.role_name}
                      </div>
                      <StatusBadge
                        label={role.role_enabled ? "角色启用" : "角色停用"}
                        tone={role.role_enabled ? "success" : "warning"}
                      />
                      <StatusBadge
                        label={`${role.bound_skill_count} 个 Skill`}
                        tone="info"
                      />
                    </div>
                    <div className="mt-2 text-xs text-slate-500">
                      角色代码：{ROLE_CODE_LABELS[role.role_code] ?? role.role_code}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleEditRole(role)}
                    className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
                  >
                    {isEditing ? "正在编辑" : "编辑绑定"}
                  </button>
                </div>

                {role.default_skill_slots.length > 0 ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {role.default_skill_slots.map((slot) => (
                      <StatusBadge key={`${role.role_code}-${slot}`} label={slot} tone="neutral" />
                    ))}
                  </div>
                ) : null}

                {role.skills.length > 0 ? (
                  <div className="mt-4 space-y-3">
                    {role.skills.map((skill) => (
                      <div
                        key={`${role.role_code}-${skill.skill_code}`}
                        className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-medium text-slate-50">
                            {skill.skill_name}
                          </div>
                          <StatusBadge label={`绑定 v${skill.bound_version}`} tone="info" />
                          {skill.registry_current_version ? (
                            <StatusBadge
                              label={`注册中心 v${skill.registry_current_version}`}
                              tone={skill.upgrade_available ? "warning" : "success"}
                            />
                          ) : null}
                          <StatusBadge
                            label={
                              SKILL_BINDING_SOURCE_LABELS[skill.binding_source] ?? skill.binding_source
                            }
                            tone="neutral"
                          />
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-300">{skill.summary}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-400">{skill.purpose}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {skill.applicable_role_codes.map((roleCode) => (
                            <StatusBadge
                              key={`${skill.skill_code}-${roleCode}`}
                              label={ROLE_CODE_LABELS[roleCode] ?? roleCode}
                              tone="neutral"
                            />
                          ))}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                          <span>{skill.registry_enabled ? "当前可绑定" : "当前已停用"}</span>
                          <span>绑定于 {formatDateTime(skill.created_at)}</span>
                          {skill.upgrade_available ? (
                            <span className="text-amber-300">
                              发现新版本，重新保存即可同步到注册中心最新版本。
                            </span>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
                    当前角色还没有绑定 Skill。点击右上角“编辑绑定”即可为该角色分配能力。
                  </div>
                )}

                {isEditing ? (
                  <div className="mt-5 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-cyan-100">
                          编辑 {role.role_name} 的 Skill 绑定
                        </div>
                        <div className="mt-1 text-xs leading-5 text-cyan-200/80">
                          这里只显示适用于当前角色的 Skill；重新保存后，会把所选 Skill 的最新版本绑定到该角色。
                        </div>
                      </div>
                      <StatusBadge
                        label={`${applicableSkills.length} 个可选 Skill`}
                        tone="info"
                      />
                    </div>

                    {applicableSkills.length > 0 ? (
                      <div className="mt-4 grid gap-3">
                        {applicableSkills.map((skill) => {
                          const checked = draftSkillCodes.includes(skill.code);
                          return (
                            <label
                              key={`${role.role_code}-${skill.code}`}
                              className={`flex items-start gap-3 rounded-xl border px-3 py-3 text-sm transition ${
                                checked
                                  ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-100"
                                  : "border-slate-800 bg-slate-950/60 text-slate-300"
                              } ${skill.enabled ? "" : "opacity-60"}`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={!skill.enabled}
                                onChange={() => handleToggleSkillCode(skill.code)}
                                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
                              />
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="font-medium text-slate-50">{skill.name}</span>
                                  <StatusBadge label={`v${skill.current_version}`} tone="info" />
                                  <StatusBadge
                                    label={skill.enabled ? "可绑定" : "已停用"}
                                    tone={skill.enabled ? "success" : "warning"}
                                  />
                                </div>
                                <div className="mt-2 text-xs text-slate-500">{skill.code}</div>
                                <p className="mt-2 text-sm leading-6 text-slate-300">{skill.summary}</p>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="mt-4 rounded-2xl border border-dashed border-cyan-500/20 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-300">
                        当前注册中心里没有适用于该角色的可选 Skill；可以先到上方注册中心新增对应 Skill。
                      </div>
                    )}

                    <div className="mt-4 flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={handleSaveRoleBindings}
                        disabled={updateBindingMutation.isPending}
                        className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {updateBindingMutation.isPending ? "保存中..." : "保存绑定"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingRoleCode(null);
                          setDraftSkillCodes([]);
                          setLocalError(null);
                        }}
                        className="rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500"
                      >
                        取消编辑
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
