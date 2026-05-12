import { useMemo } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { mapTaskStatusTone } from "../../lib/status";
import type { ProjectDetailTaskItem } from "../projects/types";
import { TASK_STATUS_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "./types";

type RoleFlowPanelProps = {
  projectName: string | null;
  tasks: ProjectDetailTaskItem[];
  isLoading?: boolean;
  errorMessage?: string | null;
};

const ROLE_FLOW_ORDER = [
  "product_manager",
  "architect",
  "engineer",
  "reviewer",
];

export function RoleFlowPanel(props: RoleFlowPanelProps) {
  const roleLinkedTasks = useMemo(
    () =>
      props.tasks
        .filter(
          (task) =>
            task.owner_role_code !== null ||
            task.upstream_role_code !== null ||
            task.downstream_role_code !== null,
        )
        .sort((left, right) => {
          if (left.depth !== right.depth) {
            return left.depth - right.depth;
          }

          return left.updated_at.localeCompare(right.updated_at);
        }),
    [props.tasks],
  );

  const chainRoleCodes = useMemo(() => {
    const seen = new Set<string>();
    const orderedCodes: string[] = [];

    for (const task of roleLinkedTasks) {
      for (const roleCode of [
        task.upstream_role_code,
        task.owner_role_code,
        task.downstream_role_code,
      ]) {
        if (!roleCode || seen.has(roleCode)) {
          continue;
        }

        seen.add(roleCode);
        orderedCodes.push(roleCode);
      }
    }

    return orderedCodes.sort((left, right) => {
      const leftIndex = ROLE_FLOW_ORDER.indexOf(left);
      const rightIndex = ROLE_FLOW_ORDER.indexOf(right);
      return (
        (leftIndex === -1 ? 999 : leftIndex) - (rightIndex === -1 ? 999 : rightIndex)
      );
    });
  }, [roleLinkedTasks]);

  const waitingHandoffCount = useMemo(
    () =>
      roleLinkedTasks.filter(
        (task) => task.downstream_role_code && task.status !== "completed",
      ).length,
    [roleLinkedTasks],
  );

  return (
    <section className="space-y-5">
      <header className="border-b border-[#333333] pb-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
              角色协作链
            </div>
            <h3 className="mt-2 text-lg font-semibold text-zinc-50">
              角色任务分派与协作链路
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
              {props.projectName
                ? `当前展示项目「${props.projectName}」的最小角色协作链。`
                : "当前展示所选项目的最小角色协作链。"}
              责任角色、上游来源角色和下游交接角色会跟随任务一起记录，方便查看接力方向。
            </p>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            <StatusBadge
              label={`角色链任务 ${roleLinkedTasks.length}`}
              tone={roleLinkedTasks.length > 0 ? "info" : "neutral"}
            />
            <StatusBadge
              label={`角色节点 ${chainRoleCodes.length}`}
              tone={chainRoleCodes.length > 0 ? "success" : "neutral"}
            />
            <StatusBadge
              label={`待交接 ${waitingHandoffCount}`}
              tone={waitingHandoffCount > 0 ? "warning" : "neutral"}
            />
          </div>
        </div>
      </header>

      {props.isLoading ? (
        <div className="border-y border-[#333333] py-4 text-sm text-zinc-500">
          正在生成角色协作链...
        </div>
      ) : props.errorMessage ? (
        <div className="border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200">
          角色协作链加载失败：{props.errorMessage}
        </div>
      ) : roleLinkedTasks.length === 0 ? (
        <div className="border-y border-dashed border-[#333333] py-4 text-sm leading-6 text-zinc-500">
          当前项目还没有带角色分派信息的任务。可以先通过 SOP 模板生成任务，或在任务创建接口中显式写入责任 / 上游 / 下游角色。
        </div>
      ) : (
        <div className="space-y-5">
          <section className="border-b border-[#333333] pb-5">
            <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
              最小角色链
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {chainRoleCodes.map((roleCode, index) => (
                <div key={roleCode} className="flex items-center gap-2">
                  <StatusBadge label={formatRoleLabel(roleCode)} tone="info" />
                  {index < chainRoleCodes.length - 1 ? (
                    <span className="text-xs text-zinc-600">→</span>
                  ) : null}
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-zinc-100">角色链任务列表</h4>
              <p className="mt-1 text-xs leading-5 text-zinc-500">
                按任务层级与更新时间展示角色分派、状态和交接方向。
              </p>
            </div>
            <div className="divide-y divide-[#333333] border-y border-[#333333]">
            {roleLinkedTasks.map((task) => (
              <article
                key={task.id}
                className="py-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium text-zinc-50">{task.title}</div>
                      <StatusBadge
                        label={TASK_STATUS_LABELS[task.status] ?? task.status}
                        tone={mapTaskStatusTone(task.status)}
                      />
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      {task.input_summary}
                    </p>
                  </div>

                  <div className="shrink-0 text-xs text-zinc-600">
                    更新时间 {formatDateTime(task.updated_at)}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <RoleStageBadge
                    label="上游"
                    roleCode={task.upstream_role_code}
                    tone="neutral"
                  />
                  <span className="text-xs text-zinc-600">→</span>
                  <RoleStageBadge
                    label="责任"
                    roleCode={task.owner_role_code}
                    tone="info"
                  />
                  <span className="text-xs text-zinc-600">→</span>
                  <RoleStageBadge
                    label="下游"
                    roleCode={task.downstream_role_code}
                    tone="warning"
                  />
                </div>
              </article>
            ))}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function RoleStageBadge(props: {
  label: string;
  roleCode: string | null;
  tone: "neutral" | "info" | "warning";
}) {
  return (
    <StatusBadge
      label={`${props.label}：${formatRoleLabel(props.roleCode)}`}
      tone={props.roleCode ? props.tone : "neutral"}
    />
  );
}

function formatRoleLabel(roleCode: string | null) {
  if (!roleCode) {
    return "未设置";
  }

  return ROLE_CODE_LABELS[roleCode] ?? roleCode;
}
