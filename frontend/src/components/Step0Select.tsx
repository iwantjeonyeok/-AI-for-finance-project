"use client";

import React, { useEffect, useRef, useState } from "react";
import { searchStocks } from "@/lib/api";
import { formatMarketCap, formatWon } from "@/lib/format";
import type { StockSearchResult } from "@/lib/types";
import { Button, Card, ErrorBanner, Spinner } from "./ui";

const HORIZON_OPTIONS = [1, 3, 6];

interface Props {
  selected: StockSearchResult[];
  setSelected: (s: StockSearchResult[]) => void;
  horizon: number;
  setHorizon: (h: number) => void;
  onAnalyze: () => void;
  analyzing: boolean;
  analyzeError: string;
}

export function Step0Select({
  selected,
  setSelected,
  horizon,
  setHorizon,
  onAnalyze,
  analyzing,
  analyzeError,
}: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (!q) {
      setResults([]);
      setSearchError("");
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchStocks(q);
        setResults(data);
        setSearchError("");
      } catch (e) {
        setResults([]);
        setSearchError(e instanceof Error ? e.message : "검색에 실패했습니다.");
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const isSelected = (ticker: string) =>
    selected.some((s) => s.ticker === ticker);

  const addStock = (stock: StockSearchResult) => {
    if (isSelected(stock.ticker)) return;
    setSelected([...selected, stock]);
  };

  const removeStock = (ticker: string) => {
    setSelected(selected.filter((s) => s.ticker !== ticker));
  };

  const countOk = selected.length >= 3 && selected.length <= 15;

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="mb-1 text-lg font-bold text-slate-900">종목 선택</h2>
        <p className="mb-4 text-sm text-slate-500">
          포트폴리오에 포함할 종목을 검색해 추가하세요. (권장 3~15개)
        </p>

        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="종목명 또는 종목코드 검색 (예: 삼성)"
            className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
          {searching && (
            <span className="absolute right-3 top-3 text-brand-600">
              <Spinner />
            </span>
          )}
        </div>

        {searchError && (
          <div className="mt-3">
            <ErrorBanner message={searchError} />
          </div>
        )}

        {results.length > 0 && (
          <ul className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
            {results.map((stock) => {
              const added = isSelected(stock.ticker);
              return (
                <li
                  key={stock.ticker}
                  className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        {stock.name}
                      </span>
                      <span className="text-xs text-slate-400">
                        {stock.ticker} · {stock.market}
                      </span>
                    </div>
                    <div className="text-sm text-slate-500">
                      {formatWon(stock.current_price)} ·{" "}
                      {formatMarketCap(stock.market_cap)}
                    </div>
                  </div>
                  <Button
                    variant={added ? "secondary" : "primary"}
                    disabled={added}
                    onClick={() => addStock(stock)}
                  >
                    {added ? "추가됨" : "추가"}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">
            선택한 종목{" "}
            <span className="text-brand-600">({selected.length})</span>
          </h3>
          {!countOk && selected.length > 0 && (
            <span className="text-xs text-amber-600">
              3~15개를 권장합니다.
            </span>
          )}
        </div>

        {selected.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">
            아직 선택한 종목이 없습니다.
          </p>
        ) : (
          <ul className="space-y-2">
            {selected.map((stock) => (
              <li
                key={stock.ticker}
                className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">
                      {stock.name}
                    </span>
                    <span className="text-xs text-slate-400">
                      {stock.ticker}
                    </span>
                  </div>
                  <div className="text-sm text-slate-500">
                    현재가 {formatWon(stock.current_price)} · 시총{" "}
                    {formatMarketCap(stock.market_cap)}
                  </div>
                </div>
                <button
                  onClick={() => removeStock(stock.ticker)}
                  className="rounded-md px-2 py-1 text-sm text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                  aria-label={`${stock.name} 제거`}
                >
                  제거
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">투자 기간</h3>
        <div className="flex gap-2">
          {HORIZON_OPTIONS.map((m) => (
            <button
              key={m}
              onClick={() => setHorizon(m)}
              className={[
                "rounded-lg border px-4 py-2 text-sm font-semibold transition-colors",
                horizon === m
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50",
              ].join(" ")}
            >
              {m}개월
            </button>
          ))}
        </div>
      </Card>

      {analyzeError && <ErrorBanner message={analyzeError} />}

      <div className="flex justify-end">
        <Button
          onClick={onAnalyze}
          loading={analyzing}
          disabled={selected.length === 0}
        >
          분석 시작
        </Button>
      </div>
    </div>
  );
}
