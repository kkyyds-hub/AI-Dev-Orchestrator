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

export const NA_TEXT = "n/a";

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

export function formatNullableText(value: string | null | undefined): string {
  if (!value) {
    return NA_TEXT;
  }

  const normalized = value.trim();
  return normalized.length ? normalized : NA_TEXT;
}

export function formatNullableCurrencyUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return NA_TEXT;
  }

  return formatCurrencyUsd(value);
}

export function formatNullableTokenCount(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return NA_TEXT;
  }

  return formatTokenCount(value);
}

export function formatTokenBreakdown(input: {
  promptTokens: number | null | undefined;
  completionTokens: number | null | undefined;
  totalTokens: number | null | undefined;
}): string {
  const derivedTotalTokens =
    input.totalTokens ??
    (input.promptTokens !== null &&
    input.promptTokens !== undefined &&
    input.completionTokens !== null &&
    input.completionTokens !== undefined
      ? input.promptTokens + input.completionTokens
      : null);

  return `${formatNullableTokenCount(input.promptTokens)} / ${formatNullableTokenCount(
    input.completionTokens,
  )} / ${formatNullableTokenCount(derivedTotalTokens)}`;
}
