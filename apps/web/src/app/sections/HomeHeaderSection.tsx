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

export function HomeHeaderSection(props: HomeHeaderSectionProps) {
  return (
    <header
      data-testid="home-header-section"
      className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/40 lg:flex-row lg:items-end lg:justify-between"
    >
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          Day 15 Console
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">
          AI Dev Orchestrator 预算守卫控制台
        </h1>
        <p className="max-w-3xl text-sm text-slate-300">
          在 Day 14 验证闸门基础上，补齐预算守卫、阻塞原因和失败重试边界。
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:items-end">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge
            label={props.backendStatus === "ok" ? "后端在线" : "后端未知"}
            tone={props.backendStatus === "ok" ? "success" : "warning"}
          />
          <StatusBadge
            label={mapRealtimeLabel(props.realtimeStatus)}
            tone={mapRealtimeTone(props.realtimeStatus)}
          />
          <button
            type="button"
            data-testid="home-run-worker-once"
            onClick={props.onRunWorkerOnce}
            disabled={props.isRunWorkerOncePending}
            className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
          >
            {props.isRunWorkerOncePending ? "执行中..." : "执行 Worker 一次"}
          </button>
          <button
            type="button"
            onClick={props.onRunWorkerPoolOnce}
            disabled={props.isRunWorkerPoolOncePending}
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
          >
            {props.isRunWorkerPoolOncePending ? "并行执行中..." : "执行 Worker Pool"}
          </button>
          <button
            type="button"
            onClick={props.onRefresh}
            className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
          >
            刷新控制台
          </button>
        </div>
        <div className="text-right text-sm text-slate-400">
          <div>服务：{props.backendService ?? "orchestrator-backend"}</div>
          <div>最近刷新：{props.lastUpdatedText}</div>
          <div>
            最近事件：
            {props.realtimeLastEventType
              ? `${props.realtimeLastEventType} @ ${formatDateTime(props.realtimeLastEventAt)}`
              : "尚未收到"}
          </div>
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
