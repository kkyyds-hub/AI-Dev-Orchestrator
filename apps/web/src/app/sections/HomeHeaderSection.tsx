import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";

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
  "rounded-md border border-zinc-200 bg-transparent px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-600";
const secondaryButtonClass =
  "rounded-md border border-[#333333] bg-transparent px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:text-zinc-600";

export function HomeHeaderSection(props: HomeHeaderSectionProps) {
  return (
    <header
      data-testid="home-header-section"
      className="border-b border-[#333333] pb-7"
    >
      <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0 space-y-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">
              AI 工作台
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
              集中查看任务队列、运行状态与预算信号。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span className="rounded-full border border-[#333333] px-3 py-1">
              中文 AI 工作台
            </span>
            <StatusBadge
              label={props.backendStatus === "ok" ? "后端在线" : "后端状态未知"}
              tone={props.backendStatus === "ok" ? "success" : "warning"}
            />
            <StatusBadge
              label={mapRealtimeLabel(props.realtimeStatus)}
              tone={mapRealtimeTone(props.realtimeStatus)}
            />
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:items-end">
          <div className="flex flex-wrap items-center gap-2 xl:justify-end">
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
              {props.isRunWorkerPoolOncePending ? "Worker Pool 运行中..." : "执行 Worker Pool"}
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

          <dl className="grid gap-x-4 gap-y-2 text-xs text-zinc-500 sm:grid-cols-3 xl:text-right">
            <HeaderMeta label="服务" value={props.backendService ?? "orchestrator-backend"} />
            <HeaderMeta label="更新时间" value={props.lastUpdatedText} />
            <HeaderMeta
              label="最近事件"
              value={
                props.realtimeLastEventType
                  ? `${props.realtimeLastEventType} @ ${formatDateTime(props.realtimeLastEventAt)}`
                  : "暂无事件"
              }
            />
          </dl>
        </div>
      </div>
    </header>
  );
}

function HeaderMeta(props: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] tracking-[0.14em] text-zinc-600">{props.label}</dt>
      <dd className="mt-1 truncate text-zinc-300">{props.value}</dd>
    </div>
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
      return "实时连接已建立";
    case "reconnecting":
      return "实时重连中";
    case "unsupported":
      return "SSE 不可用";
    default:
      return "实时连接中";
  }
}
