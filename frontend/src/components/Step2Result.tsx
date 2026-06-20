"use client";

import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  formatConfidence,
  formatPercent,
  formatSignedPercent,
  formatWon,
} from "@/lib/format";
import type { PortfolioItem, PortfolioResult } from "@/lib/types";
import { Button, Card } from "./ui";

interface Props {
  result: PortfolioResult;
  onRestart: () => void;
}

const modeLabel: Record<string, string> = {
  accept_report: "보고서 전망",
  custom_view: "직접 입력",
  abstain: "판단 보류",
};

export function Step2Result({ result, onRestart }: Props) {
  const items = result.items;

  const weightData = items.map((it) => ({
    name: it.name,
    "최종 비중": +(it.final_weight * 100).toFixed(2),
  }));

  const compareData = items.map((it) => ({
    name: it.name,
    "시장 prior": +(it.market_prior_weight * 100).toFixed(2),
    "최종 비중": +(it.final_weight * 100).toFixed(2),
  }));

  const confidenceData = items.map((it) => ({
    name: it.name,
    confidence:
      it.user_confidence !== null
        ? +(it.user_confidence * 100).toFixed(0)
        : 0,
  }));

  const posteriorData = items.map((it) => ({
    name: it.name,
    posterior: +(it.posterior_expected_return * 100).toFixed(2),
  }));

  return (
    <div className="space-y-6">
      {result.used_fallback && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="font-bold">주의: </span>
          최적화 대신 대체 방식이 사용되었습니다.
          {result.fallback_reason ? ` (${result.fallback_reason})` : ""}
        </div>
      )}

      {/* Results table */}
      <Card className="overflow-hidden">
        <h2 className="mb-3 text-lg font-bold text-slate-900">
          포트폴리오 결과
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="px-3 py-2 font-semibold">종목명</th>
                <th className="px-3 py-2 text-right font-semibold">
                  시장 prior 비중
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  보고서 평균 목표주가
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  보고서 기대수익률
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  최종 사용 view
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  사용자 confidence
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  BL posterior 기대수익률
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  최종 비중
                </th>
                <th className="px-3 py-2 text-right font-semibold">
                  prior 대비 변화
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr
                  key={it.ticker}
                  className="border-b border-slate-100 last:border-0"
                >
                  <td className="px-3 py-2.5">
                    <div className="font-semibold text-slate-900">
                      {it.name}
                    </div>
                    <div className="text-xs text-slate-400">{it.ticker}</div>
                    {!it.has_report && (
                      <div className="text-xs text-amber-600">
                        보고서 없음 — 시장 prior 기반
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {formatPercent(it.market_prior_weight)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {it.has_report ? formatWon(it.mean_target_price) : "-"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {it.has_report
                      ? formatSignedPercent(it.report_expected_return)
                      : "-"}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <div>{formatSignedPercent(it.used_view)}</div>
                    <div className="text-xs text-slate-400">
                      {modeLabel[it.user_view_mode] ?? it.user_view_mode}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {formatConfidence(it.user_confidence)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {formatSignedPercent(it.posterior_expected_return)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-bold text-slate-900">
                    {formatPercent(it.final_weight)}
                  </td>
                  <td
                    className={[
                      "px-3 py-2.5 text-right font-semibold",
                      it.weight_change > 0
                        ? "text-red-600"
                        : it.weight_change < 0
                        ? "text-blue-600"
                        : "text-slate-500",
                    ].join(" ")}
                  >
                    {formatSignedPercent(it.weight_change)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartCard title="최종 비중">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={weightData} margin={{ left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11 }}
                interval={0}
                angle={-15}
                textAnchor="end"
                height={50}
              />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar dataKey="최종 비중" fill="#3b6fe0" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="시장 prior 비중 vs 최종 비중">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={compareData} margin={{ left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11 }}
                interval={0}
                angle={-15}
                textAnchor="end"
                height={50}
              />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="시장 prior" fill="#9bb4ea" radius={[4, 4, 0, 0]} />
              <Bar dataKey="최종 비중" fill="#2f59c4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="종목별 사용자 신뢰도(confidence)">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={confidenceData} margin={{ left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11 }}
                interval={0}
                angle={-15}
                textAnchor="end"
                height={50}
              />
              <YAxis tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar
                dataKey="confidence"
                name="신뢰도"
                fill="#7c8db5"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="종목별 BL posterior 기대수익률">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={posteriorData} margin={{ left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11 }}
                interval={0}
                angle={-15}
                textAnchor="end"
                height={50}
              />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar
                dataKey="posterior"
                name="기대수익률"
                radius={[4, 4, 0, 0]}
              >
                {posteriorData.map((d, i) => (
                  <Cell
                    key={i}
                    fill={d.posterior >= 0 ? "#e2575c" : "#3b6fe0"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Explanations */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">
          종목별 설명
        </h3>
        <ul className="space-y-3">
          {items.map((it) => (
            <li key={it.ticker} className="text-sm">
              <span className="font-semibold text-slate-900">{it.name}</span>
              <p className="mt-0.5 leading-relaxed text-slate-600">
                {it.explanation}
              </p>
            </li>
          ))}
        </ul>
      </Card>

      {/* Disclaimer */}
      <div className="rounded-lg border border-slate-300 bg-slate-100 px-4 py-3 text-xs leading-relaxed text-slate-600">
        {result.disclaimer}
      </div>

      <div className="flex justify-end">
        <Button variant="secondary" onClick={onRestart}>
          처음부터 다시
        </Button>
      </div>
    </div>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <h3 className="mb-3 text-sm font-bold text-slate-900">{title}</h3>
      {children}
    </Card>
  );
}
