import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { StageChecklist } from "./components/StageChecklist";
import { useProjectSopTemplates, useSelectProjectSopTemplate } from "./hooks";
import type { ProjectDetail, ProjectSopTemplateSummary } from "./types";
import { PROJECT_STAGE_LABELS } from "./types";

type ProjectSopPanelProps = {
  projectId: string | null;
  detail: ProjectDetail | null;
};

export function ProjectSopPanel({
  projectId,
  detail,
}: ProjectSopPanelProps) {
  const templateQuery = useProjectSopTemplates();
  const selectTemplateMutation = useSelectProjectSopTemplate(projectId);
  const [feedback, setFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);

  useEffect(() => {
    setFeedback(null);
  }, [projectId]);

  const snapshot = detail?.sop_snapshot ?? null;
  const selectedTemplate = useMemo<ProjectSopTemplateSummary | null>(() => {
    if (!snapshot?.selected_template_code) {
      return null;
    }

    return (
      templateQuery.data?.find(
        (template) => template.code === snapshot.selected_template_code,
      ) ?? null
    );
  }, [snapshot?.selected_template_code, templateQuery.data]);

  const handleSelectTemplate = async (templateCode: string) => {
    try {
      const result = await selectTemplateMutation.mutateAsync({ templateCode });
      setFeedback({
        tone: "success",
        text: result.message,
      });
    } catch (error) {
      setFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "SOP 模板绑定失败。",
      });
    }
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Day06 SOP 模板与阶段推进
          </div>
          <h3 className="mt-3 text-lg font-semibold text-slate-50">
            SOP 模板、阶段清单与自动生成任务
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            Day06 把项目推进从自由对话改为 SOP 驱动：模板会声明阶段输入、产出、
            守卫条件和责任角色，并在项目进入阶段时自动补齐当前阶段任务。
          </p>
        </div>

        {snapshot?.has_template ? (
          <div className="flex flex-wrap gap-2">
            <StatusBadge
              label={snapshot.selected_template_name ?? "已选择模板"}
              tone="info"
            />
            <StatusBadge
              label={
                PROJECT_STAGE_LABELS[snapshot.current_stage] ?? snapshot.current_stage
              }
              tone="neutral"
            />
          </div>
        ) : (
          <StatusBadge
            label="未选择模板"
            tone="warning"
          />
        )}
      </div>

      {feedback ? (
        <div
          className={`mt-4 rounded-2xl border px-4 py-3 text-sm leading-6 ${
            feedback.tone === "success"
              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-100"
              : feedback.tone === "danger"
                ? "border-rose-500/20 bg-rose-500/10 text-rose-100"
                : "border-amber-500/20 bg-amber-500/10 text-amber-100"
          }`}
        >
          {feedback.text}
        </div>
      ) : null}

      {!snapshot ? (
        <p className="mt-4 text-sm leading-6 text-slate-400">
          正在读取当前项目的 SOP 信息...
        </p>
      ) : snapshot.has_template ? (
        <div className="mt-4 space-y-4">
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  当前模板
                </div>
                <h4 className="mt-2 text-base font-semibold text-slate-50">
                  {snapshot.selected_template_name}
                </h4>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {snapshot.selected_template_summary}
                </p>
              </div>

              <div className="text-xs text-slate-500">
                可用模板 {snapshot.available_template_count} 套
              </div>
            </div>

            {selectedTemplate ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {selectedTemplate.stages.map((stage) => (
                  <StatusBadge
                    key={`${selectedTemplate.code}-${stage.stage}`}
                    label={stage.title}
                    tone={
                      stage.stage === snapshot.current_stage ? "success" : "neutral"
                    }
                  />
                ))}
              </div>
            ) : null}

            <pre className="mt-4 whitespace-pre-wrap rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-4 text-xs leading-6 text-slate-300">
              {snapshot.context_summary}
            </pre>
          </section>

          <StageChecklist snapshot={snapshot} />

          {templateQuery.data && templateQuery.data.length > 1 ? (
            <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                可扩展模板目录
              </div>
              <div className="mt-4 grid gap-3 xl:grid-cols-2">
                {templateQuery.data.map((template) => (
                  <article
                    key={template.code}
                    className={`rounded-2xl border px-4 py-4 ${
                      template.code === snapshot.selected_template_code
                        ? "border-cyan-500/30 bg-cyan-500/5"
                        : "border-slate-800 bg-slate-950/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h5 className="text-sm font-medium text-slate-100">
                          {template.name}
                        </h5>
                        <p className="mt-2 text-sm leading-6 text-slate-300">
                          {template.summary}
                        </p>
                      </div>
                      <StatusBadge
                        label={
                          template.code === snapshot.selected_template_code
                            ? "当前使用"
                            : template.is_default
                              ? "默认"
                              : "备选"
                        }
                        tone={
                          template.code === snapshot.selected_template_code
                            ? "info"
                            : template.is_default
                              ? "success"
                              : "neutral"
                        }
                      />
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="text-sm leading-6 text-slate-300">
            当前项目还没有绑定 SOP 模板。选择模板后，系统会：
            <span className="mx-1 text-slate-100">1)</span>声明阶段输入/产出/守卫条件，
            <span className="mx-1 text-slate-100">2)</span>关联 Day05 角色责任，
            <span className="mx-1 text-slate-100">3)</span>自动生成当前阶段任务，
            并在阶段推进时继续补齐后续阶段任务。
          </p>

          {templateQuery.isLoading ? (
            <p className="text-sm leading-6 text-slate-400">正在加载 SOP 模板目录...</p>
          ) : templateQuery.isError ? (
            <p className="text-sm leading-6 text-rose-200">
              读取 SOP 模板目录失败：{templateQuery.error.message}
            </p>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {(templateQuery.data ?? []).map((template) => (
                <article
                  key={template.code}
                  className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-base font-semibold text-slate-50">
                          {template.name}
                        </h4>
                        {template.is_default ? (
                          <StatusBadge label="默认模板" tone="success" />
                        ) : null}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        {template.summary}
                      </p>
                      <p className="mt-2 text-xs leading-6 text-slate-500">
                        {template.description}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {template.stages.map((stage) => (
                      <StatusBadge
                        key={`${template.code}-${stage.stage}`}
                        label={stage.title}
                        tone="neutral"
                      />
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleSelectTemplate(template.code)}
                    disabled={selectTemplateMutation.isPending}
                    className="mt-4 inline-flex items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-400 hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {selectTemplateMutation.isPending
                      ? "绑定中..."
                      : `选择「${template.name}」`}
                  </button>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
