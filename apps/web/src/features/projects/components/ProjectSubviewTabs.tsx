import { type ReactNode, useEffect, useMemo, useState } from "react";

export type ProjectSubviewTabItem<TTabId extends string> = {
  id: TTabId;
  label: string;
  panelId?: string;
  content: ReactNode;
};

type ProjectSubviewTabsProps<TTabId extends string> = {
  ariaLabel: string;
  defaultTabId: TTabId;
  items: readonly ProjectSubviewTabItem<TTabId>[];
};

export function ProjectSubviewTabs<TTabId extends string>(
  props: ProjectSubviewTabsProps<TTabId>,
) {
  const resolveTabIdFromHash = () => {
    if (typeof window === "undefined") {
      return props.defaultTabId;
    }

    const hashTargetId =
      window.location.hash.startsWith("#") && window.location.hash.length > 1
        ? window.location.hash.slice(1).split("?")[0]
        : null;
    const hashMatchedItem = props.items.find(
      (item) => item.id === hashTargetId || item.panelId === hashTargetId,
    );

    return hashMatchedItem?.id ?? props.defaultTabId;
  };

  const initialTabId = useMemo(() => {
    return resolveTabIdFromHash();
  }, [props.defaultTabId, props.items]);

  const [activeTabId, setActiveTabId] = useState<TTabId>(initialTabId);
  const activeItem =
    props.items.find((item) => item.id === activeTabId) ?? props.items[0];

  useEffect(() => {
    const syncTabFromHash = () => {
      const hashTabId = resolveTabIdFromHash();
      if (hashTabId !== props.defaultTabId) {
        setActiveTabId(hashTabId);
      }
    };

    syncTabFromHash();
    window.addEventListener("hashchange", syncTabFromHash);
    return () => window.removeEventListener("hashchange", syncTabFromHash);
  }, [props.defaultTabId, props.items]);

  if (!activeItem) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label={props.ariaLabel}
        className="flex gap-1 overflow-x-auto rounded-3xl border border-[#333333] bg-[#242424] p-2"
      >
        {props.items.map((item) => {
          const isActive = item.id === activeItem.id;

          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={item.panelId ?? item.id}
              onClick={() => setActiveTabId(item.id)}
              className={`min-w-max rounded-2xl px-4 py-2.5 text-sm font-medium transition ${
                isActive
                  ? "bg-[#303030] text-zinc-50 shadow-sm shadow-black/20"
                  : "text-zinc-500 hover:bg-[#292929] hover:text-zinc-200"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div
        id={activeItem.panelId ?? activeItem.id}
        role="tabpanel"
        className="min-w-0"
      >
        {activeItem.content}
      </div>
    </div>
  );
}
