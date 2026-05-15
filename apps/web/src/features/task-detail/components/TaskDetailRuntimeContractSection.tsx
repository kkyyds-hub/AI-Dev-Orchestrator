import { StatusBadge } from "../../../components/StatusBadge";
import { mapRunStatusTone } from "../../../lib/status";
import type { ConsoleRun } from "../../console/types";
import { DetailField, type TaskDetailSurfaceVariant } from "./TaskDetailField";

type RuntimeField = {
  key: string;
  label: string;
  value: string;
};

export function TaskDetailRuntimeContractSection(props: {
  taskId: string;
  selectedRun: ConsoleRun | null;
  runtimeFields: RuntimeField[];
  roleModelPolicyFields: RuntimeField[];
  hasRoleModelPolicyData: boolean;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToStrategyPreview?: (input: {
    taskId: string;
    runId?: string | null;
  }) => void;
}) {
  const { selectedRun } = props;
  const isLine = props.surfaceVariant === "line";

  if (!selectedRun) {
    return null;
  }

  return (
    <div
      data-testid="task-detail-runtime-context"
      className={
        isLine
          ? "border-b border-[#333333] pb-5"
          : "border-l border-[#333333] px-4 py-3"
      }
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>
            运行约束详情
          </h3>
          <p className={`mt-1 text-xs ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>
            任务 {props.taskId}；运行 {selectedRun.id}
          </p>
        </div>
        <StatusBadge label={selectedRun.status} tone={mapRunStatusTone(selectedRun.status)} />
      </div>

      {props.onNavigateToStrategyPreview ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            data-testid="goto-strategy-preview-from-task-detail"
            onClick={() =>
              props.onNavigateToStrategyPreview?.({
                taskId: props.taskId,
                runId: selectedRun.id,
              })
            }
            className={isLine ? "rounded-md border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-[#3a3a3a] bg-transparent px-3 py-1.5 text-xs text-zinc-100 transition hover:bg-transparent"}
          >
            返回策略预览
          </button>
          {props.onNavigateToRun ? (
            <button
              type="button"
              data-testid="goto-run-center-from-task-detail"
              onClick={() => props.onNavigateToRun?.(selectedRun.id, props.taskId)}
              className={isLine ? "rounded-md border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-200 transition hover:border-[#6a6a6a] hover:text-zinc-100"}
            >
              打开运行中心
            </button>
          ) : null}
        </div>
      ) : props.onNavigateToRun ? (
        <div className="mt-3">
          <button
            type="button"
            data-testid="goto-run-center-from-task-detail"
            onClick={() => props.onNavigateToRun?.(selectedRun.id, props.taskId)}
            className={isLine ? "rounded-md border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-[#333333] bg-transparent px-3 py-1.5 text-xs text-zinc-200 transition hover:border-[#6a6a6a] hover:text-zinc-100"}
          >
            打开运行中心
          </button>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <DetailField
          testId="task-detail-runtime-field-task_id"
          surfaceVariant={props.surfaceVariant}
          label="任务 ID"
          value={props.taskId}
        />
        <DetailField
          testId="task-detail-runtime-field-run_id"
          surfaceVariant={props.surfaceVariant}
          label="运行 ID"
          value={selectedRun.id}
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {props.runtimeFields.map((field) => (
          <DetailField
            key={`task-runtime-${field.key}`}
            testId={`task-detail-runtime-field-${field.key}`}
            surfaceVariant={props.surfaceVariant}
            label={field.label}
            value={field.value}
          />
        ))}
      </div>

      {props.hasRoleModelPolicyData ? (
        <div className={isLine ? "mt-4 border-t border-[#333333] pt-4" : "mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3"}>
          <div className={`text-xs uppercase tracking-[0.18em] ${isLine ? "text-zinc-600" : "text-emerald-200"}`}>
            运行约束角色模型策略
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {props.roleModelPolicyFields.map((field) => (
              <DetailField
                key={`task-policy-${field.key}`}
                testId={`task-detail-policy-field-${field.key}`}
                surfaceVariant={props.surfaceVariant}
                label={field.label}
                value={field.value}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
