"""Google Gemini 기반 LLM provider (무료 티어 사용 가능).

google-generativeai SDK 대신 REST(generativeLanguage) 를 httpx 로 직접 호출한다(의존성 최소).
- responseMimeType=application/json 으로 구조화 출력을 강제하고 Pydantic 으로 검증한다.
- 키: GEMINI_API_KEY (https://aistudio.google.com 에서 무료 발급)
"""
from __future__ import annotations

import json
import re
import time
from typing import List, Optional

import httpx

from ..prompts import (
    EXTRACT_SYSTEM,
    PARSE_VIEW_SYSTEM,
    SYNTHESIS_SYSTEM,
    build_synthesis_user_prompt,
)
from ..schemas.portfolio import ParsedView, ViewMode
from ..schemas.reports import CandidateReport, LLMSynthesisOutput

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in Gemini output")
    return json.loads(m.group(0))


class GeminiLLMProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _complete(
        self, system: str, user: str, max_tokens: int = 2500,
        json_out: bool = True, temperature: float = 0.2,
    ) -> str:
        url = f"{_BASE}/{self.model}:generateContent"
        gen_cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if json_out:
            gen_cfg["responseMimeType"] = "application/json"
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        # 일시적 rate limit(429)/서버오류(503)는 짧은 백오프로 재시도.
        # 무료 티어 한도 소진이면 재시도로도 안 풀리므로 상위에서 휴리스틱으로 대체된다.
        r = None
        for attempt in range(3):
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(url, params={"key": self.api_key}, json=body)
            if r.status_code in (429, 503) and attempt < 2:
                time.sleep(2.0 * (attempt + 1))
                continue
            break
        r.raise_for_status()
        data = r.json()
        cands = data.get("candidates", [])
        if not cands:
            raise ValueError("Gemini returned no candidates")
        parts = cands[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    def generate_search_queries(self, ticker: str, name: str) -> List[str]:
        # 네이버 리서치는 종목코드로 직접 검색하므로 실제로는 미사용. 안전한 기본값 반환.
        return [f"{name} 목표주가 리포트", f"{ticker} 기업분석"]

    def evaluate_evidence_clarity(self, report: CandidateReport) -> float:
        return 0.7 if report.target_price is not None else 0.4

    def extract_target_price(self, text: str) -> Optional[float]:
        try:
            # 2.5 계열은 thinking 토큰을 소비하므로 출력 예산을 넉넉히 둔다. 추출은 결정론적으로(temp 0).
            out = self._complete(EXTRACT_SYSTEM, text[:6000], 2048, temperature=0.0)
            tp = _extract_json(out).get("target_price")
            return float(tp) if tp is not None else None
        except Exception:
            return None

    def synthesize(
        self, ticker: str, name: str, reports: List[CandidateReport]
    ) -> LLMSynthesisOutput:
        user = build_synthesis_user_prompt(name, ticker, reports)
        for attempt in range(2):
            try:
                # thinking 토큰 + 구조화 JSON 출력 공간 확보 (2.5 계열은 thinking 소비)
                out = self._complete(SYNTHESIS_SYSTEM, user, 8192)
                return LLMSynthesisOutput.model_validate(_extract_json(out))
            except Exception:
                if attempt == 1:
                    return LLMSynthesisOutput()
        return LLMSynthesisOutput()

    def parse_user_view(self, ticker: str, text: str, horizon_months: int) -> ParsedView:
        user = f"투자기간: {horizon_months}개월\n사용자 입력: {text}"
        try:
            out = self._complete(PARSE_VIEW_SYSTEM, user, 2048)
            data = _extract_json(out)
            return ParsedView(
                mode=ViewMode(data.get("mode", "accept_report")),
                expected_return=data.get("expected_return"),
                confidence=float(data.get("confidence", 0.5)),
                rationale=str(data.get("rationale", text)),
            )
        except Exception:
            return ParsedView(mode=ViewMode.ACCEPT_REPORT, confidence=0.5, rationale=text)
