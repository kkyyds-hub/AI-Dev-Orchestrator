const sizes = ["1440x900", "1366x768", "MacBook Air 13.6 browser window", "1280x800"] as const;

export function ResponsiveNotes() {
  return (
    <div className="border-t border-[#2A2A2A] py-7">
      <div className="mb-4 text-sm font-semibold text-white">Responsive acceptance / 响应式验收尺寸</div>
      <div className="grid gap-2 text-sm text-[#8A8A8A] md:grid-cols-2">
        {sizes.map((size) => (
          <div key={size} className="rounded-2xl px-3 py-2 hover:bg-[#1F1F1F]">
            {size}
          </div>
        ))}
      </div>
      <p className="mt-4 text-sm leading-6 text-[#5F5F5F]">
        1440x900 只作为设计参考，Workbench Preview 使用真实视口自适应，组件试验区只允许纵向滚动。
      </p>
    </div>
  );
}
