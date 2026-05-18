import { StatusBadge } from "../../../components/StatusBadge";

type WorkbenchHeaderProps = {
  backendStatus: string | null | undefined;
  realtimeStatus: string;
  lastUpdatedText: string;
  selectedProjectName: string;
  selectedProjectId: string;
};

function mapRealtimeTone(status: string) {
  switch (status) {
    case "open":
      return "success" as const;
    case "reconnecting":
      return "warning" as const;
    case "unsupported":
      return "danger" as const;
    default:
      return "info" as const;
  }
}

function mapRealtimeLabel(status: string) {
  switch (status) {
    case "open":
      return "实时已连接";
    case "reconnecting":
      return "实时重连中";
    case "unsupported":
      return "实时连接不可用";
    default:
      return "实时连接中";
  }
}

export function WorkbenchHeader({
  backendStatus,
  realtimeStatus,
  lastUpdatedText,
  selectedProjectName,
  selectedProjectId,
}: WorkbenchHeaderProps) {
  return (
    <header
      data-testid="workbench-header"
      className="border-b border-[#333333] pb-5"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            AI 项目主管工作台
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {selectedProjectId === "all"
              ? "全部项目总览"
              : `当前项目：${selectedProjectName}`}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
          <StatusBadge
            label={backendStatus === "ok" ? "后端在线" : "后端未知"}
            tone={backendStatus === "ok" ? "success" : "warning"}
          />
          <StatusBadge
            label={mapRealtimeLabel(realtimeStatus)}
            tone={mapRealtimeTone(realtimeStatus)}
          />
          <span className="text-zinc-600">更新 {lastUpdatedText}</span>
        </div>
      </div>
    </header>
  );
}
