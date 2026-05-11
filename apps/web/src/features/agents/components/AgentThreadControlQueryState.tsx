export function AgentThreadSessionsLoadingState() {
  return (
    <div className="border-y border-dashed border-[#333333] px-1 py-5 text-sm text-slate-400">
      正在加载会话数据...
    </div>
  );
}

export function AgentThreadSessionsErrorState(props: { message: string }) {
  return (
    <div className="border-y border-rose-500/30 px-1 py-5 text-sm text-rose-100">
      会话加载失败：{props.message}
    </div>
  );
}

export function AgentThreadTimelineErrorState(props: { message: string }) {
  return (
    <div className="border-y border-rose-500/30 px-1 py-5 text-sm text-rose-100">
      时间线加载失败：{props.message}
    </div>
  );
}

export function AgentThreadInterventionsErrorState(props: { message: string }) {
  return (
    <div className="border-y border-rose-500/30 px-1 py-5 text-sm text-rose-100">
      介入记录加载失败：{props.message}
    </div>
  );
}
