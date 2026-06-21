import { KeyRound, Mail, User } from "lucide-react";
import { useEffect, useState } from "react";

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

type AccountSettingsModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  adapter?: WorkbenchAccountAdapter;
};

type AccountDraft = {
  displayName: string;
  notificationEmail: string;
};

export type WorkbenchAccountProfile = {
  accountId: string;
  displayName: string;
  notificationEmail: string;
  loginMethod: string;
  defaultRole: string;
  source: "saved_config" | "env" | "default";
};

export type WorkbenchAccountAdapter = {
  mode: "local" | "real";
  loading: boolean;
  errorMessage: string | null;
  profile: WorkbenchAccountProfile | null;
  onSave?: (draft: AccountDraft) => void;
  saving?: boolean;
};

const initialAccountDraft: AccountDraft = {
  displayName: "kk",
  notificationEmail: "kk@example.local",
};

const fallbackAccountProfile: WorkbenchAccountProfile = {
  accountId: "kk-local-01",
  displayName: initialAccountDraft.displayName,
  notificationEmail: initialAccountDraft.notificationEmail,
  loginMethod: "本地账户",
  defaultRole: "项目所有者",
  source: "default",
};

export function AccountSettingsModal({
  open,
  onOpenChange,
  adapter,
}: AccountSettingsModalProps) {
  const profile = adapter?.profile ?? fallbackAccountProfile;
  const [accountDraft, setAccountDraft] = useState<AccountDraft>(initialAccountDraft);
  const accountRows = [
    ["账户 ID", profile.accountId],
    ["登录方式", profile.loginMethod],
    ["默认身份", profile.defaultRole],
  ] as const;

  useEffect(() => {
    if (!open) return;
    setAccountDraft({
      displayName: profile.displayName,
      notificationEmail: profile.notificationEmail,
    });
  }, [open, profile.displayName, profile.notificationEmail]);

  function updateDraft(fieldId: keyof AccountDraft, value: string) {
    setAccountDraft((current) => ({ ...current, [fieldId]: value }));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="ui-lab-account-settings-modal"
        className="ui-lab-settings-dialog-motion ui-lab-dialog-enter w-[min(620px,calc(100vw-32px))] max-w-none rounded-[28px] border-[#303030] bg-[#0B0B0B] p-0 shadow-[0_30px_120px_rgba(0,0,0,0.78)] duration-200 data-[state=closed]:!scale-100 data-[state=open]:!scale-100"
      >
        <div
          data-testid={
            adapter?.mode === "real"
              ? "workbench-account-adapter-real"
              : "workbench-account-adapter-local"
          }
          aria-hidden="true"
        />
        <div className="p-5 md:p-7">
          <DialogHeader className="space-y-3 pr-10">
            <div className="flex items-start justify-between gap-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-[16px] border border-[#303030] bg-black">
                <User className="h-5 w-5 text-[#C7C7C7]" />
              </div>
              <Badge className="h-7 rounded-full border-[#303030] bg-transparent text-[#8A8A8A]">
                {adapter?.mode === "real" ? "工作台账户" : "本地账户"}
              </Badge>
            </div>
            <DialogTitle className="text-2xl">账户信息</DialogTitle>
            <DialogDescription className="max-w-md text-sm leading-6 text-[#8A8A8A]">
              管理当前工作台身份和通知接收方式。
            </DialogDescription>
          </DialogHeader>

          <div className="mt-7 border-y border-[#242424]">
            <label className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm sm:grid-cols-[150px_1fr] sm:items-center">
              <span className="flex items-center gap-2 text-[#C7C7C7]">
                <User className="h-4 w-4 text-[#8A8A8A]" />
                显示名称
              </span>
              <Input
                data-testid="ui-lab-account-input-displayName"
                value={accountDraft.displayName}
                placeholder="输入显示名称"
                onChange={(event) => updateDraft("displayName", event.target.value)}
              />
            </label>
            <label className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm sm:grid-cols-[150px_1fr] sm:items-center">
              <span className="flex items-center gap-2 text-[#C7C7C7]">
                <Mail className="h-4 w-4 text-[#8A8A8A]" />
                通知邮箱
              </span>
              <Input
                data-testid="ui-lab-account-input-notificationEmail"
                value={accountDraft.notificationEmail}
                placeholder="输入通知邮箱"
                onChange={(event) => updateDraft("notificationEmail", event.target.value)}
              />
            </label>
            {accountRows.map(([label, value]) => (
              <div
                key={label}
                className="grid gap-2 border-b border-[#1A1A1A] px-1 py-4 text-sm last:border-b-0 sm:grid-cols-[150px_1fr]"
              >
                <div className="flex items-center gap-2 text-[#C7C7C7]">
                  <KeyRound className="h-4 w-4 text-[#8A8A8A]" />
                  {label}
                </div>
                <div className="text-[#8A8A8A]">{value}</div>
              </div>
            ))}
          </div>
          {adapter?.loading ? (
            <div className="mt-3 text-xs text-[#8A8A8A]">正在读取账户信息</div>
          ) : null}
          {adapter?.errorMessage ? (
            <div className="mt-3 text-xs text-[#D97757]">账户信息暂时无法保存</div>
          ) : null}

          <Separator className="my-7" />

          <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              关闭
            </Button>
            <Button
              disabled={adapter?.saving}
              onClick={() => {
                adapter?.onSave?.(accountDraft);
                if (!adapter?.onSave) {
                  onOpenChange(false);
                }
              }}
            >
              {adapter?.saving ? "保存中..." : "保存账户信息"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
