"""보고서 선정 테스트 (명세 14장)."""
from datetime import date

from app.core.report_scorer import (
    recency_score,
    reputation_for,
    score_candidates,
    select_reports,
)
from app.core.returns import is_valid_target_price, mean_valid_target_price
from app.schemas.reports import CandidateReport

TODAY = date(2026, 6, 20)


def _cand(sid, inst, url, pub, text, tp=90000, ev=0.8, accessible=True):
    return CandidateReport(
        source_id=sid,
        stock_code="005930",
        institution=inst,
        title=text[:20],
        url=url,
        published_at=pub,
        accessible=accessible,
        target_price=tp,
        evidence_clarity_score=ev,
        raw_text=text,
    )


def test_1_recent_report_higher_recency():
    recent = recency_score(date(2026, 6, 15), TODAY, 45)
    old = recency_score(date(2026, 1, 1), TODAY, 45)
    assert recent > old


def test_2_reputation_config_reflected():
    rep_mirae, enabled, known = reputation_for("미래에셋증권", "https://securities.miraeasset.com/x")
    rep_unknown, _, known2 = reputation_for("듣보증권", "https://unknown.example.com/x")
    assert rep_mirae > rep_unknown
    assert known is True
    assert known2 is False


def test_3_similar_reports_same_cluster():
    text = "HBM 출하 확대와 메모리 가격 반등으로 실적이 개선된다. 파운드리 회복이 핵심 근거다."
    cands = [
        _cand("a", "미래에셋증권", "https://securities.miraeasset.com/1", date(2026, 6, 10), text),
        _cand("b", "NH투자증권", "https://nhqv.com/1", date(2026, 6, 9), text + " "),
    ]
    score_candidates(cands, TODAY)
    assert cands[0].duplicate_cluster == cands[1].duplicate_cluster


def test_4_distinct_institutions_preferred():
    text_base = "메모리 업황 회복 근거 {}. HBM 파운드리 수요 다양 관점 {}."
    cands = [
        _cand("a", "미래에셋증권", "https://securities.miraeasset.com/1", date(2026, 6, 10), text_base.format("A", 1)),
        _cand("b", "미래에셋증권", "https://securities.miraeasset.com/2", date(2026, 6, 9), text_base.format("B", 2)),
        _cand("c", "NH투자증권", "https://nhqv.com/1", date(2026, 6, 8), text_base.format("C", 3)),
        _cand("d", "삼성증권", "https://samsungpop.com/1", date(2026, 6, 7), text_base.format("D", 4)),
    ]
    score_candidates(cands, TODAY)
    selected = select_reports(cands)
    insts = {c.institution for c in selected}
    # 서로 다른 기관 3곳이 모두 포함되어야 한다
    assert {"미래에셋증권", "NH투자증권", "삼성증권"}.issubset(insts)


def test_5_inaccessible_not_selected():
    cands = [
        _cand("a", "미래에셋증권", "https://securities.miraeasset.com/1", date(2026, 6, 10), "근거 A 다양", accessible=True),
        _cand("paid", "한국투자증권", "https://truefriend.com/premium", date(2026, 6, 12), "유료", accessible=False),
    ]
    score_candidates(cands, TODAY)
    selected = select_reports(cands)
    assert all(c.accessible for c in selected)
    assert "한국투자증권" not in {c.institution for c in selected}


def test_6_missing_target_price_excluded_from_mean():
    assert is_valid_target_price(None, 70000) is False
    mean = mean_valid_target_price([90000, None, 92000], 70000)
    assert mean == (90000 + 92000) / 2


def test_unknown_domestic_excluded():
    cands = [
        _cand("a", "미래에셋증권", "https://securities.miraeasset.com/1", date(2026, 6, 10), "근거 A 다양"),
        _cand("x", "외국계리서치", "https://foreign.example.com/1", date(2026, 6, 11), "근거 X 다양"),
    ]
    score_candidates(cands, TODAY)
    selected = select_reports(cands)
    insts = {c.institution for c in selected}
    assert "외국계리서치" not in insts  # require_known_domestic=true
