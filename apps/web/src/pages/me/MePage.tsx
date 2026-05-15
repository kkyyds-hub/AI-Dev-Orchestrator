import { Link } from "react-router-dom";

type SettingGroup = {
  id: string;
  title: string;
  items: SettingRow[];
};

type SettingRow = {
  title: string;
  value: string;
};

const settingGroups: SettingGroup[] = [
  {
    id: "profile",
    title: "账户资料",
    items: [
      { title: "基本资料", value: "待登录后管理" },
      { title: "组织身份", value: "暂未绑定" },
      { title: "联系方式", value: "待登录后管理" },
    ],
  },
  {
    id: "security",
    title: "安全与登录",
    items: [
      { title: "登录方式", value: "尚未开放" },
      { title: "密码与验证", value: "待登录后管理" },
      { title: "退出登录", value: "尚无会话" },
    ],
  },
  {
    id: "preferences",
    title: "个人偏好",
    items: [
      { title: "默认入口", value: "工作台" },
      { title: "显示偏好", value: "跟随系统" },
      { title: "通知偏好", value: "待登录后管理" },
    ],
  },
];

const quickLinks = [
  { title: "系统设置", to: "/settings" },
  { title: "项目中心", to: "/projects" },
  { title: "工作台", to: "/workbench" },
] as const;

export function MePage() {
  return (
    <div className="space-y-8" data-testid="account-settings-page">
      <header className="border-b border-[#333333] pb-6">
        <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
          Account Settings
        </div>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">我的账户</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-500">
              管理账户资料、安全与个人偏好。
            </p>
          </div>
          <div className="text-left md:text-right" data-testid="account-session-state">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">当前状态</div>
            <div className="mt-2 text-sm font-medium text-zinc-100">直接访问</div>
            <div className="mt-1 text-xs text-zinc-500">账号登录尚未开放</div>
          </div>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
        <AccountSettingsNav />
        <main className="space-y-8">
          {settingGroups.map((group) => (
            <SettingSection key={group.id} group={group} />
          ))}
          <QuickLinksSection />
        </main>
      </div>
    </div>
  );
}

function AccountSettingsNav() {
  return (
    <aside className="lg:sticky lg:top-6 lg:self-start" aria-label="账户设置分组">
      <nav className="space-y-1 border-l border-[#333333] pl-4">
        {settingGroups.map((group) => (
          <a
            key={group.id}
            href={`#${group.id}`}
            className="block py-2 text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            {group.title}
          </a>
        ))}
        <a href="#entries" className="block py-2 text-sm text-zinc-400 transition hover:text-zinc-100">
          快捷入口
        </a>
      </nav>
    </aside>
  );
}

function SettingSection(props: { group: SettingGroup }) {
  return (
    <section id={props.group.id} className="scroll-mt-6" data-testid={`account-section-${props.group.id}`}>
      <h2 className="text-lg font-semibold text-zinc-100">{props.group.title}</h2>
      <div className="mt-3 divide-y divide-[#333333] border-y border-[#333333]">
        {props.group.items.map((item) => (
          <SettingRowView key={item.title} item={item} />
        ))}
      </div>
    </section>
  );
}

function SettingRowView(props: { item: SettingRow }) {
  return (
    <div className="flex flex-col gap-1 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-sm font-medium text-zinc-100">{props.item.title}</div>
      <div className="text-sm text-zinc-500">{props.item.value}</div>
    </div>
  );
}

function QuickLinksSection() {
  return (
    <section id="entries" className="scroll-mt-6" data-testid="account-real-entry-links">
      <h2 className="text-lg font-semibold text-zinc-100">快捷入口</h2>
      <div className="mt-3 divide-y divide-[#333333] border-y border-[#333333]">
        {quickLinks.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className="flex items-center justify-between gap-4 py-4 text-sm transition hover:text-zinc-100"
          >
            <span className="font-medium text-zinc-100">{link.title}</span>
            <span className="text-zinc-500">打开</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
