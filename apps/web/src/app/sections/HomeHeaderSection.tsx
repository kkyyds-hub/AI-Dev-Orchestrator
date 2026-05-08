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
      className="rounded-[28px] border border-slate-800/90 bg-slate-950/70 px-5 py-5 shadow-2xl shadow-black/25 ring-1 ring-white/[0.03] lg:px-6"
    >
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-slate-400">
              Workbench
            </span>
            <StatusBadge
              label={props.backendStatus === "ok" ? "Backend online" : "Backend unknown"}
              tone={props.backendStatus === "ok" ? "success" : "warning"}
            />
            <StatusBadge
              label={mapRealtimeLabel(props.realtimeStatus)}
              tone={mapRealtimeTone(props.realtimeStatus)}
            />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
              AI Workbench Console
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              A clean control surface for task queues, runtime state, budget guardrails, and human intervention signals.
            </p>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-3 xl:items-end">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              data-testid="home-run-worker-once"
              onClick={props.onRunWorkerOnce}
              disabled={props.isRunWorkerOncePending}
              className="rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3.5 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
            >
              {props.isRunWorkerOncePending ? "Running..." : "Run Worker Once"}
            </button>
            <button
              type="button"
              onClick={props.onRunWorkerPoolOnce}
              disabled={props.isRunWorkerPoolOncePending}
              className="rounded-xl border border-cyan-400/25 bg-cyan-500/10 px-3.5 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
            >
              {props.isRunWorkerPoolOncePending ? "Pool running..." : "Run Worker Pool"}
            </button>
            <button
              type="button"
              onClick={props.onRefresh}
              className="rounded-xl border border-slate-700 bg-slate-900/80 px-3.5 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
            >
              Refresh
            </button>
          </div>

          <dl className="grid gap-2 text-xs text-slate-500 sm:grid-cols-3 xl:text-right">
            <HeaderMeta label="Service" value={props.backendService ?? "orchestrator-backend"} />
            <HeaderMeta label="Updated" value={props.lastUpdatedText} />
            <HeaderMeta
              label="Last event"
              value={
                props.realtimeLastEventType
                  ? `${props.realtimeLastEventType} @ ${formatDateTime(props.realtimeLastEventAt)}`
                  : "No events yet"
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
    <div className="min-w-0 rounded-2xl border border-slate-800/80 bg-slate-950/70 px-3 py-2">
      <dt className="text-[11px] uppercase tracking-[0.18em] text-slate-600">{props.label}</dt>
      <dd className="mt-1 truncate text-slate-300">{props.value}</dd>
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
      return "Realtime connected";
    case "reconnecting":
      return "Realtime reconnecting";
    case "unsupported":
      return "SSE unavailable";
    default:
      return "Realtime connecting";
  }
}
