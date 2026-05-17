import ReactMarkdown from "react-markdown";

const ALLOWED_ELEMENTS = [
  "h2",
  "p",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "code",
  "pre",
  "br",
];

/**
 * Safe Markdown renderer for AI run summaries.
 *
 * Only renders a whitelist of structural / inline elements.
 * All HTML tags are stripped (`skipHtml`).
 */
export function RunAiSummaryMarkdown({ markdown }: { markdown: string }) {
  return (
    <div className="break-words">
      <ReactMarkdown
        skipHtml
        allowedElements={ALLOWED_ELEMENTS}
        components={{
          h2: ({ children, ...props }) => (
            <h2
              className="mt-5 mb-2 text-xs font-semibold text-zinc-300 first:mt-0"
              {...props}
            >
              {children}
            </h2>
          ),
          p: ({ children, ...props }) => (
            <p className="text-sm leading-6 text-zinc-400" {...props}>
              {children}
            </p>
          ),
          ul: ({ children, ...props }) => (
            <ul className="mt-1 space-y-1 pl-4 list-disc list-outside" {...props}>
              {children}
            </ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className="mt-1 space-y-1 pl-4 list-decimal list-outside" {...props}>
              {children}
            </ol>
          ),
          li: ({ children, ...props }) => (
            <li className="text-sm leading-6 text-zinc-400" {...props}>
              {children}
            </li>
          ),
          strong: ({ children, ...props }) => (
            <strong className="font-semibold text-zinc-300" {...props}>
              {children}
            </strong>
          ),
          em: ({ children, ...props }) => (
            <em className="italic text-zinc-400" {...props}>
              {children}
            </em>
          ),
          code: ({ children, ...props }) => (
            <code
              className="inline-block max-w-full rounded border border-[#333333] bg-[#0a0a0a] px-1 text-xs text-zinc-300 break-all align-baseline"
              {...props}
            >
              {children}
            </code>
          ),
          pre: ({ children, ...props }) => (
            <pre
              className="mt-2 max-h-72 overflow-auto rounded border border-[#333333] bg-[#0a0a0a] p-3 text-xs leading-5 text-zinc-300 whitespace-pre-wrap break-all"
              {...props}
            >
              {children}
            </pre>
          ),
          br: ({ ...props }) => <br {...props} />,
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
