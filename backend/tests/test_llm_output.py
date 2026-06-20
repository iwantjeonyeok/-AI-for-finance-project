"""LLM 출력 검증 테스트 (명세 14장). DEMO mock + 스키마 검증 기준."""
import json

import pytest
from pydantic import ValidationError

from app.providers.mock import MockLLMProvider
from app.schemas.reports import CandidateReport, LLMSynthesisOutput
from app.services.analysis_service import analyze_stock, clear_cache


def _cand(sid, inst, text, tp=90000):
    return CandidateReport(
        source_id=sid, stock_code="005930", institution=inst, title=text[:10],
        url=f"https://x/{sid}", target_price=tp, raw_text=text,
    )


def test_1_invalid_json_recovered_by_schema():
    # 스키마 상한(상승 6 / 하락 5) 초과 시 ValidationError 발생해야 함(엄격 검증)
    data = {
        "core_rationales": [{"text": f"r{i}", "supporting_source_ids": []} for i in range(8)],
        "major_risks": [{"text": f"k{i}", "supporting_source_ids": []} for i in range(7)],
        "consensus_summary": "c",
        "disagreement_summary": "d",
    }
    with pytest.raises(ValidationError):
        LLMSynthesisOutput.model_validate(data)


def test_2_no_fabricated_numbers():
    clear_cache()
    a = analyze_stock("005930", 3)
    # mean_target_price 는 fixture 의 목표가 평균과 일치해야 하며 임의 생성 금지
    assert a.mean_target_price is not None
    # 선정 보고서 목표가들의 평균 범위 내
    assert 80000 <= a.mean_target_price <= 100000


def test_3_rationales_within_cap():
    llm = MockLLMProvider()
    cands = [_cand("a", "미래에셋증권", "HBM 메모리 파운드리 AI 수주 공장 주주환원 하이브리드 광고 커머스")]
    out = llm.synthesize("005930", "삼성전자", cands)
    assert len(out.core_rationales) <= 6


def test_4_risks_within_cap():
    llm = MockLLMProvider()
    cands = [_cand("a", "미래에셋증권", "중국 환율 경쟁 관세 규제 재고 capex 둔화")]
    out = llm.synthesize("005930", "삼성전자", cands)
    assert len(out.major_risks) <= 5


def test_5_source_ids_point_to_real_docs():
    clear_cache()
    a = analyze_stock("005930", 3)
    valid_ids = {s.source_id for s in a.sources}
    for r in a.core_rationales:
        for sid in r.supporting_source_ids:
            assert sid in valid_ids
    for r in a.major_risks:
        for sid in r.supporting_source_ids:
            assert sid in valid_ids
