import type {
  HealthResponse,
  PortfolioResult,
  PortfolioView,
  ReportAnalysis,
  StockSearchResult,
  UserViewParseResult,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/** 보고서 파생 요약 페이지 URL (DEMO 샘플 링크 대상) */
export function sourceViewUrl(sourceId: string): string {
  return `${API_BASE}/api/reports/source/${encodeURIComponent(sourceId)}/view`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
  } catch (e) {
    throw new Error(
      "서버에 연결할 수 없습니다. 백엔드(http://localhost:8000)가 실행 중인지 확인해 주세요."
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = typeof data?.detail === "string" ? data.detail : "";
    } catch {
      /* ignore */
    }
    throw new Error(
      detail || `요청에 실패했습니다 (HTTP ${res.status}).`
    );
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function searchStocks(q: string): Promise<StockSearchResult[]> {
  return request<StockSearchResult[]>(
    `/api/stocks/search?q=${encodeURIComponent(q)}`
  );
}

export function analyzeReports(
  tickers: string[],
  horizonMonths: number
): Promise<ReportAnalysis[]> {
  return request<ReportAnalysis[]>("/api/reports/analyze", {
    method: "POST",
    body: JSON.stringify({ tickers, horizon_months: horizonMonths }),
  });
}

export function parseUserView(
  ticker: string,
  text: string,
  horizonMonths: number
): Promise<UserViewParseResult> {
  return request<UserViewParseResult>("/api/user-views/parse", {
    method: "POST",
    body: JSON.stringify({ ticker, text, horizon_months: horizonMonths }),
  });
}

export function optimizePortfolio(
  tickers: string[],
  horizonMonths: number,
  views: PortfolioView[]
): Promise<PortfolioResult> {
  return request<PortfolioResult>("/api/portfolio/optimize", {
    method: "POST",
    body: JSON.stringify({
      tickers,
      horizon_months: horizonMonths,
      views,
    }),
  });
}

export function getPortfolio(id: string): Promise<PortfolioResult> {
  return request<PortfolioResult>(`/api/portfolio/${encodeURIComponent(id)}`);
}
