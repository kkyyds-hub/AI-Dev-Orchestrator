import { DeliverableCenterMetric } from "./DeliverableCenterMetric";

const EYEBROW = "\u6210\u679c\u4e2d\u5fc3 / \u4ea4\u4ed8\u7269";
const TITLE = "\u4ea4\u4ed8\u7269\u6458\u8981\u4e0e\u8bc1\u636e\u5165\u53e3";
const DESCRIPTION = "\u9ed8\u8ba4\u8bfb\u53d6\u540e\u7aef Deliverable \u517c\u5bb9\u5408\u540c\uff1b\u9875\u9762\u5e38\u9a7b\u8f7b\u5217\u8868\u4e0e\u6458\u8981\u9762\u677f\uff0c\u6b63\u6587\u3001\u8bc1\u636e\u94fe\u548c\u7248\u672c\u8bb0\u5f55\u901a\u8fc7\u5f39\u7a97\u6536\u7eb3\u3002";
const CURRENT_PROJECT = "\u5f53\u524d\u9879\u76ee";
const NO_PROJECT = "\u672a\u9009\u62e9\u9879\u76ee";
const DELIVERABLE_COUNT = "\u4ea4\u4ed8\u7269\u6570\u91cf";
const VERSION_COUNT = "\u7248\u672c\u8bb0\u5f55\u6570";

type DeliverableCenterHeaderProps = {
  projectName: string | null;
  totalDeliverables: number;
  totalVersions: number;
};

export function DeliverableCenterHeader(props: DeliverableCenterHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-zinc-500">
          {EYEBROW}
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-100">
          {TITLE}
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          {DESCRIPTION}
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <DeliverableCenterMetric
          label={CURRENT_PROJECT}
          value={props.projectName ?? NO_PROJECT}
        />
        <DeliverableCenterMetric
          label={DELIVERABLE_COUNT}
          value={String(props.totalDeliverables)}
        />
        <DeliverableCenterMetric
          label={VERSION_COUNT}
          value={String(props.totalVersions)}
        />
      </div>
    </header>
  );
}
