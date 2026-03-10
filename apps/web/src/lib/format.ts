const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 4,
  maximumFractionDigits: 6,
});

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatCurrencyUsd(value: number): string {
  return currencyFormatter.format(value);
}

export function formatDateTime(isoText: string | null): string {
  if (!isoText) {
    return "—";
  }

  return dateTimeFormatter.format(new Date(isoText));
}

export function formatTokenCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}
