/** 92333.33 -> "92,333원" (rounded, comma grouped) */
export function formatWon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

/** 70000 -> "70,000" (no suffix) */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return Math.round(value).toLocaleString("ko-KR");
}

/** 417000000000000 -> "417.0조원" */
export function formatMarketCap(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const jo = value / 1_0000_0000_0000; // 1조 = 10^12
  return `${jo.toFixed(1)}조원`;
}

/** decimal -> signed percent, e.g. 0.0717 -> "+7.2%" */
export function formatSignedPercent(
  value: number | null | undefined,
  digits = 1
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

/** decimal -> unsigned percent, e.g. 0.4521 -> "45.2%" */
export function formatPercent(
  value: number | null | undefined,
  digits = 1
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

/** confidence 0..1 -> "40%" */
export function formatConfidence(
  value: number | null | undefined
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}
