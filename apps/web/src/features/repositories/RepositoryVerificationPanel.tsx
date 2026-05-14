import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import {
  useProjectRepositoryVerificationBaseline,
  useReplaceProjectRepositoryVerificationBaseline,
} from "./hooks";
import type {
  RepositoryVerificationBaselineInput,
  RepositoryVerificationCategory,
  RepositoryVerificationTemplate,
} from "./types";
import { REPOSITORY_VERIFICATION_CATEGORY_LABELS } from "./types";

type RepositoryVerificationPanelProps = {
  projectId: string | null;
  repositoryRootPath: string | null;
};

type RepositoryVerificationTemplateDraft = {
  id?: string | null;
  category: RepositoryVerificationCategory;
  name: string;
  command: string;
  working_directory: string;
  timeout_seconds: number;
  enabled_by_default: boolean;
  description: string;
};

const CATEGORY_ORDER: RepositoryVerificationCategory[] = [
  "build",
  "test",
  "lint",
  "typecheck",
];

export function RepositoryVerificationPanel(
  props: RepositoryVerificationPanelProps,
) {
  const canLoadBaseline = props.projectId !== null && props.repositoryRootPath !== null;
  const baselineQuery = useProjectRepositoryVerificationBaseline(
    canLoadBaseline ? props.projectId : null,
  );
  const replaceMutation = useReplaceProjectRepositoryVerificationBaseline(
    canLoadBaseline ? props.projectId : null,
  );
  const [draftsByCategory, setDraftsByCategory] = useState<
    Record<RepositoryVerificationCategory, RepositoryVerificationTemplateDraft>
  >(buildEmptyDraftMap());
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!baselineQuery.data) {
      return;
    }

    setDraftsByCategory(buildDraftMapFromTemplates(baselineQuery.data.templates));
  }, [baselineQuery.data]);

  useEffect(() => {
    if (!replaceMutation.isSuccess) {
      return;
    }

    setSuccessMessage("已保存验证基线。");
  }, [replaceMutation.isSuccess]);

  const templates = useMemo(
    () => CATEGORY_ORDER.map((category) => draftsByCategory[category]),
    [draftsByCategory],
  );

  if (!props.repositoryRootPath) {
    return (
      <section className="border-l border-dashed border-[#3a3a3a] px-4 py-4 text-sm leading-6 text-zinc-500">
        验证基线依赖主仓库绑定；当前项目尚未绑定仓库，因此暂不展示
        build / test / lint / typecheck 命令模板。
      </section>
    );
  }

  return (
    <section className="border-l border-[#333333] px-4 py-1">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            仓库验证基线
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-400">
            在这里维护项目级 build / test / lint / typecheck 命令模板，作为变更批次执行前的统一验证口径。
            当前只保存模板、工作目录、超时与默认启用状态，不触发实际运行。
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={`模板 ${baselineQuery.data?.template_count ?? 0}`}
            tone="info"
          />
          <StatusBadge
            label={
              baselineQuery.data?.last_updated_at
                ? `最近更新 ${formatDateTime(baselineQuery.data.last_updated_at)}`
                : "等待初始化"
            }
            tone={baselineQuery.data?.last_updated_at ? "success" : "warning"}
          />
        </div>
      </div>

      <div className="mt-4 border-l border-[#333333] px-4 py-3 text-sm leading-6 text-zinc-400">
        仓库根目录：<span className="break-all text-zinc-100">{props.repositoryRootPath}</span>
        <div className="mt-2 flex flex-wrap gap-2">
          {(baselineQuery.data?.configured_categories ?? []).map((category) => (
            <StatusBadge
              key={category}
              label={REPOSITORY_VERIFICATION_CATEGORY_LABELS[category]}
              tone="neutral"
            />
          ))}
        </div>
      </div>

      {baselineQuery.isLoading && !baselineQuery.data ? (
        <div className="mt-4 text-sm leading-6 text-zinc-500">
          正在加载验证基线...
        </div>
      ) : null}

      {baselineQuery.isError ? (
        <div className="mt-4 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          验证基线加载失败：{baselineQuery.error.message}
        </div>
      ) : null}

      <form
        className="mt-4 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          setSuccessMessage(null);

          const payload: RepositoryVerificationBaselineInput = {
            templates: CATEGORY_ORDER.map((category) => {
              const draft = draftsByCategory[category];
              return {
                id: draft.id ?? undefined,
                category: draft.category,
                name: draft.name.trim(),
                command: draft.command.trim(),
                working_directory: draft.working_directory.trim() || ".",
                timeout_seconds: draft.timeout_seconds,
                enabled_by_default: draft.enabled_by_default,
                description: draft.description.trim() || null,
              };
            }),
          };

          void replaceMutation.mutateAsync(payload);
        }}
      >
        <div className="grid gap-4 xl:grid-cols-2">
          {templates.map((template) => (
            <article
              key={template.category}
              className="border-l border-[#333333] px-4 py-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold text-zinc-100">
                    {REPOSITORY_VERIFICATION_CATEGORY_LABELS[template.category]}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-zinc-600">
                    {CATEGORY_HELP_TEXT[template.category]}
                  </div>
                </div>
                <label className="inline-flex items-center gap-2 text-xs text-zinc-400">
                  <input
                    type="checkbox"
                    checked={template.enabled_by_default}
                    onChange={(event) =>
                      updateDraft(template.category, {
                        enabled_by_default: event.target.checked,
                      })
                    }
                    className="h-4 w-4 rounded border-[#3a3a3a] bg-transparent text-zinc-100 focus:ring-zinc-500"
                  />
                  默认启用
                </label>
              </div>

              <div className="mt-4 space-y-4">
                <FieldBlock label="模板名称">
                  <input
                    type="text"
                    value={template.name}
                    onChange={(event) =>
                      updateDraft(template.category, { name: event.target.value })
                    }
                    className="w-full border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                  />
                </FieldBlock>

                <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_160px]">
                  <FieldBlock label="工作目录">
                    <input
                      type="text"
                      value={template.working_directory}
                      onChange={(event) =>
                        updateDraft(template.category, {
                          working_directory: event.target.value,
                        })
                      }
                      className="w-full border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                    />
                  </FieldBlock>

                  <FieldBlock label="超时（秒）">
                    <input
                      type="number"
                      min={30}
                      max={7200}
                      value={template.timeout_seconds}
                      onChange={(event) =>
                        updateDraft(template.category, {
                          timeout_seconds: Number(event.target.value || 0),
                        })
                      }
                      className="w-full border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                    />
                  </FieldBlock>
                </div>

                <FieldBlock label="命令">
                  <textarea
                    rows={4}
                    value={template.command}
                    onChange={(event) =>
                      updateDraft(template.category, { command: event.target.value })
                    }
                    className="w-full border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-100 outline-none transition focus:border-zinc-500"
                  />
                </FieldBlock>

                <FieldBlock label="说明">
                  <textarea
                    rows={3}
                    value={template.description}
                    onChange={(event) =>
                      updateDraft(template.category, {
                        description: event.target.value,
                      })
                    }
                    className="w-full border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm leading-6 text-zinc-100 outline-none transition focus:border-zinc-500"
                  />
                </FieldBlock>
              </div>
            </article>
          ))}
        </div>

        {replaceMutation.isError ? (
          <div className="border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
            保存失败：{replaceMutation.error.message}
          </div>
        ) : null}

        {successMessage ? (
          <div className="border-l border-emerald-500/50 px-4 py-3 text-sm leading-6 text-emerald-100">
            {successMessage}
          </div>
        ) : null}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={replaceMutation.isPending || baselineQuery.isLoading}
            className="rounded border border-[#4a4a4a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600"
          >
            {replaceMutation.isPending ? "保存中..." : "保存验证基线"}
          </button>
        </div>
      </form>
    </section>
  );

  function updateDraft(
    category: RepositoryVerificationCategory,
    patch: Partial<RepositoryVerificationTemplateDraft>,
  ) {
    setDraftsByCategory((current) => ({
      ...current,
      [category]: {
        ...current[category],
        ...patch,
      },
    }));
  }
}

function FieldBlock(props: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2">{props.children}</div>
    </label>
  );
}

function buildDraftMapFromTemplates(templates: RepositoryVerificationTemplate[]) {
  return templates.reduce(
    (mapping, template) => {
      mapping[template.category] = {
        id: template.id,
        category: template.category,
        name: template.name,
        command: template.command,
        working_directory: template.working_directory,
        timeout_seconds: template.timeout_seconds,
        enabled_by_default: template.enabled_by_default,
        description: template.description ?? "",
      };
      return mapping;
    },
    buildEmptyDraftMap(),
  );
}

function buildEmptyDraftMap(): Record<
  RepositoryVerificationCategory,
  RepositoryVerificationTemplateDraft
> {
  return {
    build: buildDefaultDraft("build"),
    test: buildDefaultDraft("test"),
    lint: buildDefaultDraft("lint"),
    typecheck: buildDefaultDraft("typecheck"),
  };
}

function buildDefaultDraft(
  category: RepositoryVerificationCategory,
): RepositoryVerificationTemplateDraft {
  return {
    id: null,
    category,
    name: "",
    command: "",
    working_directory: category === "build" || category === "typecheck" ? "apps/web" : ".",
    timeout_seconds: category === "build" || category === "test" ? 900 : 600,
    enabled_by_default: true,
    description: "",
  };
}

const CATEGORY_HELP_TEXT: Record<RepositoryVerificationCategory, string> = {
  build: "约定最终构建口径；默认映射前端构建。",
  test: "约定仓库级最小烟测或测试口径；当前默认使用轻量烟测。",
  lint: "约定静态检查口径；当前仓库先以 Python 编译检查承接。",
  typecheck: "约定类型检查口径；默认映射前端 TypeScript 检查。",
};
