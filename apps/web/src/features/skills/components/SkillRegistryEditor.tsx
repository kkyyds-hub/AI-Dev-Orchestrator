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
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
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

        <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-3 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={props.draft.enabled}
            onChange={(event) => props.onUpdateDraft({ enabled: event.target.checked })}
            className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
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
            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {props.isSaving ? "保存中..." : "保存 Skill"}
          </button>
          <button
            type="button"
            onClick={props.onCreateSkill}
            className="rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500"
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
        <div className="text-sm font-medium text-slate-100">
          {props.selectedSkill ? "编辑 Skill" : "创建新 Skill"}
        </div>
        <div className="mt-1 text-xs leading-5 text-slate-400">
          更新 version 时会新增版本记录；后续项目仍可回看自己绑定的是哪一版 Skill。
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
    <label className="block text-sm text-slate-300">
      <div className="mb-2 font-medium text-slate-100">{props.label}</div>
      <input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        placeholder={props.placeholder}
        className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
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
    <label className="block text-sm text-slate-300">
      <div className="mb-2 font-medium text-slate-100">{props.label}</div>
      <textarea
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        rows={props.rows}
        placeholder={props.placeholder}
        className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none transition focus:border-cyan-400/50"
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
      <div className="text-sm font-medium text-slate-100">适用角色</div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {SKILL_REGISTRY_ROLE_OPTIONS.map((roleCode) => {
          const checked = props.draft.applicable_role_codes.includes(roleCode);
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
                onChange={() => props.onToggleRole(roleCode)}
                className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
              />
              <span>{ROLE_CODE_LABELS[roleCode] ?? roleCode}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
