import { Activity, BarChart3, Timer, Wallet, Workflow } from "lucide-react";

const linePoints = [
  [8, 72],
  [28, 58],
  [48, 66],
  [68, 42],
  [88, 46],
  [108, 28],
  [128, 36],
  [148, 20],
  [168, 30],
] as const;

const bars = [44, 68, 52, 82, 58, 74, 48, 64];

const metrics = [
  { label: "运行次数", value: "128", hint: "近 7 天", icon: Workflow },
  { label: "成功率", value: "91%", hint: "灰阶状态", icon: Activity },
  { label: "平均耗时", value: "6m 42s", hint: "单次运行", icon: Timer },
  { label: "成本估算", value: "$18.6", hint: "本周", icon: Wallet },
];

export function ChartPreview() {
  const path = linePoints.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ");

  return (
    <>
      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
          <BarChart3 className="h-4 w-4 text-[#8A8A8A]" />
          Chart / 图表组件样张
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-[22px] border border-[#2A2A2A] bg-black p-4">
            <div className="mb-4 flex items-center justify-between text-sm">
              <span className="text-white">极简折线图</span>
              <span className="text-[#8A8A8A]">运行趋势</span>
            </div>
            <svg viewBox="0 0 176 92" className="h-32 w-full overflow-visible" role="img" aria-label="灰阶折线图">
              <path d="M 8 82 H 168" stroke="#2A2A2A" strokeWidth="1" />
              <path d="M 8 58 H 168" stroke="#1F1F1F" strokeWidth="1" />
              <path d="M 8 34 H 168" stroke="#1F1F1F" strokeWidth="1" />
              <path d={path} fill="none" stroke="#C7C7C7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              {linePoints.map(([x, y]) => (
                <circle key={`${x}-${y}`} cx={x} cy={y} fill="#000000" r="3" stroke="#C7C7C7" strokeWidth="1.5" />
              ))}
            </svg>
          </div>

          <div className="rounded-[22px] border border-[#2A2A2A] bg-black p-4">
            <div className="mb-4 flex items-center justify-between text-sm">
              <span className="text-white">极简柱状图</span>
              <span className="text-[#8A8A8A]">任务吞吐</span>
            </div>
            <div className="flex h-32 items-end gap-3">
              {bars.map((height, index) => (
                <div key={`${height}-${index}`} className="flex flex-1 items-end rounded-full bg-[#1A1A1A]">
                  <div
                    className="w-full rounded-full bg-[#C7C7C7]"
                    style={{ height: `${height}%`, opacity: 0.36 + index * 0.04 }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-[#2A2A2A] py-7">
        <div className="mb-4 text-sm font-semibold text-white">Metric / 指标组件样张</div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <div key={metric.label} className="rounded-2xl px-3 py-3 transition-colors hover:bg-[#1F1F1F]">
                <div className="mb-3 flex items-center gap-2 text-xs text-[#8A8A8A]">
                  <Icon className="h-4 w-4" />
                  {metric.label}
                </div>
                <div className="text-xl font-semibold text-white">{metric.value}</div>
                <div className="mt-1 text-xs text-[#5F5F5F]">{metric.hint}</div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
