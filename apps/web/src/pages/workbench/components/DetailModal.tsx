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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-modal-backdrop"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-2xl border border-zinc-900 bg-zinc-950 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.9)] flex flex-col animate-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-900 px-6 py-4 bg-zinc-950/40">
          <h3 className="text-sm font-bold tracking-tight text-zinc-100 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-500"></span>
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 custom-scrollbar bg-black">
          {children}
        </div>

        {/* Footer */}
        <div className="border-t border-zinc-900 px-6 py-3.5 bg-zinc-950/40 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 hover:border-zinc-700 transition"
          >
            关闭窗口
          </button>
        </div>
      </div>
    </div>
  );
}
