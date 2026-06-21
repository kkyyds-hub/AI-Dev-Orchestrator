import { CheckCircle2, CircleAlert, Clock3, Loader2, X } from "lucide-react";

export type WorkbenchActionToastStatus = "queued" | "processing" | "done" | "failed";

export type WorkbenchActionToastState = {
  message: string;
  status: WorkbenchActionToastStatus;
};

const toastStatusLabel: Record<WorkbenchActionToastStatus, string> = {
  queued: "已排队",
  processing: "处理中",
  done: "已完成",
  failed: "失败",
};

export function WorkbenchActionToast({
  toast,
  onClose,
}: {
  toast: WorkbenchActionToastState | null;
  onClose: () => void;
}) {
  if (!toast) {
    return null;
  }

  const Icon =
    toast.status === "processing"
      ? Loader2
      : toast.status === "queued"
        ? Clock3
        : toast.status === "failed"
          ? CircleAlert
          : CheckCircle2;

  return (
    <div
      data-testid="workbench-action-toast"
      className="fixed bottom-7 left-1/2 z-50 -translate-x-1/2 animate-[uiLabToastLifecycle_3000ms_ease-in-out_forwards]"
      role="status"
      aria-live="polite"
    >
      <div className="flex max-w-[calc(100vw-32px)] items-center gap-3 rounded-full border border-[#3A3A3A] bg-[#202020] px-4 py-2.5 shadow-2xl shadow-black/60">
        <Icon
          className={`h-4 w-4 shrink-0 text-white ${
            toast.status === "processing" ? "animate-spin" : ""
          }`}
        />
        <span className="shrink-0 text-xs text-[#8A8A8A]">
          {toastStatusLabel[toast.status]}
        </span>
        <span className="truncate text-sm text-white">{toast.message}</span>
        <button
          type="button"
          className="ml-1 rounded-full p-0.5 text-[#8A8A8A] transition-colors hover:text-white"
          onClick={onClose}
          aria-label="关闭反馈"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
