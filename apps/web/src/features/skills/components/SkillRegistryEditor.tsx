import { StatusBadge } from "../../../components/StatusBadge";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { SkillRegistrySkill } from "../types";
import { SKILL_REGISTRY_ROLE_OPTIONS } from "./skillRegistryRoleOptions";
import type { SkillDraft } from "./skillRegistryDraft";

type SkillRegistryEditorProps = {
  draft: SkillDraft;
  isSaving: boolean;
  selectedSkill: SkillRegistrySkill | null;
  onCreateSkill: () => void;
  onSaveSkill: () => void;
  onToggleRole: (roleCode: string) => void;
  onUpdateDraft: (patch: Partial<SkillDraft>) => void;
};

export function SkillRegistryEditor(props: SkillRegistryEditorProps) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <SkillRegistryEditorHeader selectedSkill={props.selectedSkill} />

      <div className="mt-4 space-y-4">
        <SkillTextInput
          label="Skill Code"
          value={props.draft.code}
          placeholder="例如 quality_gate"
          onChange={(code) => props.onUpdateDraft({ code })}
        />
        <SkillTextInput
          label="名称"
          value={props.draft.name}
          placeholder="例如 质量闸门"
          onChange={(name) => props.onUpdateDraft({ name })}
        />
        <SkillTextInput
          label="当前版本"
          value={props.draft.version}
          placeholder="例如 1.0.0"
          onChange={(version) => props.onUpdateDraft({ version })}
        />
        <SkillTextarea
          label="摘要"
          value={props.draft.summary}
          rows={3}
          placeholder="一句话说明这个 Skill 解决什么问题"
          onChange={(summary) => props.onUpdateDraft({ summary })}
        />
        <SkillTextarea
          label="用途说明"
          value={props.draft.purpose}
          rows={5}
          placeholder="描述这个 Skill 的用途、边界和适合在哪个阶段使用"
          onChange={(purpose) => props.onUpdateDraft({ purpose })}
        />

        <SkillRoleCheckboxes draft={props.draft} onToggleRole={props.onToggleRole} />

        <label className="flex items-center gap-3 border-l border-[#333333] py-3 pl-3 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={props.draft.enabled}
            onChange={(event) => props.onUpdateDraft({ enabled: event.target.checked })}
            className="h-4 w-4 rounded border-zinc-600 bg-transparent text-zinc-200"
          />
          <span>Skill 当前可用于角色绑定</span>
        </label>

        <SkillTextarea
          label="版本备注"
          value={props.draft.change_note}
          rows={3}
          placeholder="如果这次提升了版本，可以说明改动原因和影响面"
          onChange={(change_note) => props.onUpdateDraft({ change_note })}
        />

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={props.onSaveSkill}
            disabled={props.isSaving}
            className="rounded border border-[#3a3a3a] bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.isSaving ? "保存中..." : "保存 Skill"}
          </button>
          <button
            type="button"
            onClick={props.onCreateSkill}
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            清空编辑器
          </button>
        </div>
      </div>
    </section>
  );
}

function SkillRegistryEditorHeader(props: { selectedSkill: SkillRegistrySkill | null }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <div className="text-lg font-semibold text-zinc-50">
          {props.selectedSkill ? "编辑 Skill" : "创建新 Skill"}
        </div>
        <div className="mt-1 text-sm leading-6 text-zinc-500">
          更新 version 时会新增版本记录；后续项目仍可回看自己绑定的是哪一个版本 Skill。
        </div>
      </div>
      {props.selectedSkill ? (
        <StatusBadge label={`当前编辑：${props.selectedSkill.name}`} tone="info" />
      ) : null}
    </div>
  );
}

function SkillTextInput(props: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm text-zinc-300">
      <div className="mb-2 font-medium text-zinc-100">{props.label}</div>
      <input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        placeholder={props.placeholder}
        className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-zinc-100 outline-none transition focus:border-zinc-500"
      />
    </label>
  );
}

function SkillTextarea(props: {
  label: string;
  value: string;
  rows: number;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm text-zinc-300">
      <div className="mb-2 font-medium text-zinc-100">{props.label}</div>
      <textarea
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        rows={props.rows}
        placeholder={props.placeholder}
        className="w-full rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-zinc-100 outline-none transition focus:border-zinc-500"
      />
    </label>
  );
}

function SkillRoleCheckboxes(props: {
  draft: SkillDraft;
  onToggleRole: (roleCode: string) => void;
}) {
  return (
    <div>
      <div className="text-sm font-medium text-zinc-100">适用角色</div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {SKILL_REGISTRY_ROLE_OPTIONS.map((roleCode) => {
          const checked = props.draft.applicable_role_codes.includes(roleCode);
          return (
            <label
              key={roleCode}
              className={`flex items-center gap-3 border-l px-3 py-2 text-sm transition ${
                checked
                  ? "border-zinc-300 text-zinc-100"
                  : "border-[#333333] text-zinc-400"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => props.onToggleRole(roleCode)}
                className="h-4 w-4 rounded border-zinc-600 bg-transparent text-zinc-200"
              />
              <span>{ROLE_CODE_LABELS[roleCode] ?? roleCode}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}