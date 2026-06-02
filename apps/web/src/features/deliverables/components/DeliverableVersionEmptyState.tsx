const EMPTY_TEXT = "\u8bf7\u5148\u4ece\u5de6\u4fa7\u9009\u62e9\u4e00\u4e2a\u4ea4\u4ed8\u7269\uff0c\u518d\u67e5\u770b\u53f3\u4fa7\u6458\u8981\u3001\u6b63\u6587\u3001\u8bc1\u636e\u4e0e\u7248\u672c\u8bb0\u5f55\u5165\u53e3\u3002";

export function DeliverableVersionEmptyState() {
  return (
    <section className="border border-dashed border-[#3a3a3a] px-4 py-6 text-sm leading-6 text-zinc-400">
      {EMPTY_TEXT}
    </section>
  );
}
