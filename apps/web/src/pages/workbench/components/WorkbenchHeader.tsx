type WorkbenchHeaderProps = {
  backendStatus: string | null | undefined;
  realtimeStatus: string;
  lastUpdatedText: string;
  selectedProjectName: string;
  selectedProjectId: string;
};

export function WorkbenchHeader({
  backendStatus,
  realtimeStatus,
  lastUpdatedText,
  selectedProjectName,
  selectedProjectId,
}: WorkbenchHeaderProps) {
  const isRealtimeOpen = realtimeStatus === "open";
  const isRealtimeReconnecting = realtimeStatus === "reconnecting";
  const isRealtimeUnsupported = realtimeStatus === "unsupported";

  return (
    <header
      data-testid="workbench-header"
      className="relative pb-5 border-b border-zinc-850"
    >
      <div className="relative z-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          {/* Breadcrumb */}
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-600">
            <span>控制台工作台</span>
            <span>/</span>
            <span>AI 开发编排平台</span>
            <span>/</span>
            <span className="text-zinc-500">工作台</span>
          </div>

          {/* Simple Clean White Title */}
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <span>AI 项目主管工作台</span>
            <span className="text-[10px] font-normal text-zinc-500 border border-zinc-800 bg-zinc-950 px-1.5 py-0.5 rounded">v0.9</span>
          </h1>

          {/* Project Name Context */}
          <p className="text-xs text-zinc-400 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
            {selectedProjectId === "all" ? (
              <span className="font-medium text-zinc-400">全部项目总览</span>
            ) : (
              <span>
                当前项目：<span className="font-semibold text-zinc-300">{selectedProjectName}</span>
              </span>
            )}
          </p>
        </div>

        {/* Minimalist Status Indicators */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          {/* Backend Connection */}
          {backendStatus === "ok" ? (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/20 px-2.5 py-0.5 text-[11px] text-zinc-400">
              <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
              <span>后端在线</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/20 px-2.5 py-0.5 text-[11px] text-zinc-400">
              <span className="flex h-1.5 w-1.5 rounded-full bg-amber-500" />
              <span>后端未知</span>
            </div>
          )}

          {/* Realtime Stream */}
          {isRealtimeOpen ? (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/20 px-2.5 py-0.5 text-[11px] text-zinc-400">
              <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
              <span>实时已连接</span>
            </div>
          ) : isRealtimeReconnecting ? (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/20 px-2.5 py-0.5 text-[11px] text-zinc-400">
              <span className="flex h-1.5 w-1.5 rounded-full bg-amber-500" />
              <span>实时重连中</span>
            </div>
          ) : isRealtimeUnsupported ? (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/20 px-2.5 py-0.5 text-[11px] text-zinc-400">
              <span className="flex h-1.5 w-1.5 rounded-full bg-rose-500" />
              <span>实时连接不可用</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/20 px-2.5 py-0.5 text-[11px] text-zinc-400">
              <span className="flex h-1.5 w-1.5 rounded-full bg-zinc-600 animate-pulse" />
              <span>实时连接中</span>
            </div>
          )}

          {/* Sync Time */}
          <div className="flex items-center gap-1 text-[11px] text-zinc-500 border-l border-zinc-850 pl-2.5">
            <span>更新 {lastUpdatedText}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
