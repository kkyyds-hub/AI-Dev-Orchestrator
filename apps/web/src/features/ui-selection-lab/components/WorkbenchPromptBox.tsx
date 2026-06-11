import { ArrowUp } from "lucide-react";
import { useCallback, useRef, useState } from "react";

interface WorkbenchPromptBoxProps {
  onSend: (text: string) => void;
}

export function WorkbenchPromptBox({ onSend }: WorkbenchPromptBoxProps) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasText = text.trim().length > 0;

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  const isActive = focused || hasText;

  return (
    <div
      data-testid="ui-lab-promptbox"
      className="absolute bottom-5 left-1/2 max-w-[calc(100%-40px)] -translate-x-1/2 md:bottom-7 lg:bottom-9"
      style={{ width: "min(760px, calc(100vw - var(--lab-sidebar-width) - 64px))" }}
    >
      <div
        className={`flex min-h-16 items-end gap-4 rounded-[24px] border bg-[#161616]/95 px-4 py-3 shadow-2xl shadow-black/70 ring-1 ring-white/[0.03] backdrop-blur-md transition-all duration-150 md:min-h-[72px] md:px-5 md:py-4 ${
          isActive ? "border-[#3A3A3A]" : "border-[#333333]"
        }`}
      >
        <textarea
          ref={textareaRef}
          className="min-w-0 flex-1 resize-none bg-transparent pt-0.5 text-sm text-white outline-none placeholder:text-[#8A8A8A]"
          placeholder="输入你的目标、需求或执行结果..."
          rows={1}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />
        <button
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-150 active:scale-[0.96] ${
            hasText
              ? "bg-white text-black hover:bg-[#E7E7E7]"
              : "bg-[#2C2C2C] text-[#5F5F5F]"
          }`}
          onClick={handleSend}
          disabled={!hasText}
          aria-label="发送"
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
