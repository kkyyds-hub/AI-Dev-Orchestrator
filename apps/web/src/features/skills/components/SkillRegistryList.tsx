import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { SkillRegistrySkill } from "../types";

type SkillRegistryListProps = {
  isLoading: boolean;
  registryLoaded: boolean;
  selectedSkillCode: string | null;
  skills: SkillRegistrySkill[];
  onCreateSkill: () => void;
  onSelectSkill: (skill: SkillRegistrySkill) => void;
};

export function SkillRegistryList(props: SkillRegistryListProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <SkillRegistryListHeader onCreateSkill={props.onCreateSkill} />

      {props.isLoading && !props.registryLoaded ? (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400">
          正在加载 Skill 注册中心...
        </div>
      ) : props.skills.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.skills.map((skill) => (
            <SkillRegistryListItem
              key={skill.id}
              skill={skill}
              isActive={props.selectedSkillCode === skill.code}
              onSelectSkill={props.onSelectSkill}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 px-4 py-8 text-center text-sm leading-6 text-slate-400">
          当前还没有 Skill；可以使用右侧编辑器创建第一条注册能力。
        </div>
      )}
    </section>
  );
}

function SkillRegistryListHeader(props: { onCreateSkill: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <div className="text-sm font-medium text-slate-100">注册中的 Skill</div>
        <div className="mt-1 text-xs leading-5 text-slate-400">
          在这里查看当前 Skill 的启停状态、适用角色和版本历史；需要新能力时可以新增 Skill 并立即纳入项目绑定面板。
        </div>
      </div>
      <button
        type="button"
        onClick={props.onCreateSkill}
        className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
      >
        新建 Skill
      </button>
    </div>
  );
}

function SkillRegistryListItem(props: {
  skill: SkillRegistrySkill;
  isActive: boolean;
  onSelectSkill: (skill: SkillRegistrySkill) => void;
}) {
  const historyTail = props.skill.version_history.slice(-3).reverse();

  return (
    <article
      className={`rounded-2xl border px-4 py-4 transition ${
        props.isActive ? "border-cyan-500/40 bg-cyan-500/10" : "border-slate-800 bg-slate-950/60"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-base font-medium text-slate-50">{props.skill.name}</div>
            <StatusBadge label={`v${props.skill.current_version}`} tone="info" />
            <StatusBadge
              label={props.skill.enabled ? "已启用" : "已停用"}
              tone={props.skill.enabled ? "success" : "warning"}
            />
          </div>
          <div className="mt-2 text-xs text-slate-500">{props.skill.code}</div>
          <p className="mt-3 text-sm leading-6 text-slate-300">{props.skill.summary}</p>
        </div>

        <button
          type="button"
          onClick={() => props.onSelectSkill(props.skill)}
          className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-100 transition hover:border-cyan-400/40 hover:text-cyan-100"
        >
          {props.isActive ? "正在编辑" : "编辑 Skill"}
        </button>
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-400">{props.skill.purpose}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {props.skill.applicable_role_codes.map((roleCode) => (
          <StatusBadge
            key={`${props.skill.code}-${roleCode}`}
            label={ROLE_CODE_LABELS[roleCode] ?? roleCode}
            tone="neutral"
          />
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
        <span>创建于 {formatDateTime(props.skill.created_at)}</span>
        <span>更新于 {formatDateTime(props.skill.updated_at)}</span>
        <span>历史版本 {props.skill.version_history.length} 条</span>
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
}
