export interface HealthResponse {
  status: string;
  demo_mode: boolean;
  horizon_months: number;
  tau: number;
  risk_aversion: number;
  max_asset_weight: number;
}

export interface StockSearchResult {
  ticker: string;
  name: string;
  market: string;
  current_price: number;
  market_cap: number;
}

export interface RationaleItem {
  text: string;
  supporting_source_ids: string[];
}

export interface ReportSource {
  source_id: string;
  institution: string;
  title: string;
  published_at: string;
  url: string;
  /** DEMO 샘플이면 외부 URL 대신 백엔드 파생 요약 페이지로 연결 */
  demo_sample?: boolean;
}

export type ReportStatus = "available" | "no_report";

export interface ReportAnalysis {
  stock_code: string;
  stock_name: string;
  current_price: number;
  mean_target_price: number | null;
  target_price_count: number;
  selected_report_count: number;
  institutions: string[];
  implied_return_raw: number | null;
  implied_return_portfolio_horizon: number | null;
  core_rationales: RationaleItem[];
  major_risks: RationaleItem[];
  consensus_summary: string;
  disagreement_summary: string;
  sources: ReportSource[];
  status: ReportStatus;
  horizon_months: number;
}

export type ViewMode = "accept_report" | "custom_view" | "abstain";

export interface UserViewParseResult {
  mode: ViewMode;
  expected_return: number | null;
  confidence: number;
  rationale: string;
}

export interface PortfolioView {
  ticker: string;
  mode: ViewMode;
  expected_return: number | null;
  confidence: number;
  rationale: string;
}

export interface PortfolioItem {
  ticker: string;
  name: string;
  market_prior_weight: number;
  mean_target_price: number | null;
  report_expected_return: number | null;
  used_view: number | null;
  user_view_mode: ViewMode | string;
  user_confidence: number | null;
  posterior_expected_return: number;
  final_weight: number;
  weight_change: number;
  has_report: boolean;
  explanation: string;
}

export interface PortfolioResult {
  portfolio_id: string;
  horizon_months: number;
  tau: number;
  risk_aversion: number;
  max_asset_weight: number;
  items: PortfolioItem[];
  used_fallback: boolean;
  fallback_reason: string | null;
  disclaimer: string;
}
