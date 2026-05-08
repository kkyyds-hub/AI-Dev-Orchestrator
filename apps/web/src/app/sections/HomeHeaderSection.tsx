import { StatusBadge } from "../../components/StatusBadge";

type HomeHeaderSectionProps = {
  backendStatus: string | null | undefined;
  backendService: string | null | undefined;
  realtimeStatus: string;
  realtimeLastEventType: string | null;
  realtimeLastEventAt: string | null;
  lastUpdatedText: string;
  isRunWorkerOncePending: boolean;
  isRunWorkerPoolOncePending: boolean;
  onRunWorkerOnce: () => void;
  onRunWorkerPoolOnce: () => void;
  onRefresh: () => void;
};

const primaryButtonClass =
  "rounded-md border border-zinc-200 bg-transparent px-3.5 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600";
const secondaryButtonClass =
  "rounded-md border border-[#333333] bg-transparent px-3.5 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:text-zinc-600";

export function HomeHeaderSection(props: HomeHeaderSectionProps) {
  return (
    <header
      data-testid="home-header-section"
      className="border-b border-[#333333] pb-6"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">
            AI 工作台
          </h1>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span className="rounded-full border border-[#333333] px-3 py-1">
              任务队列
            </span>
            <StatusBadge
              label={props.backendStatus === "ok" ? "后端在线" : "后端未知"}
              tone={props.backendStatus === "ok" ? "success" : "warning"}
            />
            <StatusBadge
              label={mapRealtimeLabel(props.realtimeStatus)}
              tone={mapRealtimeTone(props.realtimeStatus)}
            />
            <span className="text-zinc-600">更新 {props.lastUpdatedText}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <button
            type="button"
            data-testid="home-run-worker-once"
            onClick={props.onRunWorkerOnce}
            disabled={props.isRunWorkerOncePending}
            className={primaryButtonClass}
          >
            {props.isRunWorkerOncePending ? "执行中..." : "执行 Worker 一次"}
          </button>
          <button
            type="button"
            data-testid="home-run-worker-pool-once"
            onClick={props.onRunWorkerPoolOnce}
            disabled={props.isRunWorkerPoolOncePending}
            className={secondaryButtonClass}
          >
            {props.isRunWorkerPoolOncePending ? "Pool 运行中..." : "Worker Pool"}
          </button>
          <button
            type="button"
            data-testid="home-refresh"
            onClick={props.onRefresh}
            className={secondaryButtonClass}
          >
            刷新
          </button>
        </div>
      </div>
    </header>
  );
}

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
      return "SSE 不可用";
    default:
      return "实时连接中";
  }
}
