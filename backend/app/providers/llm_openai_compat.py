"""OpenAI 호환 Chat Completions LLM provider.

base_url 만 바꾸면 여러 무료/유료 제공자에 그대로 동작한다:
- Groq      : https://api.groq.com/openai/v1        (무료, 카드 불필요, 30 RPM / 1000 RPD)
- OpenRouter: https://openrouter.ai/api/v1          (무료 모델 슬롯)
- Cerebras  : https://api.cerebras.ai/v1            (무료, 빠름)
- OpenAI    : https://api.openai.com/v1             (유료)

JSON 출력은 response_format={"type":"json_object"} 로 강제하고 Pydantic 으로 검증한다.
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


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in LLM output")
    return json.loads(m.group(0))


class OpenAICompatLLMProvider:
    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 60.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _complete(
        self, system: str, user: str, max_tokens: int = 2048,
        json_out: bool = True, temperature: float = 0.2,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_out:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        r = None
        for attempt in range(3):
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(url, headers=headers, json=payload)
            if r.status_code in (429, 503) and attempt < 2:
                time.sleep(2.0 * (attempt + 1))  # 일시적 rate limit 백오프
                continue
            break
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def generate_search_queries(self, ticker: str, name: str) -> List[str]:
        return [f"{name} 목표주가 리포트", f"{ticker} 기업분석"]

    def evaluate_evidence_clarity(self, report: CandidateReport) -> float:
        return 0.7 if report.target_price is not None else 0.4

    def extract_target_price(self, text: str) -> Optional[float]:
        try:
            out = self._complete(EXTRACT_SYSTEM, text[:6000], 256, temperature=0.0)
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
                out = self._complete(SYNTHESIS_SYSTEM, user, 3000)
                return LLMSynthesisOutput.model_validate(_extract_json(out))
            except Exception:
                if attempt == 1:
                    return LLMSynthesisOutput()
        return LLMSynthesisOutput()

    def parse_user_view(self, ticker: str, text: str, horizon_months: int) -> ParsedView:
        user = f"투자기간: {horizon_months}개월\n사용자 입력: {text}"
        try:
            out = self._complete(PARSE_VIEW_SYSTEM, user, 256)
            data = _extract_json(out)
            return ParsedView(
                mode=ViewMode(data.get("mode", "accept_report")),
                expected_return=data.get("expected_return"),
                confidence=float(data.get("confidence", 0.5)),
                rationale=str(data.get("rationale", text)),
            )
        except Exception:
            return ParsedView(mode=ViewMode.ACCEPT_REPORT, confidence=0.5, rationale=text)
