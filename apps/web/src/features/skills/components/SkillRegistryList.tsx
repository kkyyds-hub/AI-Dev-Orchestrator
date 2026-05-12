import { useEffect, useMemo, useState } from "react";

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

const SKILLS_PER_PAGE = 5;

export function SkillRegistryList(props: SkillRegistryListProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(props.skills.length / SKILLS_PER_PAGE));

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const pagedSkills = useMemo(() => {
    const startIndex = (currentPage - 1) * SKILLS_PER_PAGE;
    return props.skills.slice(startIndex, startIndex + SKILLS_PER_PAGE);
  }, [currentPage, props.skills]);

  const pageStart = props.skills.length ? (currentPage - 1) * SKILLS_PER_PAGE + 1 : 0;
  const pageEnd = Math.min(currentPage * SKILLS_PER_PAGE, props.skills.length);

  return (
    <section className="border-b border-[#333333] pb-4">
      <SkillRegistryListHeader onCreateSkill={props.onCreateSkill} />

      {props.isLoading && !props.registryLoaded ? (
        <div className="mt-4 border-y border-dashed border-[#333333] py-7 text-sm text-zinc-500">
          正在加载 Skill 注册中心...
        </div>
      ) : props.skills.length > 0 ? (
        <div className="mt-3 divide-y divide-[#333333] border-y border-[#333333]">
          {pagedSkills.map((skill) => (
            <SkillRegistryListItem
              key={skill.id}
              skill={skill}
              isActive={props.selectedSkillCode === skill.code}
              onSelectSkill={props.onSelectSkill}
            />
          ))}
          {totalPages > 1 ? (
            <SkillRegistryPagination
              currentPage={currentPage}
              pageEnd={pageEnd}
              pageStart={pageStart}
              totalItems={props.skills.length}
              totalPages={totalPages}
              onNextPage={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
              onPreviousPage={() => setCurrentPage((page) => Math.max(1, page - 1))}
            />
          ) : null}
        </div>
      ) : (
        <div className="mt-3 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前还没有 Skill；可以使用右侧编辑器创建第一条注册能力。
        </div>
      )}
    </section>
  );
}

function SkillRegistryPagination(props: {
  currentPage: number;
  pageEnd: number;
  pageStart: number;
  totalItems: number;
  totalPages: number;
  onNextPage: () => void;
  onPreviousPage: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 px-3 py-3 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
      <div>
        共 {props.totalItems} 个 Skill
        {props.totalItems ? `，当前 ${props.pageStart}-${props.pageEnd}` : ""}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={props.onPreviousPage}
          disabled={props.currentPage <= 1}
          className="rounded border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-500 hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:text-zinc-700"
        >
          上一页
        </button>
        <span className="min-w-16 text-center text-xs text-zinc-500">
          {props.currentPage} / {props.totalPages}
        </span>
        <button
          type="button"
          onClick={props.onNextPage}
          disabled={props.currentPage >= props.totalPages}
          className="rounded border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-500 hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:text-zinc-700"
        >
          下一页
        </button>
      </div>
    </div>
  );
}

function SkillRegistryListHeader(props: { onCreateSkill: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <div className="text-base font-semibold text-zinc-50">注册中的 Skill</div>
        <div className="mt-1 text-sm leading-6 text-zinc-500">
          查看当前 Skill 的启停状态、适用角色和版本历史；需要新能力时可新增 Skill 并纳入项目绑定面板。
        </div>
      </div>
      <button
        type="button"
        onClick={props.onCreateSkill}
        className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
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
    <article className={`px-3 py-4 transition ${props.isActive ? "bg-white/[0.035]" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium text-zinc-50">{props.skill.name}</div>
            <StatusBadge label={`v${props.skill.current_version}`} tone="info" />
            <StatusBadge
              label={props.skill.enabled ? "已启用" : "已停用"}
              tone={props.skill.enabled ? "success" : "warning"}
            />
          </div>
          <div className="mt-2 text-xs text-zinc-500">{props.skill.code}</div>
          <p className="mt-3 text-sm leading-6 text-zinc-300">{props.skill.summary}</p>
        </div>

        <button
          type="button"
          onClick={() => props.onSelectSkill(props.skill)}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
        >
          {props.isActive ? "正在编辑" : "编辑 Skill"}
        </button>
      </div>

      <p className="mt-3 text-sm leading-6 text-zinc-400">{props.skill.purpose}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {props.skill.applicable_role_codes.map((roleCode) => (
          <StatusBadge
            key={`${props.skill.code}-${roleCode}`}
            label={ROLE_CODE_LABELS[roleCode] ?? roleCode}
            tone="neutral"
          />
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-zinc-500">
        <span>创建于 {formatDateTime(props.skill.created_at)}</span>
        <span>更新于 {formatDateTime(props.skill.updated_at)}</span>
        <span>历史版本 {props.skill.version_history.length} 条</span>
      </div>

      {historyTail.length > 0 ? (
        <div className="mt-4 space-y-2 border-l border-[#333333] pl-3">
          {historyTail.map((record) => (
            <div key={record.id} className="text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge label={`v${record.version}`} tone="info" />
                <StatusBadge
                  label={record.enabled ? "启用" : "停用"}
                  tone={record.enabled ? "success" : "warning"}
                />
                <span className="text-xs text-zinc-500">
                  {formatDateTime(record.created_at)}
                </span>
              </div>
              {record.change_note ? (
                <p className="mt-2 text-sm leading-6 text-zinc-300">
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
