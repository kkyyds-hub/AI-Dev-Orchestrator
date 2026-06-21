import {
  Bell,
  Bot,
  Check,
  ChevronRight,
  KeyRound,
  Lock,
  Monitor,
  SlidersHorizontal,
} from "lucide-react";
import type { HTMLInputTypeAttribute } from "react";
import { useEffect, useMemo, useState } from "react";

import { cn } from "../../../lib/cn";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Input,
  Separator,
} from "./ui";

export type WorkbenchSettingsSection = "workspace" | "model" | "security";

type WorkbenchSettingsModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultSection?: WorkbenchSettingsSection;
  adapter?: WorkbenchSettingsAdapter;
};

type EditableSettingField = {
  id: keyof SettingsDraft;
  testId: string;
  label: string;
  placeholder: string;
  inputType?: HTMLInputTypeAttribute;
};

export type SettingsDraft = {
  defaultWorkspace: string;
  projectPrefix: string;
  defaultModel: string;
  economyModel: string;
  premiumModel: string;
  providerName: string;
  providerBaseUrl: string;
  providerTimeoutSeconds: string;
  providerKeyName: string;
  providerApiKey: string;
  trustedRoot: string;
};

export type WorkbenchSettingsAdapter = {
  mode: "mock" | "real" | "hybrid";
  loading?: boolean;
  errorMessage?: string | null;
  provider?: {
    configured: boolean;
    source: string;
    baseUrl: string;
    timeoutSeconds: number;
    detectedProviderType: string;
    modelPreset: string;
    modelNames: {
      economy: string;
      balanced: string;
      premium: string;
    };
    maskedApiKey?: string | null;
  } | null;
  workspace?: {
    defaultWorkspaceRoot: string;
    allowedWorkspaceRoots: string[];
    usingDefault: boolean;
  } | null;
  providerTest?: {
    status: "idle" | "testing" | "passed" | "failed";
    summary: string;
    testedAt?: string | null;
    modelName?: string | null;
  };
  onTestProvider?: () => void;
  onSave?: (draft: SettingsDraft) => void;
  saving?: boolean;
};

const sections: Array<{
  id: WorkbenchSettingsSection;
  label: string;
  icon: typeof Monitor;
  title: string;
  subtitle: string;
  fields: EditableSettingField[];
  rows: Array<readonly [string, string]>;
}> = [
  {
    id: "workspace",
    label: "工作台",
    icon: Monitor,
    title: "工作台设置",
    subtitle: "控制项目会话栏、AI 主管建议和低干扰交互的默认行为。",
    fields: [
      {
        id: "defaultWorkspace",
        testId: "ui-lab-setting-input-defaultWorkspace",
        label: "默认工作区",
        placeholder: "输入默认工作区路径",
      },
      {
        id: "projectPrefix",
        testId: "ui-lab-setting-input-projectPrefix",
        label: "项目命名前缀",
        placeholder: "输入项目命名前缀",
      },
    ],
    rows: [
      ["界面模式", "Minimal Dark"],
      ["AI 主管建议", "默认收起"],
      ["项目会话栏", "窄版布局"],
      ["计划确认", "需要用户手动确认"],
    ],
  },
  {
    id: "model",
    label: "模型",
    icon: Bot,
    title: "模型与执行",
    subtitle: "配置默认模型、执行确认方式和高风险动作边界。",
    fields: [
      {
        id: "defaultModel",
        testId: "ui-lab-setting-input-defaultModel",
        label: "默认模型",
        placeholder: "输入默认模型",
      },
      {
        id: "providerName",
        testId: "ui-lab-setting-input-providerName",
        label: "Provider",
        placeholder: "输入 Provider 名称",
      },
      {
        id: "providerBaseUrl",
        testId: "ui-lab-setting-input-providerBaseUrl",
        label: "接口地址",
        placeholder: "输入 OpenAI-compatible Base URL",
      },
      {
        id: "providerTimeoutSeconds",
        testId: "ui-lab-setting-input-providerTimeoutSeconds",
        label: "超时时间",
        placeholder: "输入请求超时秒数",
        inputType: "number",
      },
      {
        id: "providerKeyName",
        testId: "ui-lab-setting-input-providerKeyName",
        label: "密钥状态",
        placeholder: "显示当前密钥配置状态",
      },
      {
        id: "providerApiKey",
        testId: "ui-lab-setting-input-providerApiKey",
        label: "更新密钥",
        placeholder: "留空则保留当前密钥",
        inputType: "password",
      },
      {
        id: "economyModel",
        testId: "ui-lab-setting-input-economyModel",
        label: "轻量模型",
        placeholder: "输入轻量模型",
      },
      {
        id: "premiumModel",
        testId: "ui-lab-setting-input-premiumModel",
        label: "高阶模型",
        placeholder: "输入高阶模型",
      },
    ],
    rows: [
      ["执行策略", "高风险动作先确认"],
      ["运行记录", "保留最近 30 天"],
    ],
  },
  {
    id: "security",
    label: "边界",
    icon: Lock,
    title: "安全边界",
    subtitle: "限制仓库写入、发布动作和自动化权限的默认范围。",
    fields: [
      {
        id: "trustedRoot",
        testId: "ui-lab-setting-input-trustedRoot",
        label: "允许仓库根目录",
        placeholder: "输入允许访问的仓库根目录",
      },
    ],
    rows: [
      ["仓库权限", "默认只读"],
      ["Git 写入", "每次显式确认"],
      ["自动发布", "关闭"],
      ["危险命令", "需要二次确认"],
    ],
  },
];

const preferenceRows = [
  { icon: SlidersHorizontal, label: "项目默认值", value: "新项目沿用当前工作台偏好" },
  { icon: KeyRound, label: "密钥显示", value: "只显示配置状态，不展示明文" },
  { icon: Bell, label: "通知节奏", value: "只提醒需要你决策的事项" },
] as const;

const initialSettingsDraft: SettingsDraft = {
  defaultWorkspace: "/Users/kk/owner project",
  projectPrefix: "MVP",
  defaultModel: "Codex high",
  economyModel: "Codex low",
  premiumModel: "Codex high",
  providerName: "OpenAI",
  providerBaseUrl: "https://api.openai.com/v1",
  providerTimeoutSeconds: "30",
  providerKeyName: "OPENAI_API_KEY",
  providerApiKey: "",
  trustedRoot: "/Users/kk/owner project",
};

export function WorkbenchSettingsModal({
  open,
  onOpenChange,
  defaultSection = "workspace",
  adapter,
}: WorkbenchSettingsModalProps) {
  const [activeSectionId, setActiveSectionId] = useState<WorkbenchSettingsSection>(defaultSection);
  const [settingsDraft, setSettingsDraft] = useState<SettingsDraft>(initialSettingsDraft);

  useEffect(() => {
    if (open) setActiveSectionId(defaultSection);
  }, [defaultSection, open]);

  useEffect(() => {
    if (!open || !adapter) return;
    setSettingsDraft({
      defaultWorkspace:
        adapter.workspace?.defaultWorkspaceRoot ||
        adapter.workspace?.allowedWorkspaceRoots[0] ||
        initialSettingsDraft.defaultWorkspace,
      projectPrefix: initialSettingsDraft.projectPrefix,
      defaultModel:
        adapter.provider?.modelNames.balanced ||
        adapter.provider?.modelNames.premium ||
        initialSettingsDraft.defaultModel,
      economyModel:
        adapter.provider?.modelNames.economy ||
        initialSettingsDraft.economyModel,
      premiumModel:
        adapter.provider?.modelNames.premium ||
        initialSettingsDraft.premiumModel,
      providerName:
        adapter.provider?.detectedProviderType ||
        initialSettingsDraft.providerName,
      providerBaseUrl:
        adapter.provider?.baseUrl ||
        initialSettingsDraft.providerBaseUrl,
      providerTimeoutSeconds:
        adapter.provider?.timeoutSeconds
          ? String(adapter.provider.timeoutSeconds)
          : initialSettingsDraft.providerTimeoutSeconds,
      providerKeyName:
        adapter.provider?.maskedApiKey ||
        (adapter.provider?.configured ? "已配置" : "未配置"),
      providerApiKey: "",
      trustedRoot:
        adapter.workspace?.allowedWorkspaceRoots.join("\n") ||
        initialSettingsDraft.trustedRoot,
    });
  }, [adapter, open]);

  const activeSection = useMemo(
    () => sections.find((section) => section.id === activeSectionId) ?? sections[1],
    [activeSectionId],
  );
  const ActiveIcon = activeSection.icon;

  function updateDraft(fieldId: keyof SettingsDraft, value: string) {
    setSettingsDraft((current) => ({ ...current, [fieldId]: value }));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="ui-lab-settings-modal"
        className="ui-lab-settings-dialog-motion ui-lab-dialog-enter flex h-[min(760px,calc(100dvh-40px))] w-[min(1120px,calc(100vw-32px))] max-w-none overflow-hidden rounded-[28px] border-[#303030] bg-[#0B0B0B] p-0 shadow-[0_30px_120px_rgba(0,0,0,0.78)] duration-200 data-[state=closed]:!scale-100 data-[state=open]:!scale-100"
      >
        <div className="flex min-h-0 w-full flex-col md:flex-row">
          <aside className="flex shrink-0 flex-col border-b border-[#242424] bg-[#090909] p-4 md:w-[244px] md:border-b-0 md:border-r md:p-5">
            <DialogHeader className="space-y-2 pr-10 md:pr-0">
              <DialogTitle className="text-xl">设置</DialogTitle>
              <DialogDescription className="text-[13px] leading-5 text-[#8A8A8A]">
                管理账户、工作台、模型和安全边界。
              </DialogDescription>
            </DialogHeader>

            <nav className="mt-5 flex gap-2 overflow-x-auto md:flex-col md:overflow-visible">
              {sections.map((section) => {
                const Icon = section.icon;
                const active = activeSection.id === section.id;

                return (
                  <button
                    key={section.id}
                    className={cn(
                      "group flex h-11 shrink-0 items-center gap-3 rounded-[14px] px-3 text-left text-sm transition-all duration-200 md:w-full",
                      active ? "bg-white text-black" : "text-[#C7C7C7] hover:bg-[#1F1F1F] hover:text-white",
                    )}
                    onClick={() => setActiveSectionId(section.id)}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0 flex-1 whitespace-nowrap">{section.label}</span>
                    <ChevronRight
                      className={cn(
                        "hidden h-4 w-4 shrink-0 transition-transform md:block",
                        active ? "translate-x-0 opacity-100" : "-translate-x-1 opacity-0 group-hover:translate-x-0 group-hover:opacity-60",
                      )}
                    />
                  </button>
                );
              })}
            </nav>

            <div className="mt-auto hidden pt-6 md:block">
              <div className="rounded-[18px] border border-[#242424] px-3 py-3">
                <div className="flex items-center gap-2 text-xs text-[#C7C7C7]">
                  <Check className="h-3.5 w-3.5" />
                  已保存到本地草稿
                </div>
                <div className="mt-2 text-xs leading-5 text-[#6F6F6F]">
                  修改会先保存为工作台偏好，后续可继续调整。
                </div>
              </div>
            </div>
          </aside>

          <main className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-5 md:px-8 md:py-7">
            <div key={activeSection.id} className="settings-panel-expand max-w-3xl">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-[16px] border border-[#303030] bg-black">
                    <ActiveIcon className="h-5 w-5 text-[#C7C7C7]" />
                  </div>
                  <h3 className="text-2xl font-semibold tracking-normal text-white">{activeSection.title}</h3>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-[#8A8A8A]">{activeSection.subtitle}</p>
                </div>
                <Badge className="h-7 rounded-full border-[#303030] bg-transparent text-[#8A8A8A]">
                  {adapter?.mode === "real" ? "已接入" : "本地偏好"}
                </Badge>
              </div>

              <div className="mt-8 border-y border-[#242424]">
                {activeSection.fields.map((field) => (
                  <label
                    key={field.id}
                    className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm last:border-b-0 sm:grid-cols-[180px_1fr] sm:items-center"
                  >
                    <span className="text-[#C7C7C7]">{field.label}</span>
                    <Input
                      data-testid={field.testId}
                      type={field.inputType}
                      value={settingsDraft[field.id]}
                      placeholder={field.placeholder}
                      onChange={(event) => updateDraft(field.id, event.target.value)}
                      readOnly={field.id === "providerKeyName"}
                    />
                  </label>
                ))}
                {activeSection.rows.map(([label, value]) => (
                  <div
                    key={label}
                    className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm last:border-b-0 sm:grid-cols-[180px_1fr]"
                  >
                    <div className="text-[#C7C7C7]">{label}</div>
                    <div className="text-[#8A8A8A]">{value}</div>
                  </div>
                ))}
                {adapter ? (
                  <>
                    <div className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm sm:grid-cols-[180px_1fr]">
                      <div className="text-[#C7C7C7]">配置来源</div>
                      <div className="text-[#8A8A8A]">
                        {adapter.loading
                          ? "读取中"
                          : adapter.errorMessage
                            ? "暂不可用"
                            : adapter.provider?.source ?? "本地偏好"}
                      </div>
                    </div>
                    <div className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm sm:grid-cols-[180px_1fr]">
                      <div className="text-[#C7C7C7]">Provider 状态</div>
                      <div className="text-[#8A8A8A]">
                        {adapter.provider?.configured ? "已配置" : "未配置"}
                      </div>
                    </div>
                    <div className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm sm:grid-cols-[180px_1fr]">
                      <div className="text-[#C7C7C7]">接口地址</div>
                      <div className="break-all text-[#8A8A8A]">
                        {adapter.provider?.baseUrl ?? "未读取"}
                      </div>
                    </div>
                    <div className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm sm:grid-cols-[180px_1fr]">
                      <div className="text-[#C7C7C7]">工作区范围</div>
                      <div className="whitespace-pre-wrap break-all text-[#8A8A8A]">
                        {adapter.workspace?.allowedWorkspaceRoots.join("\n") ?? "未读取"}
                      </div>
                    </div>
                    <div className="grid gap-3 px-1 py-4 text-sm sm:grid-cols-[180px_1fr] sm:items-center">
                      <div className="text-[#C7C7C7]">连接测试</div>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                        <Button
                          variant="secondary"
                          onClick={adapter.onTestProvider}
                          disabled={!adapter.onTestProvider || adapter.providerTest?.status === "testing"}
                        >
                          {adapter.providerTest?.status === "testing" ? "测试中..." : "测试 Provider"}
                        </Button>
                        <div className="text-xs leading-5 text-[#8A8A8A]">
                          {adapter.providerTest?.summary ?? "尚未测试"}
                          {adapter.providerTest?.modelName ? ` · ${adapter.providerTest.modelName}` : ""}
                        </div>
                      </div>
                    </div>
                  </>
                ) : null}
              </div>

              <section className="mt-8">
                <div className="text-sm font-semibold text-white">偏好摘要</div>
                <div className="mt-4 divide-y divide-[#1A1A1A] border-y border-[#242424]">
                  {preferenceRows.map((item) => {
                    const Icon = item.icon;

                    return (
                      <div key={item.label} className="flex items-center gap-4 px-1 py-4">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] border border-[#242424] bg-[#101010]">
                          <Icon className="h-4 w-4 text-[#8A8A8A]" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm text-[#D7D7D7]">{item.label}</div>
                          <div className="mt-1 text-xs text-[#6F6F6F]">{item.value}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              <Separator className="my-7" />

              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <Button variant="secondary" onClick={() => onOpenChange(false)}>
                  关闭
                </Button>
                <Button
                  onClick={() => {
                    adapter?.onSave?.(settingsDraft);
                    onOpenChange(false);
                  }}
                  disabled={adapter?.saving}
                >
                  {adapter?.saving ? "保存中..." : "保存设置"}
                </Button>
              </div>
            </div>
          </main>
        </div>
      </DialogContent>
    </Dialog>
  );
}
