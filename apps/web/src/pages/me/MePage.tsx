import { Link } from "react-router-dom";

const accountCapabilityGroups = [
  {
    title: "账户资料",
    status: "预留结构",
    description: "后续登录后展示头像、昵称、邮箱、组织身份与个人资料编辑入口。",
    items: ["基础资料", "组织与角色", "资料编辑"],
  },
  {
    title: "安全与登录",
    status: "待接登录注册",
    description: "后续承接密码、登录方式、多因素验证、登录设备与退出登录。",
    items: ["账号密码", "登录方式", "退出登录"],
  },
  {
    title: "个人偏好",
    status: "预留结构",
    description: "后续保存语言、通知、默认项目、工作台显示等个人级偏好。",
    items: ["显示偏好", "通知偏好", "默认入口"],
  },
] as const;

const authFlowSteps = [
  {
    title: "注册账号",
    description: "未来新用户先完成注册，注册成功后再进入系统。当前版本不提供注册表单。",
  },
  {
    title: "登录验证",
    description: "未来通过账号密码或其他登录方式建立真实会话。当前版本不模拟登录态。",
  },
  {
    title: "进入账户中心",
    description: "登录后在这里管理资料、安全、偏好与退出登录。当前仅展示接入结构。",
  },
] as const;

const realEntryLinks = [
  {
    title: "系统设置",
    description: "查看环境、连接状态与平台级配置。",
    to: "/settings",
  },
  {
    title: "项目中心",
    description: "进入项目域，管理项目总览与项目内上下文。",
    to: "/projects",
  },
  {
    title: "工作台",
    description: "返回当前真实工作入口，查看任务、状态与运行概览。",
    to: "/workbench",
  },
] as const;

export function MePage() {
  return (
    <div className="space-y-7" data-testid="account-center-page">
      <section className="border-b border-[#333333] pb-6">
        <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
          Account Center
        </div>
        <div className="mt-3 grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-end">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">
              我的账户
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-500">
              这里收口为账户中心，不再聚合任务、项目、审批或交付物。后续登录 / 注册上线后，
              本页承接个人资料、账号安全、登录方式、个人偏好与退出登录。
            </p>
          </div>
          <AccessStateCard />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3" aria-label="账户中心状态概览">
        <StateMetric label="访问状态" value="直接访问" helper="账号登录未启用" />
        <StateMetric label="登录 / 注册" value="未接入" helper="不模拟登录态" />
        <StateMetric label="页面职责" value="账户中心" helper="不承接工作聚合" />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <AuthFlowSection />
          <AccountCapabilitySection />
        </div>
        <RealEntrySection />
      </section>
    </div>
  );
}

function AccessStateCard() {
  return (
    <aside className="rounded-2xl border border-[#333333] bg-[#202020] p-4" data-testid="account-access-state">
      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-600">
        当前访问状态
      </div>
      <div className="mt-3 text-base font-semibold text-zinc-100">
        当前环境直接访问，账号登录未启用
      </div>
      <p className="mt-2 text-sm leading-6 text-zinc-500">
        本页不会展示假用户、假登录、假注册或后端未提供的账号数据；所有账号能力仅作为后续接入结构说明。
      </p>
    </aside>
  );
}

function StateMetric(props: { label: string; value: string; helper: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">{props.label}</div>
      <div className="mt-2 text-xl font-semibold text-zinc-100">{props.value}</div>
      <div className="mt-1 text-xs leading-5 text-zinc-500">{props.helper}</div>
    </div>
  );
}

function AuthFlowSection() {
  return (
    <section className="space-y-3" data-testid="account-auth-flow">
      <div className="border-b border-[#333333] pb-3">
        <h2 className="text-lg font-semibold text-zinc-100">登录注册流程</h2>
        <p className="mt-1 text-sm leading-6 text-zinc-500">
          只展示未来流程边界，不提供假按钮、不写入假账号、不新增接口。
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {authFlowSteps.map((step, index) => (
          <article key={step.title} className="rounded-2xl border border-[#333333] bg-[#202020] p-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-500/30 text-sm font-semibold text-zinc-300">
              {index + 1}
            </div>
            <h3 className="mt-4 text-sm font-semibold text-zinc-100">{step.title}</h3>
            <p className="mt-2 text-xs leading-5 text-zinc-500">{step.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function AccountCapabilitySection() {
  return (
    <section className="space-y-3" data-testid="account-capability-layout">
      <div className="border-b border-[#333333] pb-3">
        <h2 className="text-lg font-semibold text-zinc-100">账户中心布局</h2>
        <p className="mt-1 text-sm leading-6 text-zinc-500">
          账户资料、安全登录、个人偏好分区保留稳定位置，等待真实登录体系接入。
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {accountCapabilityGroups.map((group) => (
          <article key={group.title} className="rounded-2xl border border-[#333333] bg-[#202020] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-zinc-100">{group.title}</h3>
              <span className="rounded-full border border-[#3a3a3a] px-2 py-1 text-[11px] text-zinc-500">
                {group.status}
              </span>
            </div>
            <p className="mt-3 text-xs leading-5 text-zinc-500">{group.description}</p>
            <ul className="mt-4 space-y-2 text-xs text-zinc-400">
              {group.items.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-zinc-600" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function RealEntrySection() {
  return (
    <section className="space-y-3" data-testid="account-real-entry-links">
      <div className="border-b border-[#333333] pb-3">
        <h2 className="text-lg font-semibold text-zinc-100">真实可用入口</h2>
        <p className="mt-1 text-sm leading-6 text-zinc-500">
          账户能力未启用时，仅保留不会伪造登录状态的真实页面入口。
        </p>
      </div>

      <div className="divide-y divide-[#333333] border-y border-[#333333]">
        {realEntryLinks.map((entry) => (
          <Link key={entry.to} to={entry.to} className="block px-2 py-3 transition hover:bg-[#292929]">
            <div className="text-sm font-medium text-zinc-100">{entry.title}</div>
            <div className="mt-1 text-xs leading-5 text-zinc-500">{entry.description}</div>
          </Link>
        ))}
      </div>

      <div className="rounded-2xl border border-dashed border-[#3a3a3a] p-4 text-xs leading-5 text-zinc-500">
        任务中心、项目中心、审批中心、交付物中心继续由各自页面负责；本页不再复制它们的列表、统计或处理入口。
      </div>
    </section>
  );
}
