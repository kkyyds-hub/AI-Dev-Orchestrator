import { useEffect, useMemo, useState } from "react";

import type {
  ProjectRoleSkillBindingGroup,
  ProjectSkillBindingSnapshot,
  SkillRegistrySkill,
} from "../types";
import { RoleSkillBindingRoleCard } from "./RoleSkillBindingRoleCard";

type RoleSkillBindingGridProps = {
  applicableSkillMap: Map<string, SkillRegistrySkill[]>;
  bindingSnapshot: ProjectSkillBindingSnapshot | null;
  draftSkillCodes: string[];
  editingRoleCode: string | null;
  isSaving: boolean;
  onCancelEdit: () => void;
  onEditRole: (role: ProjectRoleSkillBindingGroup) => void;
  onSaveRoleBindings: () => void;
  onToggleSkillCode: (skillCode: string) => void;
};

const ROLES_PER_PAGE = 4;

export function RoleSkillBindingGrid(props: RoleSkillBindingGridProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const roles = props.bindingSnapshot?.roles ?? [];
  const totalPages = Math.max(1, Math.ceil(roles.length / ROLES_PER_PAGE));

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const pagedRoles = useMemo(() => {
    const startIndex = (currentPage - 1) * ROLES_PER_PAGE;
    return roles.slice(startIndex, startIndex + ROLES_PER_PAGE);
  }, [currentPage, roles]);

  const pageStart = roles.length ? (currentPage - 1) * ROLES_PER_PAGE + 1 : 0;
  const pageEnd = Math.min(currentPage * ROLES_PER_PAGE, roles.length);

  if (!props.bindingSnapshot) {
    return null;
  }

  return (
    <section className="space-y-4">
      <div className="grid gap-x-5 gap-y-4 xl:grid-cols-2">
        {pagedRoles.map((role) => (
          <RoleSkillBindingRoleCard
            key={role.role_code}
            applicableSkills={props.applicableSkillMap.get(role.role_code) ?? []}
            draftSkillCodes={props.draftSkillCodes}
            isEditing={props.editingRoleCode === role.role_code}
            isSaving={props.isSaving}
            role={role}
            onCancelEdit={props.onCancelEdit}
            onEditRole={props.onEditRole}
            onSaveRoleBindings={props.onSaveRoleBindings}
            onToggleSkillCode={props.onToggleSkillCode}
          />
        ))}
      </div>

      <RoleBindingPagination
        currentPage={currentPage}
        pageEnd={pageEnd}
        pageStart={pageStart}
        totalItems={roles.length}
        totalPages={totalPages}
        onNextPage={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
        onPreviousPage={() => setCurrentPage((page) => Math.max(1, page - 1))}
      />
    </section>
  );
}

function RoleBindingPagination(props: {
  currentPage: number;
  pageEnd: number;
  pageStart: number;
  totalItems: number;
  totalPages: number;
  onNextPage: () => void;
  onPreviousPage: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 border-y border-[#333333] px-3 py-3 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
      <div>
        共 {props.totalItems} 个角色
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
