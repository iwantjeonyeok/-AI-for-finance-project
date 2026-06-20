"""후보 보고서 점수 부여 및 선정(명세 4장).

reputation 은 config 값, recency 는 발행일 감쇠, evidence_clarity 는 LLM 평가(입력으로 받음),
uniqueness 는 본문 간 의미적 중복도(여기서는 TF 유사도 근사)로 계산한다.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..config import load_institutions_config, load_scoring_config
from ..schemas.reports import CandidateReport


# ---------------------------------------------------------------------------
# 기관 평판도
# ---------------------------------------------------------------------------
def _institution_index() -> Tuple[Dict[str, dict], Dict[str, dict], dict]:
    cfg = load_institutions_config()
    by_name: Dict[str, dict] = {}
    by_domain: Dict[str, dict] = {}
    for inst in cfg.get("institutions", []):
        by_name[inst["name"]] = inst
        for d in inst.get("domains", []):
            by_domain[d.lower()] = inst
    return by_name, by_domain, cfg


def resolve_institution(name: Optional[str], url: str) -> Tuple[Optional[dict], bool]:
    """(institution_config, is_known_domestic) 반환. config 미존재 시 None."""
    by_name, by_domain, _ = _institution_index()
    if name and name in by_name:
        return by_name[name], True
    host = (urlparse(url).hostname or "").lower()
    for domain, inst in by_domain.items():
        if host.endswith(domain):
            return inst, True
    return None, False


def reputation_for(name: Optional[str], url: str) -> Tuple[float, bool, bool]:
    """(reputation_score, enabled, is_known_domestic)."""
    _, _, cfg = _institution_index()
    inst, known = resolve_institution(name, url)
    if inst is not None:
        return float(inst.get("reputation_score", cfg["default_reputation"])), bool(
            inst.get("enabled", True)
        ), True
    return float(cfg.get("default_reputation", 0.5)), True, False


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------
def recency_score(published_at: Optional[date], today: date, half_life_days: float) -> float:
    if published_at is None:
        return 0.3  # 발행일 불명: 낮은 기본값
    days = max((today - published_at).days, 0)
    return float(0.5 ** (days / half_life_days))


# ---------------------------------------------------------------------------
# Uniqueness (본문 의미적 중복도 근사: bag-of-words 코사인)
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def _vector(text: str) -> Counter:
    return Counter(_TOKEN_RE.findall(text.lower()))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def compute_similarity_matrix(texts: List[str]) -> List[List[float]]:
    vecs = [_vector(t) for t in texts]
    n = len(vecs)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            s = _cosine(vecs[i], vecs[j])
            sim[i][j] = sim[j][i] = s
    return sim


def assign_duplicate_clusters(sim: List[List[float]], threshold: float) -> List[int]:
    """유사도 threshold 이상이면 같은 군집. union-find."""
    n = len(sim)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= threshold:
                union(i, j)
    # 군집 id 정규화
    roots = {}
    clusters = []
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        clusters.append(roots[r])
    return clusters


def uniqueness_score_from_sim(sim_row: List[float], self_index: int) -> float:
    """다른 보고서들과의 최대 유사도가 낮을수록 uniqueness 높음."""
    others = [s for i, s in enumerate(sim_row) if i != self_index]
    if not others:
        return 1.0
    return float(1.0 - max(others))


# ---------------------------------------------------------------------------
# 종합 점수 + 선정
# ---------------------------------------------------------------------------
def score_candidates(candidates: List[CandidateReport], today: date) -> List[CandidateReport]:
    """후보 리스트에 모든 점수를 채운다. evidence_clarity_score 는 사전 설정 가정."""
    scoring = load_scoring_config()
    w = scoring["weights"]
    half_life = scoring.get("recency_half_life_days", 45)
    dup_threshold = scoring["selection"]["duplicate_similarity_threshold"]

    # 본문 유사도 행렬
    texts = [c.raw_text or c.title for c in candidates]
    sim = compute_similarity_matrix(texts)
    clusters = assign_duplicate_clusters(sim, dup_threshold)

    for i, c in enumerate(candidates):
        rep, enabled, known = reputation_for(c.institution, c.url)
        c.reputation_score = rep
        c.recency_score = recency_score(c.published_at, today, half_life)
        c.uniqueness_score = uniqueness_score_from_sim(sim[i], i)
        # evidence_clarity_score: 목표가 유무 + 본문 충실도로 근사.
        # 이미지/스캔 PDF(본문 거의 없음)는 낮게 평가해 선정에서 밀어낸다.
        if c.evidence_clarity_score <= 0.0:
            text_len = len(c.raw_text or "")
            ev = 0.2
            if c.target_price is not None:
                ev += 0.4
            ev += min(text_len / 5000.0, 0.4)  # 본문 5000자 이상이면 +0.4 만점
            c.evidence_clarity_score = min(ev, 1.0)
        c.duplicate_cluster = clusters[i]
        c.candidate_score = (
            w["reputation"] * c.reputation_score
            + w["recency"] * c.recency_score
            + w["evidence_clarity"] * c.evidence_clarity_score
            + w["uniqueness"] * c.uniqueness_score
        )
    return candidates


def select_reports(candidates: List[CandidateReport]) -> List[CandidateReport]:
    """선정 규칙 적용. selected 플래그를 세팅하고 선정된 리스트 반환.

    규칙: 접근 가능만 / 비활성·미확인 국내기관 제외 / 중복군집당 대표 1개 /
    기관 다양성 우선 / 종목당 최대 N개.
    """
    scoring = load_scoring_config()
    sel = scoring["selection"]
    max_reports = sel["max_reports_per_stock"]
    prefer_one = sel.get("prefer_one_per_institution", True)

    _, _, inst_cfg = (None, None, load_institutions_config())
    require_domestic = inst_cfg.get("require_known_domestic", True)

    # 1. 접근 불가 / 비활성 기관 / (요구 시) 미확인 국내기관 제외
    eligible = []
    for c in candidates:
        if not c.accessible:
            continue
        rep, enabled, known = reputation_for(c.institution, c.url)
        if not enabled:
            continue
        if require_domestic and not known and not c.domestic_confirmed:
            continue
        eligible.append(c)

    # 2. 점수 내림차순
    eligible.sort(key=lambda c: c.candidate_score, reverse=True)

    # 3. 중복 군집당 대표(최고점) 1개만
    seen_clusters = set()
    deduped = []
    for c in eligible:
        if c.duplicate_cluster in seen_clusters:
            continue
        seen_clusters.add(c.duplicate_cluster)
        deduped.append(c)

    # 4. 기관 다양성: 1차로 기관당 1개씩, 2차로 부족분 채움
    selected: List[CandidateReport] = []
    used_inst = set()
    if prefer_one:
        for c in deduped:
            if len(selected) >= max_reports:
                break
            if c.institution in used_inst:
                continue
            selected.append(c)
            used_inst.add(c.institution)
        for c in deduped:
            if len(selected) >= max_reports:
                break
            if c in selected:
                continue
            selected.append(c)
    else:
        selected = deduped[:max_reports]

    for c in candidates:
        c.selected = c in selected
    return [c for c in candidates if c.selected]
