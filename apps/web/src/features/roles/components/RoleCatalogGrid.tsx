import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { ROLE_CODE_LABELS } from "../types";
import type { RoleCatalogDisplayRole } from "../lib/roleCatalogRoles";
import { RoleCatalogCard } from "./RoleCatalogCard";

type RoleCatalogGridProps = {
  roles: RoleCatalogDisplayRole[];
  projectSelected: boolean;
  onEditRole: (roleCode: string | null) => void;
};

const ROLE_CATALOG_PAGE_SIZE = 6;

export function RoleCatalogGrid(props: RoleCatalogGridProps) {
  const [selectedRoleKey, setSelectedRoleKey] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const pageCount = Math.max(
    1,
    Math.ceil(props.roles.length / ROLE_CATALOG_PAGE_SIZE),
  );

  useEffect(() => {
    setCurrentPage((page) => Math.min(Math.max(page, 1), pageCount));
  }, [pageCount]);

  useEffect(() => {
    if (props.roles.length === 0) {
      setSelectedRoleKey(null);
      return;
    }

    if (selectedRoleKey && props.roles.some((role) => role.key === selectedRoleKey)) {
      return;
    }

    setSelectedRoleKey(props.roles[0]?.key ?? null);
  }, [props.roles, selectedRoleKey]);

  const pagedRoles = useMemo(() => {
    const start = (currentPage - 1) * ROLE_CATALOG_PAGE_SIZE;
    return props.roles.slice(start, start + ROLE_CATALOG_PAGE_SIZE);
  }, [currentPage, props.roles]);

  const selectedRole =
    props.roles.find((role) => role.key === selectedRoleKey) ??
    pagedRoles[0] ??
    props.roles[0] ??
    null;

  const visibleStart =
    props.roles.length === 0 ? 0 : (currentPage - 1) * ROLE_CATALOG_PAGE_SIZE + 1;
  const visibleEnd = Math.min(
    currentPage * ROLE_CATALOG_PAGE_SIZE,
    props.roles.length,
  );

  const selectPage = (nextPage: number) => {
    const normalizedPage = Math.min(Math.max(nextPage, 1), pageCount);
    const firstRoleOnPage =
      props.roles[(normalizedPage - 1) * ROLE_CATALOG_PAGE_SIZE] ?? null;

    setCurrentPage(normalizedPage);
    setSelectedRoleKey(firstRoleOnPage?.key ?? null);
  };

  return (
    <section aria-label="角色目录" className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100">角色目录</h3>
          <p className="mt-1 text-xs leading-5 text-zinc-500">
            左侧选择角色，右侧仅展开当前角色详情；选择项目后可进入轻量编辑。
          </p>
        </div>
        <p className="mt-1 text-xs leading-5 text-zinc-500">
          {props.roles.length > 0
            ? `第 ${visibleStart}-${visibleEnd} 个 / 共 ${props.roles.length} 个角色`
            : "暂无可展示角色"}
        </p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(280px,0.82fr)_minmax(0,1.18fr)]">
        <section className="min-w-0 rounded-lg border border-[#333333]">
          <div className="border-b border-[#333333] px-4 py-3">
            <div className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-600">
              Role List
            </div>
            <p className="mt-1 text-sm text-zinc-300">角色清单</p>
          </div>

          {pagedRoles.length > 0 ? (
            <div className="divide-y divide-[#333333]">
              {pagedRoles.map((role) => {
                const roleCode = getRoleCode(role);
                const roleName = getRoleName(role);
                const roleSummary = getRoleSummary(role);
                const isSelected = selectedRole?.key === role.key;
                const enabled = getRoleEnabled(role);

                return (
                  <button
                    key={role.key}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setSelectedRoleKey(role.key)}
                    className={`block w-full border-l-2 px-4 py-3 text-left transition ${
                      isSelected
                        ? "border-zinc-100 bg-zinc-100/[0.04]"
                        : "border-transparent hover:border-zinc-600 hover:bg-zinc-100/[0.025]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-zinc-100">
                          {roleName}
                        </div>
                        <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500">
                          {roleSummary}
                        </p>
                      </div>

                      {enabled !== null ? (
                        <StatusBadge
                          label={enabled ? "启用" : "停用"}
                          tone={enabled ? "success" : "neutral"}
                        />
                      ) : null}
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-[#3a3a3a] px-2 py-0.5 text-[11px] text-zinc-400">
                        {ROLE_CODE_LABELS[roleCode] ?? roleCode}
                      </span>
                      {!role.projectRole ? (
                        <span className="rounded-full border border-[#3a3a3a] px-2 py-0.5 text-[11px] text-zinc-500">
                          系统目录
                        </span>
                      ) : null}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="px-4 py-8 text-sm leading-6 text-zinc-500">
              角色目录加载完成后将在这里显示清单。
            </div>
          )}

          <div className="flex items-center justify-between gap-3 border-t border-[#333333] px-4 py-3">
            <button
              type="button"
              onClick={() => selectPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="rounded border border-[#3a3a3a] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:border-[#2a2a2a] disabled:text-zinc-600"
            >
              上一页
            </button>
            <span className="text-xs text-zinc-500">
              {currentPage} / {pageCount}
            </span>
            <button
              type="button"
              onClick={() => selectPage(currentPage + 1)}
              disabled={currentPage >= pageCount}
              className="rounded border border-[#3a3a3a] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:border-[#2a2a2a] disabled:text-zinc-600"
            >
              下一页
            </button>
          </div>
        </section>

        <section className="min-w-0 rounded-lg border border-[#333333]">
          <div className="border-b border-[#333333] px-5 py-3">
            <div className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-600">
              Current Role
            </div>
            <p className="mt-1 text-sm text-zinc-300">当前角色详情</p>
          </div>

          {selectedRole ? (
            <RoleCatalogCard
              projectRole={selectedRole.projectRole}
              systemRole={selectedRole.systemRole}
              projectSelected={props.projectSelected}
              onEdit={() => props.onEditRole(getRoleCode(selectedRole))}
            />
          ) : (
            <div className="px-5 py-8 text-sm leading-6 text-zinc-500">
              请先从左侧清单选择一个角色。
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function getRoleCode(role: RoleCatalogDisplayRole) {
  return role.projectRole?.role_code ?? role.systemRole?.code ?? "unknown";
}

function getRoleName(role: RoleCatalogDisplayRole) {
  return role.projectRole?.name ?? role.systemRole?.name ?? "角色";
}

function getRoleSummary(role: RoleCatalogDisplayRole) {
  return role.projectRole?.summary ?? role.systemRole?.summary ?? "—";
}

function getRoleEnabled(role: RoleCatalogDisplayRole) {
  if (role.projectRole) {
    return role.projectRole.enabled;
  }

  if (role.systemRole) {
    return role.systemRole.enabled_by_default;
  }

  return null;
}
