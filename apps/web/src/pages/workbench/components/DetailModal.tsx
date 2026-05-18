import type { ReactNode } from "react";

type DetailModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

export function DetailModal({ open, onClose, title, children }: DetailModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-lg border border-[#333333] bg-[#1a1a1a] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between border-b border-[#333333] pb-3">
          <h3 className="text-lg font-semibold text-zinc-100">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-zinc-400 transition hover:bg-[#2f2f2f] hover:text-zinc-200"
          >
            关闭
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
