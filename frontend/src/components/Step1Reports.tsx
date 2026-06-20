"use client";

import React, { useState } from "react";
import { parseUserView, sourceViewUrl } from "@/lib/api";
import {
  formatSignedPercent,
  formatWon,
} from "@/lib/format";
import type {
  ReportAnalysis,
  ReportSource,
  ViewMode,
} from "@/lib/types";
import { Button, Card, ErrorBanner, Spinner } from "./ui";

export interface ViewState {
  mode: ViewMode;
  /** percent value as the user types it, e.g. "4" meaning +4% */
  customPercentInput: string;
  confidence: number; // 0..100
  rationale: string;
  nlText: string;
}

export function makeDefaultView(report: ReportAnalysis): ViewState {
  const hasReport = report.status === "available";
  return {
    mode: hasReport ? "accept_report" : "custom_view",
    customPercentInput: "",
    confidence: 60,
    rationale: "",
    nlText: "",
  };
}

interface Props {
  reports: ReportAnalysis[];
  views: Record<string, ViewState>;
  setView: (ticker: string, patch: Partial<ViewState>) => void;
  horizon: number;
  onBack: () => void;
  onOptimize: () => void;
  optimizing: boolean;
  optimizeError: string;
}

export function Step1Reports({
  reports,
  views,
  setView,
  horizon,
  onBack,
  onOptimize,
  optimizing,
  optimizeError,
}: Props) {
  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">
        각 종목의 리서치 종합을 확인하고, 종목별로 「내 판단」을 선택하세요.
        신뢰도가 낮을수록 결과는 시장 시가총액 비중에 가까워집니다.
      </p>

      {reports.map((report) => (
        <ReportCard
          key={report.stock_code}
          report={report}
          view={views[report.stock_code]}
          setView={(patch) => setView(report.stock_code, patch)}
          horizon={horizon}
        />
      ))}

      {optimizeError && <ErrorBanner message={optimizeError} />}

      <div className="flex flex-col-reverse justify-between gap-2 sm:flex-row">
        <Button variant="secondary" onClick={onBack} disabled={optimizing}>
          이전
        </Button>
        <Button onClick={onOptimize} loading={optimizing}>
          포트폴리오 계산
        </Button>
      </div>
    </div>
  );
}

function ReportCard({
  report,
  view,
  setView,
  horizon,
}: {
  report: ReportAnalysis;
  view: ViewState;
  setView: (patch: Partial<ViewState>) => void;
  horizon: number;
}) {
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState("");
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const hasReport = report.status === "available";

  const handleParse = async () => {
    const text = view.nlText.trim();
    if (!text) return;
    setParsing(true);
    setParseError("");
    try {
      const res = await parseUserView(report.stock_code, text, horizon);
      const patch: Partial<ViewState> = {
        mode: res.mode,
        confidence: Math.round((res.confidence ?? 0) * 100),
        rationale: res.rationale ?? "",
      };
      if (res.expected_return !== null && res.expected_return !== undefined) {
        patch.customPercentInput = (res.expected_return * 100).toString();
      }
      // accept_report has no report -> downgrade to custom_view
      if (!hasReport && res.mode === "accept_report") {
        patch.mode = "custom_view";
      }
      setView(patch);
    } catch (e) {
      setParseError(
        e instanceof Error ? e.message : "자연어 해석에 실패했습니다."
      );
    } finally {
      setParsing(false);
    }
  };

  const lowConfidence = view.mode !== "abstain" && view.confidence <= 50;

  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold text-slate-900">
          {report.stock_name}
          <span className="ml-2 text-xs font-normal text-slate-400">
            {report.stock_code}
          </span>
        </h3>
        {!hasReport && (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
            리서치 보고서 없음
          </span>
        )}
      </div>

      {hasReport ? (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-1 gap-2 rounded-lg bg-slate-50 p-3 sm:grid-cols-3">
            <Metric label="현재가" value={formatWon(report.current_price)} />
            <Metric
              label="보고서 평균 목표주가"
              value={formatWon(report.mean_target_price)}
            />
            <Metric
              label={`${report.horizon_months}개월 환산 기대수익률`}
              value={formatSignedPercent(
                report.implied_return_portfolio_horizon
              )}
              highlight={
                (report.implied_return_portfolio_horizon ?? 0) >= 0
                  ? "pos"
                  : "neg"
              }
            />
          </div>

          {report.core_rationales.length > 0 && (
            <Section title="상승 근거">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {report.core_rationales.map((r, i) => (
                  <li key={i}>{r.text}</li>
                ))}
              </ul>
            </Section>
          )}

          {report.major_risks.length > 0 && (
            <Section title="하락 근거 / 리스크">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {report.major_risks.map((r, i) => (
                  <li key={i}>{r.text}</li>
                ))}
              </ul>
            </Section>
          )}

          {(report.consensus_summary || report.disagreement_summary) && (
            <Section title="기관 간 종합">
              <div className="space-y-1 text-sm text-slate-700">
                {report.consensus_summary && (
                  <p>
                    <span className="font-semibold text-slate-500">
                      공통 견해:{" "}
                    </span>
                    {report.consensus_summary}
                  </p>
                )}
                {report.disagreement_summary && (
                  <p>
                    <span className="font-semibold text-slate-500">
                      이견:{" "}
                    </span>
                    {report.disagreement_summary}
                  </p>
                )}
              </div>
            </Section>
          )}

          {report.sources.length > 0 && (
            <div className="rounded-lg border border-slate-200">
              <button
                onClick={() => setSourcesOpen((v) => !v)}
                className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <span>사용된 보고서 ({report.sources.length})</span>
                <span className="text-slate-400">
                  {sourcesOpen ? "▲" : "▼"}
                </span>
              </button>
              {sourcesOpen && (
                <ul className="divide-y divide-slate-100 border-t border-slate-100">
                  {report.sources.map((s) => (
                    <SourceRow key={s.source_id} source={s} />
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          리서치 보고서 없음 — 시장 prior만 사용합니다. 목표주가 정보가
          없으므로 「보고서 전망 사용」은 선택할 수 없습니다.
        </div>
      )}

      {/* 내 판단 */}
      <div className="mt-5 rounded-lg border border-slate-200 bg-white p-4">
        <h4 className="mb-3 text-sm font-bold text-slate-900">내 판단</h4>

        <div className="space-y-2">
          <RadioRow
            name={`mode-${report.stock_code}`}
            checked={view.mode === "accept_report"}
            disabled={!hasReport}
            onChange={() => setView({ mode: "accept_report" })}
            label="보고서 전망 사용"
          />
          <RadioRow
            name={`mode-${report.stock_code}`}
            checked={view.mode === "custom_view"}
            onChange={() => setView({ mode: "custom_view" })}
            label="나의 기대수익률 입력"
          />
          {view.mode === "custom_view" && (
            <div className="ml-6 flex items-center gap-2">
              <input
                type="number"
                step="0.1"
                value={view.customPercentInput}
                onChange={(e) =>
                  setView({ customPercentInput: e.target.value })
                }
                placeholder="예: 4"
                className="w-28 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
              <span className="text-sm text-slate-500">
                % ({report.horizon_months}개월 기대수익률)
              </span>
            </div>
          )}
          <RadioRow
            name={`mode-${report.stock_code}`}
            checked={view.mode === "abstain"}
            onChange={() => setView({ mode: "abstain" })}
            label="판단 보류 (시장 prior 사용)"
          />
        </div>

        {view.mode !== "abstain" && (
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between text-sm">
              <label className="font-semibold text-slate-700">신뢰도</label>
              <span className="font-bold text-brand-600">
                {view.confidence}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={view.confidence}
              onChange={(e) =>
                setView({ confidence: Number(e.target.value) })
              }
              className="w-full accent-brand-600"
            />
            {lowConfidence && (
              <p className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
                {view.confidence}%는 목표수익률을 {view.confidence}%로 줄이는
                것이 아니라, 해당 전망에 대한 신뢰도를 의미합니다. 신뢰도가
                낮을수록 최종 결과는 시장 시가총액 기준 비중에 가까워집니다.
              </p>
            )}
          </div>
        )}

        {/* 자연어 입력 */}
        <div className="mt-4 border-t border-slate-100 pt-4">
          <label className="mb-1 block text-sm font-semibold text-slate-700">
            자연어로 판단 입력 (선택)
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={view.nlText}
              onChange={(e) => setView({ nlText: e.target.value })}
              placeholder="예: 반도체 업황 회복으로 10% 정도 오를 것 같고 확신은 보통"
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            <Button
              variant="secondary"
              onClick={handleParse}
              loading={parsing}
              disabled={!view.nlText.trim()}
            >
              해석
            </Button>
          </div>
          {parseError && (
            <p className="mt-2 text-xs text-red-600">{parseError}</p>
          )}
          {view.rationale && (
            <p className="mt-2 text-xs text-slate-500">
              해석된 근거: {view.rationale}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

function Metric({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: "pos" | "neg";
}) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div
        className={[
          "text-base font-bold",
          highlight === "pos"
            ? "text-red-600"
            : highlight === "neg"
            ? "text-blue-600"
            : "text-slate-900",
        ].join(" ")}
      >
        {value}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 text-sm font-bold text-slate-800">{title}</div>
      {children}
    </div>
  );
}

function RadioRow({
  name,
  checked,
  disabled,
  onChange,
  label,
}: {
  name: string;
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <label
      className={[
        "flex cursor-pointer items-center gap-2 text-sm",
        disabled ? "cursor-not-allowed text-slate-300" : "text-slate-700",
      ].join(" ")}
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        disabled={disabled}
        onChange={onChange}
        className="h-4 w-4 accent-brand-600"
      />
      {label}
    </label>
  );
}

function SourceRow({ source }: { source: ReportSource }) {
  // DEMO 샘플은 죽은 외부 URL 대신 백엔드 파생 요약 페이지로 연결한다.
  const href = source.demo_sample
    ? sourceViewUrl(source.source_id)
    : source.url;
  return (
    <li className="px-4 py-2.5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-700">
          {source.institution}
        </span>
        <span className="text-xs text-slate-400">{source.published_at}</span>
        {source.demo_sample && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
            DEMO 샘플
          </span>
        )}
      </div>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-brand-600 hover:underline"
      >
        {source.title}
      </a>
    </li>
  );
}
