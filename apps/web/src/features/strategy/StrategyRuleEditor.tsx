import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { useStrategyRules, useUpdateStrategyRules } from "./hooks";

type StrategyRuleEditorProps = {
  projectId: string | null;
};

export function StrategyRuleEditor(props: StrategyRuleEditorProps) {
  const rulesQuery = useStrategyRules();
  const updateRulesMutation = useUpdateStrategyRules(props.projectId);
  const [draft, setDraft] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!rulesQuery.data?.rules) {
      return;
    }

    setDraft(JSON.stringify(rulesQuery.data.rules, null, 2));
  }, [rulesQuery.dataUpdatedAt, rulesQuery.data?.rules]);

  const helperLines = useMemo(
    () => [
      "可编辑关键项：budget_model_tiers、stage_role_boosts、stage_skill_preferences、stage_model_tier_overrides。",
      "修改后会立即影响项目级策略预览和后续 Worker 路由。",
      "建议先在预览面板核对结果，再执行 Worker。",
    ],
    [],
  );

  const handleSave = () => {
    try {
      const parsed = JSON.parse(draft) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setLocalError("规则 JSON 必须是对象。");
        return;
      }

      setLocalError(null);
      updateRulesMutation.mutate({
        rules: parsed as Record<string, unknown>,
      });
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "JSON 解析失败。");
    }
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Day15 策略规则编辑器
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">
            最小配置化规则集
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            通过一份集中规则集控制“预算 → 模型层级、阶段 → 角色加权、阶段 → Skill 偏好”，避免把策略散落到多个服务里。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={rulesQuery.data?.source ?? "default"}
            tone={rulesQuery.data?.source === "runtime_override" ? "success" : "info"}
          />
          {updateRulesMutation.isPending ? (
            <StatusBadge label="保存中" tone="warning" />
          ) : null}
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          规则文件位置
        </div>
        <div className="mt-2 break-all text-sm text-slate-300">
          {rulesQuery.data?.storage_path ?? "读取中..."}
        </div>
      </div>

      <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-300">
        {helperLines.map((line) => (
          <li
            key={line}
            className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2"
          >
            {line}
          </li>
        ))}
      </ul>

      {rulesQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          规则读取失败：
          {rulesQuery.error instanceof Error ? rulesQuery.error.message : "未知错误"}
        </div>
      ) : null}

      <div className="mt-4">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          spellCheck={false}
          className="min-h-[360px] w-full rounded-2xl border border-slate-800 bg-slate-950/80 p-4 font-mono text-xs leading-6 text-slate-200 outline-none transition focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-400/20"
          placeholder="策略规则 JSON 将显示在这里..."
        />
      </div>

      {localError ? (
        <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
          {localError}
        </div>
      ) : null}
      {updateRulesMutation.isError ? (
        <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100">
          {updateRulesMutation.error instanceof Error
            ? updateRulesMutation.error.message
            : "规则保存失败。"}
        </div>
      ) : null}
      {updateRulesMutation.isSuccess ? (
        <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          规则已保存，策略预览会自动刷新。
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={updateRulesMutation.isPending || !draft.trim()}
          className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
        >
          {updateRulesMutation.isPending ? "保存中..." : "保存规则"}
        </button>
        <button
          type="button"
          onClick={() => {
            setDraft(JSON.stringify(rulesQuery.data?.rules ?? {}, null, 2));
            setLocalError(null);
          }}
          className="rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-900"
        >
          重置为当前快照
        </button>
      </div>
    </section>
  );
}
