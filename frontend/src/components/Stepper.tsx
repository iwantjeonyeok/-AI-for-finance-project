"use client";

import React from "react";

const STEPS = ["종목 선택", "리서치 종합 & 내 판단", "결과"];

export function Stepper({
  current,
  maxStep = current,
  onStepClick,
}: {
  current: number;
  /** 이동 가능한 최대 단계(데이터가 준비된 단계까지) */
  maxStep?: number;
  onStepClick?: (idx: number) => void;
}) {
  return (
    <nav aria-label="진행 단계" className="w-full">
      <ol className="flex items-center gap-2 sm:gap-4">
        {STEPS.map((label, idx) => {
          const active = idx === current;
          const done = idx < current;
          const navigable = !!onStepClick && idx <= maxStep && idx !== current;
          return (
            <li key={label} className="flex flex-1 items-center gap-2">
              <button
                type="button"
                disabled={!navigable}
                onClick={() => navigable && onStepClick!(idx)}
                title={navigable ? `${label} 단계로 이동` : undefined}
                className={[
                  "flex items-center gap-2 rounded-lg px-1.5 py-1 transition-colors",
                  navigable ? "cursor-pointer hover:bg-slate-100" : "cursor-default",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                    active
                      ? "bg-brand-600 text-white"
                      : done
                      ? "bg-brand-100 text-brand-700"
                      : "bg-slate-200 text-slate-500",
                  ].join(" ")}
                >
                  {done ? "✓" : idx + 1}
                </span>
                <span
                  className={[
                    "hidden text-sm font-medium sm:inline",
                    active
                      ? "text-slate-900"
                      : done
                      ? "text-brand-700"
                      : "text-slate-400",
                  ].join(" ")}
                >
                  {label}
                </span>
              </button>
              {idx < STEPS.length - 1 && (
                <div
                  className={[
                    "h-px flex-1",
                    done ? "bg-brand-300" : "bg-slate-200",
                  ].join(" ")}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
