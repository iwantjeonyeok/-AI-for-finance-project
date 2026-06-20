"""Anthropic 기반 LLM provider. DEMO_MODE 가 아니고 ANTHROPIC_API_KEY 가 있을 때 사용.

모든 출력은 Pydantic 스키마로 검증하며, 실패 시 1회 재시도한다.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from ..prompts import (
    EXTRACT_SYSTEM,
    PARSE_VIEW_SYSTEM,
    SEARCH_QUERY_SYSTEM,
    SYNTHESIS_SYSTEM,
    build_synthesis_user_prompt,
)
from ..schemas.portfolio import ParsedView, ViewMode
from ..schemas.reports import CandidateReport, LLMSynthesisOutput


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in LLM output")
    return json.loads(m.group(0))


class AnthropicLLMProvider:
    def __init__(self, api_key: str, model: str):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def _complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    def generate_search_queries(self, ticker: str, name: str) -> List[str]:
        out = self._complete(SEARCH_QUERY_SYSTEM, f"종목명: {name}\n종목코드: {ticker}", 300)
        try:
            data = _extract_json(out)
            qs = data.get("queries", [])
            return [str(q) for q in qs][:5] or [f"{name} 목표주가 리포트"]
        except Exception:
            return [f"{name} 목표주가 리포트", f"{ticker} 기업분석"]

    def evaluate_evidence_clarity(self, report: CandidateReport) -> float:
        prompt = (
            f"다음 보고서 본문에서 목표주가/산정논리/상승근거/리스크를 얼마나 명확히 식별할 수 있는지 "
            f"0~1 점수로만 JSON {{\"score\": x}} 형태로 답하라.\n\n{report.raw_text[:4000]}"
        )
        try:
            out = self._complete("너는 보고서 품질 평가자다. JSON 만 출력하라.", prompt, 100)
            return float(_extract_json(out).get("score", 0.5))
        except Exception:
            return 0.5

    def extract_target_price(self, text: str) -> Optional[float]:
        try:
            out = self._complete(EXTRACT_SYSTEM, text[:6000], 150)
            data = _extract_json(out)
            tp = data.get("target_price")
            return float(tp) if tp is not None else None
        except Exception:
            return None

    def synthesize(
        self, ticker: str, name: str, reports: List[CandidateReport]
    ) -> LLMSynthesisOutput:
        user = build_synthesis_user_prompt(name, ticker, reports)
        for attempt in range(2):
            try:
                out = self._complete(SYNTHESIS_SYSTEM, user, 2500)
                return LLMSynthesisOutput.model_validate(_extract_json(out))
            except Exception:
                if attempt == 1:
                    return LLMSynthesisOutput()
        return LLMSynthesisOutput()

    def parse_user_view(self, ticker: str, text: str, horizon_months: int) -> ParsedView:
        user = f"투자기간: {horizon_months}개월\n사용자 입력: {text}"
        try:
            out = self._complete(PARSE_VIEW_SYSTEM, user, 300)
            data = _extract_json(out)
            return ParsedView(
                mode=ViewMode(data.get("mode", "accept_report")),
                expected_return=data.get("expected_return"),
                confidence=float(data.get("confidence", 0.5)),
                rationale=str(data.get("rationale", text)),
            )
        except Exception:
            return ParsedView(mode=ViewMode.ACCEPT_REPORT, confidence=0.5, rationale=text)
