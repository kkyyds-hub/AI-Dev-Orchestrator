import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import type {
  ProjectRoleConfig,
  ProjectRoleUpdateInput,
  SystemRoleCatalogItem,
} from "./types";

type RoleEditorDrawerProps = {
  open: boolean;
  role: ProjectRoleConfig | null;
  systemRole: SystemRoleCatalogItem | null;
  projectName: string | null;
  isSaving: boolean;
  onClose: () => void;
  onSave: (payload: ProjectRoleUpdateInput) => Promise<void>;
};

export function RoleEditorDrawer(props: RoleEditorDrawerProps) {
  const [enabled, setEnabled] = useState(true);
  const [name, setName] = useState("");
  const [summary, setSummary] = useState("");
  const [responsibilitiesText, setResponsibilitiesText] = useState("");
  const [inputBoundaryText, setInputBoundaryText] = useState("");
  const [outputBoundaryText, setOutputBoundaryText] = useState("");
  const [skillSlotsText, setSkillSlotsText] = useState("");
  const [customNotes, setCustomNotes] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!props.role) {
      setEnabled(true);
      setName("");
      setSummary("");
      setResponsibilitiesText("");
      setInputBoundaryText("");
      setOutputBoundaryText("");
      setSkillSlotsText("");
      setCustomNotes("");
      setErrorMessage(null);
      return;
    }

    setEnabled(props.role.enabled);
    setName(props.role.name);
    setSummary(props.role.summary);
    setResponsibilitiesText(props.role.responsibilities.join("\n"));
    setInputBoundaryText(props.role.input_boundary.join("\n"));
    setOutputBoundaryText(props.role.output_boundary.join("\n"));
    setSkillSlotsText(props.role.default_skill_slots.join("\n"));
    setCustomNotes(props.role.custom_notes ?? "");
    setErrorMessage(null);
  }, [props.role]);

  const roleLabel = useMemo(() => {
    if (props.role) {
      return props.role.name;
    }

    return props.systemRole?.name ?? "角色";
  }, [props.role, props.systemRole]);

  if (!props.open || !props.role) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    const currentRole = props.role;
    if (!currentRole) {
      setErrorMessage("当前没有可保存的角色配置。");
      return;
    }

    const payload: ProjectRoleUpdateInput = {
      enabled,
      name: name.trim(),
      summary: summary.trim(),
      responsibilities: parseLineItems(responsibilitiesText),
      input_boundary: parseLineItems(inputBoundaryText),
      output_boundary: parseLineItems(outputBoundaryText),
      default_skill_slots: parseLineItems(skillSlotsText),
      custom_notes: customNotes.trim() ? customNotes.trim() : null,
      sort_order: currentRole.sort_order,
    };

    if (
      !payload.name ||
      !payload.summary ||
      payload.responsibilities.length === 0 ||
      payload.input_boundary.length === 0 ||
      payload.output_boundary.length === 0 ||
      payload.default_skill_slots.length === 0
    ) {
      setErrorMessage("名称、摘要、职责、输入/输出边界和 Skill 占位都需要填写。");
      return;
    }

    try {
      await props.onSave(payload);
      props.onClose();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "角色配置保存失败，请稍后重试。",
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/75 backdrop-blur-sm">
      <button
        type="button"
        aria-label="关闭角色编辑抽屉"
        className="flex-1 cursor-default"
        onClick={props.onClose}
      />

      <aside className="flex h-full w-full max-w-2xl flex-col border-l border-slate-800 bg-slate-950 shadow-2xl shadow-slate-950/70">
        <header className="border-b border-slate-800 px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-cyan-300">
                Day05 Role Config
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-slate-50">
                {roleLabel}
              </h2>
            </div>

            <div className="flex flex-wrap gap-2">
              <StatusBadge
                label={enabled ? "已启用" : "未启用"}
                tone={enabled ? "success" : "neutral"}
              />
              <StatusBadge label={props.role.role_code} tone="info" />
            </div>
          </div>

          <p className="mt-3 text-sm leading-6 text-slate-300">
            当前项目：
            <span className="font-medium text-slate-100">
              {props.projectName ?? "未选择项目"}
            </span>
            。这里只编辑 Day05 的角色目录与身份配置，不涉及 SOP、角色调度或 Skill
            引擎。
          </p>
        </header>

        <form
          className="flex flex-1 flex-col overflow-hidden"
          onSubmit={handleSubmit}
        >
          <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
            <label className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-4">
              <div>
                <div className="text-sm font-medium text-slate-100">项目启用状态</div>
                <div className="mt-1 text-xs leading-5 text-slate-400">
                  Day05 只维护角色是否在当前项目中启用，不触发任何调度行为。
                </div>
              </div>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
                className="h-5 w-5 rounded border-slate-700 bg-slate-950 text-cyan-400 focus:ring-cyan-400"
              />
            </label>

            <FieldBlock
              label="角色名称"
              description="可在当前项目中覆盖系统默认角色名。"
            >
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
              />
            </FieldBlock>

            <FieldBlock
              label="角色摘要"
              description="一句话说明这个角色在项目中承担什么职责。"
            >
              <textarea
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                rows={3}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
              />
            </FieldBlock>

            <div className="grid gap-6 lg:grid-cols-2">
              <FieldBlock
                label="职责边界"
                description="每行一条职责，保存时会自动去重。"
              >
                <textarea
                  value={responsibilitiesText}
                  onChange={(event) => setResponsibilitiesText(event.target.value)}
                  rows={6}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                />
              </FieldBlock>

              <FieldBlock
                label="默认 Skill 占位"
                description="这里只是占位标签，不会接入 Day13 的 Skill 引擎。"
              >
                <textarea
                  value={skillSlotsText}
                  onChange={(event) => setSkillSlotsText(event.target.value)}
                  rows={6}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                />
              </FieldBlock>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <FieldBlock
                label="输入边界"
                description="当前角色接手前应该已经具备哪些输入。"
              >
                <textarea
                  value={inputBoundaryText}
                  onChange={(event) => setInputBoundaryText(event.target.value)}
                  rows={6}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                />
              </FieldBlock>

              <FieldBlock
                label="输出边界"
                description="当前角色完成后应该留下哪些结果给下游。"
              >
                <textarea
                  value={outputBoundaryText}
                  onChange={(event) => setOutputBoundaryText(event.target.value)}
                  rows={6}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
                />
              </FieldBlock>
            </div>

            <FieldBlock
              label="项目备注"
              description="记录当前项目对该角色的额外说明、协作禁区或特别要求。"
            >
              <textarea
                value={customNotes}
                onChange={(event) => setCustomNotes(event.target.value)}
                rows={4}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400"
              />
            </FieldBlock>

            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-xs leading-6 text-slate-400">
              <div>系统默认名称：{props.systemRole?.name ?? "—"}</div>
              <div>默认启用：{props.systemRole?.enabled_by_default ? "是" : "否"}</div>
              <div>
                上次更新：
                <span className="text-slate-300">
                  {formatDateTime(props.role.updated_at)}
                </span>
              </div>
            </section>

            {errorMessage ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
                {errorMessage}
              </div>
            ) : null}
          </div>

          <footer className="flex items-center justify-between gap-3 border-t border-slate-800 px-6 py-4">
            <button
              type="button"
              onClick={props.onClose}
              className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
            >
              取消
            </button>

            <button
              type="submit"
              disabled={props.isSaving}
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
            >
              {props.isSaving ? "保存中..." : "保存角色配置"}
            </button>
          </footer>
        </form>
      </aside>
    </div>
  );
}

function FieldBlock(props: {
  label: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-sm font-medium text-slate-100">{props.label}</div>
      <div className="mt-1 text-xs leading-5 text-slate-400">
        {props.description}
      </div>
      <div className="mt-3">{props.children}</div>
    </section>
  );
}

function parseLineItems(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter((item, index, collection) => item.length > 0 && collection.indexOf(item) === index);
}
