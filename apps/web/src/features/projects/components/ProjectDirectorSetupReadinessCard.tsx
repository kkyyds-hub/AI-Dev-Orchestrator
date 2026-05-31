import { StatusBadge } from "../../../components/StatusBadge";
import { useProjectDirectorSetupReadiness } from "../../project-director/hooks";
import type {
  ProjectDirectorSetupReadiness,
  ProjectDirectorSetupReadinessConfigStatus,
} from "../../project-director/types";

const CONFIG_STATUS_LABELS: Record<ProjectDirectorSetupReadinessConfigStatus, string> = {
  pending_confirmation: "待确认",
  confirmed: "已确认",
  rejected: "已拒绝",
  missing: "未生成",
};

const CONFIG_STATUS_TONES: Record<
  ProjectDirectorSetupReadinessConfigStatus,
  "info" | "success" | "warning" | "danger"
> = {
  pending_confirmation: "warning",
  confirmed: "success",
  rejected: "danger",
  missing: "info",
};

const BOUNDARY_TIPS = [
  "不会自动启动 Worker",
  "不会自动创建 Run",
  "不会执行验证命令",
  "不会写入仓库",
];

export function ProjectDirectorSetupReadinessCard({
  projectId,
}: {
  projectId: string | null;
}) {
  const query = useProjectDirectorSetupReadiness(projectId);
  const readiness = query.data ?? null;

  if (!projectId || query.isLoading) {
    return null;
  }

  if (query.isError) {
    return (
      <section className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100">
        AI 主控项目配置总览暂时读取失败，不影响项目详情页继续使用。
      </section>
    );
  }

  if (!readiness?.created_by_director) {
    return null;
  }

  return (
    <section
      data-testid="project-director-setup-readiness-card"
      className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-emerald-100">
              AI 主控项目配置总览
            </h4>
            <StatusBadge
              label={
                readiness.ready_for_manual_execution
                  ? "可手动考虑执行"
                  : "仍需确认配置"
              }
              tone={readiness.ready_for_manual_execution ? "success" : "warning"}
            />
          </div>
          <p className="mt-1 text-xs leading-5 text-emerald-100/75">
            这里汇总 AI 主控草案创建正式项目后的当前状态；仅展示只读状态，不会触发执行动作。
          </p>
        </div>
      </div>

      <ReadinessFacts readiness={readiness} />
      <ConfigStatusGrid readiness={readiness} />
      <ReadinessCounts readiness={readiness} />
      <NextSteps readiness={readiness} />
      <BoundaryTips />
    </section>
  );
}

function ReadinessFacts({ readiness }: { readiness: ProjectDirectorSetupReadiness }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <FactBlock label="来源" value="AI 主控草案" />
      <FactBlock
        label="草案版本 ID"
        value={readiness.source_plan_version_id ?? "未识别"}
        mono
      />
      <FactBlock
        label="正式 Project"
        value={readiness.formal_project_created ? "已创建" : "未创建"}
      />
      <FactBlock
        label="任务队列"
        value={
          readiness.task_queue_created
            ? `已创建，${readiness.pending_task_count} 个待执行任务`
            : "未创建"
        }
      />
    </div>
  );
}

function ConfigStatusGrid({ readiness }: { readiness: ProjectDirectorSetupReadiness }) {
  const items = [
    { label: "Agent 编队", status: readiness.agent_team_config_status },
    { label: "Skill 绑定", status: readiness.skill_binding_config_status },
    { label: "仓库绑定", status: readiness.repository_binding_config_status },
    { label: "验证机制", status: readiness.verification_config_status },
  ];

  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2"
        >
          <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-600">
            {item.label}
          </div>
          <div className="mt-2">
            <StatusBadge
              label={CONFIG_STATUS_LABELS[item.status]}
              tone={CONFIG_STATUS_TONES[item.status]}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function ReadinessCounts({ readiness }: { readiness: ProjectDirectorSetupReadiness }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-3">
      <FactBlock label="待确认数量" value={`${readiness.pending_confirmation_count}`} />
      <FactBlock label="已确认数量" value={`${readiness.confirmed_count}`} />
      <FactBlock
        label="是否可手动考虑执行"
        value={
          readiness.ready_for_manual_execution
            ? "是：所有建议配置已确认，仍需用户手动启动 Worker"
            : "否：仍有待确认、已拒绝或未生成配置"
        }
      />
    </div>
  );
}

function NextSteps({ readiness }: { readiness: ProjectDirectorSetupReadiness }) {
  if (readiness.next_steps.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 rounded border border-emerald-500/20 bg-[#111111]/70 px-3 py-2">
      <div className="text-xs font-medium text-emerald-100">下一步建议</div>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-emerald-100/80">
        {readiness.next_steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ul>
    </div>
  );
}

function BoundaryTips() {
  return (
    <div className="mt-3 rounded border border-emerald-500/20 bg-[#111111]/70 px-3 py-2">
      <div className="text-xs font-medium text-emerald-100">边界提示</div>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-emerald-100/80">
        {BOUNDARY_TIPS.map((tip) => (
          <li key={tip}>{tip}</li>
        ))}
      </ul>
    </div>
  );
}

function FactBlock({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded border border-[#333333] bg-[#111111]/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-600">
        {label}
      </div>
      <div className={`mt-1 break-all text-xs text-zinc-300 ${mono ? "font-mono" : ""}`}>
        {value}
      </div>
    </div>
  );
}
