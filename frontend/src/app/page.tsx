"use client";

import React, { useEffect, useState } from "react";
import {
  analyzeReports,
  getHealth,
  optimizePortfolio,
} from "@/lib/api";
import type {
  HealthResponse,
  PortfolioResult,
  PortfolioView,
  ReportAnalysis,
  StockSearchResult,
} from "@/lib/types";
import { Stepper } from "@/components/Stepper";
import { Step0Select } from "@/components/Step0Select";
import {
  Step1Reports,
  makeDefaultView,
  type ViewState,
} from "@/components/Step1Reports";
import { Step2Result } from "@/components/Step2Result";

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [step, setStep] = useState(0);

  // Step 0
  const [selected, setSelected] = useState<StockSearchResult[]>([]);
  const [horizon, setHorizon] = useState(3);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");

  // Step 1
  const [reports, setReports] = useState<ReportAnalysis[]>([]);
  const [views, setViews] = useState<Record<string, ViewState>>({});
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeError, setOptimizeError] = useState("");

  // Step 2
  const [result, setResult] = useState<PortfolioResult | null>(null);

  // 데이터가 준비된 단계까지만 스텝 이동을 허용
  const maxStep = result ? 2 : reports.length > 0 ? 1 : 0;

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const setView = (ticker: string, patch: Partial<ViewState>) => {
    setViews((prev) => ({
      ...prev,
      [ticker]: { ...prev[ticker], ...patch },
    }));
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalyzeError("");
    try {
      const tickers = selected.map((s) => s.ticker);
      const data = await analyzeReports(tickers, horizon);
      setReports(data);
      const initViews: Record<string, ViewState> = {};
      data.forEach((r) => {
        initViews[r.stock_code] = makeDefaultView(r);
      });
      setViews(initViews);
      setStep(1);
    } catch (e) {
      setAnalyzeError(
        e instanceof Error ? e.message : "분석에 실패했습니다."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const buildViews = (): PortfolioView[] => {
    return reports.map((r) => {
      const v = views[r.stock_code];
      const mode = v.mode;
      let expectedReturn: number | null = null;
      let confidence = v.confidence / 100;
      if (mode === "accept_report") {
        expectedReturn = r.implied_return_portfolio_horizon;
      } else if (mode === "custom_view") {
        const parsed = parseFloat(v.customPercentInput);
        expectedReturn = Number.isFinite(parsed) ? parsed / 100 : null;
      } else {
        // abstain
        expectedReturn = null;
        confidence = 0;
      }
      return {
        ticker: r.stock_code,
        mode,
        expected_return: expectedReturn,
        confidence,
        rationale: v.rationale,
      };
    });
  };

  const handleOptimize = async () => {
    setOptimizing(true);
    setOptimizeError("");
    try {
      const tickers = reports.map((r) => r.stock_code);
      const portfolioViews = buildViews();
      const data = await optimizePortfolio(tickers, horizon, portfolioViews);
      setResult(data);
      setStep(2);
    } catch (e) {
      setOptimizeError(
        e instanceof Error ? e.message : "포트폴리오 계산에 실패했습니다."
      );
    } finally {
      setOptimizing(false);
    }
  };

  const handleRestart = () => {
    setStep(0);
    setSelected([]);
    setHorizon(3);
    setReports([]);
    setViews({});
    setResult(null);
    setAnalyzeError("");
    setOptimizeError("");
  };

  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRestart}
              title="처음 화면으로 (초기화)"
              className="rounded-lg text-left text-base font-bold text-slate-900 transition-colors hover:text-brand-600 sm:text-lg"
            >
              리서치 기반 개인화 포트폴리오
            </button>
            {health?.demo_mode && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-700">
                DEMO
              </span>
            )}
          </div>
          <span className="hidden text-xs text-slate-400 sm:inline">
            Black–Litterman
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="mb-8">
          <Stepper current={step} maxStep={maxStep} onStepClick={setStep} />
        </div>

        {step === 0 && (
          <Step0Select
            selected={selected}
            setSelected={setSelected}
            horizon={horizon}
            setHorizon={setHorizon}
            onAnalyze={handleAnalyze}
            analyzing={analyzing}
            analyzeError={analyzeError}
          />
        )}

        {step === 1 && (
          <Step1Reports
            reports={reports}
            views={views}
            setView={setView}
            horizon={horizon}
            onBack={() => setStep(0)}
            onOptimize={handleOptimize}
            optimizing={optimizing}
            optimizeError={optimizeError}
          />
        )}

        {step === 2 && result && (
          <Step2Result result={result} onRestart={handleRestart} />
        )}
      </div>

      <footer className="mx-auto max-w-5xl px-4 pb-10 pt-2 text-center text-xs text-slate-400 sm:px-6">
        본 서비스는 투자 참고용 데모이며, 투자 결정의 책임은 이용자에게 있습니다.
      </footer>
    </main>
  );
}
