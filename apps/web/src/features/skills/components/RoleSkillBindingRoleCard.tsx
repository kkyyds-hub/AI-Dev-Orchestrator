import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { ProjectRoleBoundSkill, ProjectRoleSkillBindingGroup, SkillRegistrySkill } from "../types";
import { SKILL_BINDING_SOURCE_LABELS } from "../types";

type RoleSkillBindingRoleCardProps = {
  applicableSkills: SkillRegistrySkill[];
  draftSkillCodes: string[];
  isEditing: boolean;
  isSaving: boolean;
  role: ProjectRoleSkillBindingGroup;
  onCancelEdit: () => void;
  onEditRole: (role: ProjectRoleSkillBindingGroup) => void;
  onSaveRoleBindings: () => void;
  onToggleSkillCode: (skillCode: string) => void;
};

export function RoleSkillBindingRoleCard(props: RoleSkillBindingRoleCardProps) {
  return (
    <article className="border-b border-[#333333] pb-4">
      <RoleSkillBindingRoleHeader
        isEditing={props.isEditing}
        role={props.role}
        onEditRole={props.onEditRole}
      />

      {props.role.default_skill_slots.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {props.role.default_skill_slots.map((slot) => (
            <StatusBadge key={`${props.role.role_code}-${slot}`} label={slot} tone="neutral" />
          ))}
        </div>
      ) : null}

      {props.role.skills.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
          {props.role.skills.map((skill) => (
            <BoundSkillCard key={`${props.role.role_code}-${skill.skill_code}`} skill={skill} />
          ))}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前角色还没有绑定 Skill。点击右上角“编辑绑定”即可为该角色分配能力。
        </div>
      )}

      {props.isEditing ? (
        <RoleSkillBindingEditor
          applicableSkills={props.applicableSkills}
          draftSkillCodes={props.draftSkillCodes}
          isSaving={props.isSaving}
          role={props.role}
          onCancelEdit={props.onCancelEdit}
          onSaveRoleBindings={props.onSaveRoleBindings}
          onToggleSkillCode={props.onToggleSkillCode}
        />
      ) : null}
    </article>
  );
}

function RoleSkillBindingRoleHeader(props: {
  isEditing: boolean;
  role: ProjectRoleSkillBindingGroup;
  onEditRole: (role: ProjectRoleSkillBindingGroup) => void;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-base font-medium text-zinc-50">{props.role.role_name}</div>
          <StatusBadge
            label={props.role.role_enabled ? "角色启用" : "角色停用"}
            tone={props.role.role_enabled ? "success" : "warning"}
          />
          <StatusBadge label={`${props.role.bound_skill_count} 个 Skill`} tone="info" />
        </div>
        <div className="mt-2 text-xs text-zinc-500">
          角色代码：{ROLE_CODE_LABELS[props.role.role_code] ?? props.role.role_code}
        </div>
      </div>

      <button
        type="button"
        onClick={() => props.onEditRole(props.role)}
        className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
      >
        {props.isEditing ? "正在编辑" : "编辑绑定"}
      </button>
    </div>
  );
}

function BoundSkillCard(props: { skill: ProjectRoleBoundSkill }) {
  return (
    <div className="px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-medium text-zinc-50">{props.skill.skill_name}</div>
        <StatusBadge label={`绑定 v${props.skill.bound_version}`} tone="info" />
        {props.skill.registry_current_version ? (
          <StatusBadge
            label={`注册中心 v${props.skill.registry_current_version}`}
            tone={props.skill.upgrade_available ? "warning" : "success"}
          />
        ) : null}
        <StatusBadge
          label={SKILL_BINDING_SOURCE_LABELS[props.skill.binding_source] ?? props.skill.binding_source}
          tone="neutral"
        />
      </div>
      <p className="mt-3 text-sm leading-6 text-zinc-300">{props.skill.summary}</p>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{props.skill.purpose}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {props.skill.applicable_role_codes.map((roleCode) => (
          <StatusBadge
            key={`${props.skill.skill_code}-${roleCode}`}
            label={ROLE_CODE_LABELS[roleCode] ?? roleCode}
            tone="neutral"
          />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
        <span>{props.skill.registry_enabled ? "当前可绑定" : "当前已停用"}</span>
        <span>绑定于 {formatDateTime(props.skill.created_at)}</span>
        {props.skill.upgrade_available ? (
          <span className="text-amber-300">
            发现新版本，重新保存即可同步到注册中心最新版本。
          </span>
        ) : null}
      </div>
    </div>
  );
}

function RoleSkillBindingEditor(props: {
  applicableSkills: SkillRegistrySkill[];
  draftSkillCodes: string[];
  isSaving: boolean;
  role: ProjectRoleSkillBindingGroup;
  onCancelEdit: () => void;
  onSaveRoleBindings: () => void;
  onToggleSkillCode: (skillCode: string) => void;
}) {
  return (
    <div className="mt-5 border-l border-[#333333] pl-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-zinc-100">
            编辑 {props.role.role_name} 的 Skill 绑定
          </div>
          <div className="mt-1 text-xs leading-5 text-zinc-500">
            这里只显示适用于当前角色的 Skill；重新保存后，会把所选 Skill 的最新版本绑定到该角色。
          </div>
        </div>
        <StatusBadge label={`${props.applicableSkills.length} 个可选 Skill`} tone="info" />
      </div>

      {props.applicableSkills.length > 0 ? (
        <div className="mt-4 grid gap-3">
          {props.applicableSkills.map((skill) => {
            const checked = props.draftSkillCodes.includes(skill.code);
            return (
              <label
                key={`${props.role.role_code}-${skill.code}`}
                className={`flex items-start gap-3 border-l px-3 py-3 text-sm transition ${
                  checked
                    ? "border-zinc-300 text-zinc-100"
                    : "border-[#333333] text-zinc-400"
                } ${skill.enabled ? "" : "opacity-60"}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={!skill.enabled}
                  onChange={() => props.onToggleSkillCode(skill.code)}
                  className="mt-1 h-4 w-4 rounded border-zinc-600 bg-transparent text-zinc-200"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-zinc-50">{skill.name}</span>
                    <StatusBadge label={`v${skill.current_version}`} tone="info" />
                    <StatusBadge
                      label={skill.enabled ? "可绑定" : "已停用"}
                      tone={skill.enabled ? "success" : "warning"}
                    />
                  </div>
                  <div className="mt-2 text-xs text-zinc-500">{skill.code}</div>
                  <p className="mt-2 text-sm leading-6 text-zinc-300">{skill.summary}</p>
                </div>
              </label>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前注册中心里没有适用于该角色的可选 Skill；可以先到上方注册中心新增对应 Skill。
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={props.onSaveRoleBindings}
          disabled={props.isSaving}
          className="rounded border border-[#3a3a3a] bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {props.isSaving ? "保存中..." : "保存绑定"}
        </button>
        <button
          type="button"
          onClick={props.onCancelEdit}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
        >
          取消编辑
        </button>
      </div>
    </div>
  );
}
