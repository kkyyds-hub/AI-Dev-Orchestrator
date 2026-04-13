import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { useStrategyRules, useUpdateStrategyRules } from "./hooks";

type StrategyRuleEditorProps = {
  projectId: string | null;
};

const MODEL_TIER_LABELS: Record<string, string> = {
  economy: "经济",
  balanced: "均衡",
  premium: "高质量",
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
      "可编辑关键项：budget_model_tiers、role_model_tier_preferences、stage_model_tier_overrides、stage_skill_preferences。",
      "保存后会立即影响项目策略预览，以及后续 Worker 的模型路由选择。",
      "建议先看上方策略预览，再回到这里调整 Role Model Policy。",
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
            Strategy Rule Editor
          </div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">
            策略规则与 Role Model Policy
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            这里保留完整 JSON 编辑入口，同时把 Role Model Policy 的最小控制面显式展开，
            避免只剩“能改 JSON，但看不见当前策略口径”。
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

      {rulesQuery.data?.role_model_policy ? (
        <section className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">
            Role Model Policy
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            该摘要由 <code>/strategy/rules</code> 显式返回，代表当前保存态的角色模型策略；
            修改并保存 JSON 后，这里的摘要会与策略预览一起刷新。
          </p>

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                角色默认层级
              </div>
              <div className="mt-3 space-y-3">
                {rulesQuery.data.role_model_policy.role_preferences.length ? (
                  rulesQuery.data.role_model_policy.role_preferences.map((item) => (
                    <PolicyRow
                      key={item.role_code}
                      title={ROLE_CODE_LABELS[item.role_code] ?? item.role_code}
                      modelTier={item.model_tier}
                      modelLabel={item.model_label}
                      modelName={item.model_name}
                      summary={item.summary}
                    />
                  ))
                ) : (
                  <EmptyState text="当前没有显式角色默认层级，运行时会优先回退到预算基线模型层级。" />
                )}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                阶段覆盖
              </div>
              <div className="mt-3 space-y-3">
                {rulesQuery.data.role_model_policy.stage_overrides.length ? (
                  rulesQuery.data.role_model_policy.stage_overrides.map((item) => (
                    <PolicyRow
                      key={`${item.stage}-${item.role_code}`}
                      title={`${PROJECT_STAGE_LABELS[item.stage] ?? item.stage} / ${ROLE_CODE_LABELS[item.role_code] ?? item.role_code}`}
                      modelTier={item.model_tier}
                      modelLabel={item.model_label}
                      modelName={item.model_name}
                      summary={item.summary}
                    />
                  ))
                ) : (
                  <EmptyState text="当前没有阶段级覆盖，运行时会继续沿用角色默认层级。" />
                )}
              </div>
            </div>
          </div>
        </section>
      ) : null}

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
          规则读取失败：{rulesQuery.error instanceof Error ? rulesQuery.error.message : "未知错误"}
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

function PolicyRow(props: {
  title: string;
  modelTier: string;
  modelLabel: string | null;
  modelName: string | null;
  summary: string | null;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-100">{props.title}</div>
        <StatusBadge
          label={MODEL_TIER_LABELS[props.modelTier] ?? props.modelTier}
          tone="info"
        />
      </div>
      <div className="mt-2 text-sm text-slate-300">
        {props.modelLabel ?? "未命名层级"}
        {props.modelName ? ` · ${props.modelName}` : ""}
      </div>
      {props.summary ? (
        <p className="mt-2 text-xs leading-5 text-slate-500">{props.summary}</p>
      ) : null}
    </div>
  );
}

function EmptyState(props: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/50 px-3 py-4 text-sm leading-6 text-slate-400">
      {props.text}
    </div>
  );
}
