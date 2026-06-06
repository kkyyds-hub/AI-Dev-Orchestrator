import { useState } from "react";

type WorkerHumanApprovalConfirmDialogProps = {
  open: boolean;
  isSubmitting: boolean;
  errorMessage: string | null;
  proposedCommitMessage: string;
  changedFiles: string[];
  changedFilesCount: number;
  worktreePath: string | null;
  branchName: string | null;
  operationSource: string | null;
  gateSource: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

export const DELIVERY_HUMAN_APPROVAL_CONFIRMATION_TEXT =
  "我确认提交预览内容，可进入下一阶段安全检查。";

export function WorkerHumanApprovalConfirmDialog(
  props: WorkerHumanApprovalConfirmDialogProps,
) {
  const [checked, setChecked] = useState(false);

  if (!props.open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="worker-human-approval-title"
    >
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl border border-[#3a3a3a] bg-[#181818] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              id="worker-human-approval-title"
              className="text-base font-semibold text-zinc-100"
            >
              确认提交预览
            </h2>
            <p className="mt-2 text-sm leading-6 text-zinc-300">
              确认后不会立即提交代码。系统只会记录你的确认，并进入下一阶段写入前安全检查。
              当前不会执行 git add、git commit、git push 或创建 PR。
            </p>
          </div>
          <button
            type="button"
            onClick={props.onCancel}
            className="rounded-lg border border-[#3a3a3a] px-3 py-1 text-xs text-zinc-300 transition hover:bg-[#242424]"
          >
            关闭
          </button>
        </div>

        <section className="mt-4 rounded-xl border border-[#333333] bg-[#202020] p-3">
          <div className="text-xs tracking-[0.2em] text-zinc-500">提交预览内容</div>
          <div className="mt-3">
            <div className="text-xs text-zinc-500">提交说明</div>
            <div className="mt-1 break-all rounded-lg border border-[#333333] bg-[#161616] p-3 text-sm text-zinc-100">
              {props.proposedCommitMessage}
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-center justify-between gap-3 text-xs text-zinc-500">
              <span>涉及文件</span>
              <span>{props.changedFilesCount} 个</span>
            </div>
            <ul className="mt-2 max-h-40 space-y-1 overflow-auto rounded-lg border border-[#333333] bg-[#161616] p-3 text-xs leading-5 text-zinc-300">
              {props.changedFiles.map((file) => (
                <li key={file} className="break-all">
                  {file}
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <DialogInfo label="预览动作" value="提交预览" />
            <DialogInfo label="工作区" value={formatNullable(props.worktreePath)} />
            <DialogInfo label="目标分支" value={formatNullable(props.branchName)} />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <DialogInfo label="提交预览证据" value={formatNullable(props.operationSource)} />
            <DialogInfo label="交付前检查证据" value={formatNullable(props.gateSource)} />
          </div>
        </section>

        <label className="mt-4 flex gap-3 rounded-xl border border-[#333333] bg-[#202020] p-3 text-sm leading-6 text-zinc-200">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 accent-[#8ea2ff]"
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
          />
          <span>{DELIVERY_HUMAN_APPROVAL_CONFIRMATION_TEXT}</span>
        </label>

        {props.errorMessage ? (
          <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm leading-6 text-amber-100">
            {props.errorMessage}
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={props.onCancel}
            className="rounded-lg border border-[#3a3a3a] px-4 py-2 text-sm text-zinc-200 transition hover:bg-[#242424]"
          >
            取消
          </button>
          <button
            type="button"
            disabled={!checked || props.isSubmitting}
            onClick={props.onConfirm}
            className="rounded-lg border border-[#8ea2ff] bg-[#8ea2ff] px-4 py-2 text-sm font-medium text-[#111111] transition disabled:cursor-not-allowed disabled:opacity-50"
          >
            {props.isSubmitting ? "正在记录确认..." : "确认提交预览"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DialogInfo(props: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#333333] bg-[#161616] p-3">
      <div className="text-xs text-zinc-500">{props.label}</div>
      <div className="mt-1 break-all text-xs text-zinc-200">{props.value}</div>
    </div>
  );
}

function formatNullable(value: string | null): string {
  return value && value.trim().length > 0 ? value : "未记录";
}
