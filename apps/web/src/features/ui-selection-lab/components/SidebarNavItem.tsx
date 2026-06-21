import type * as React from "react";

import { cn } from "../../../lib/cn";
import { Badge } from "./ui";

type SidebarNavItemProps = {
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  active?: boolean;
  hover?: boolean;
  muted?: boolean;
  badge?: string;
  className?: string;
  onClick?: () => void;
};

export function SidebarNavItem({
  label,
  icon: Icon,
  active,
  hover,
  muted,
  badge,
  className,
  onClick,
}: SidebarNavItemProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.();
      }}
      className={cn(
        "flex h-9 cursor-pointer items-center gap-3 rounded-md px-3 text-sm transition-all duration-150 active:scale-[0.99]",
        active && "bg-[#2C2C2C] text-white",
        hover && "bg-[#222222] text-white",
        !active && !hover && (muted ? "text-[#5F5F5F]" : "text-[#C7C7C7]"),
        "hover:bg-[#222222] hover:text-white",
        className,
      )}
    >
      {Icon ? <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge ? <Badge className="h-5 border-[#3A3A3A] bg-[#2C2C2C] text-[11px] text-white">{badge}</Badge> : null}
    </div>
  );
}
