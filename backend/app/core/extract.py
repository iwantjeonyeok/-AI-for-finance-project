"""리서치 PDF 본문에서 목표주가를 추출(국내 보고서 표준 표기 기준).

LLM 없이도 동작하는 1차 추출기. 신뢰성 위해 현재가 대비 합리적 범위만 채택하고,
의심스러우면 None 을 반환한다(LLM 보정 또는 평균 제외로 넘어감).
"""
from __future__ import annotations

import re
from typing import List, Optional

# "목표주가 480,000원", "목표주가(원) 480,000", "목표주가: 88,000", "TP 480,000"
_LABEL = r"(?:목표\s*주가|목표가|적정\s*주가|적정가|Target\s*Price|TP)"
_NUM = r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})"
_PATTERNS = [
    re.compile(_LABEL + r"[^0-9\-]{0,15}" + _NUM, re.IGNORECASE),
]


def _to_int(s: str) -> Optional[int]:
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return None


def extract_target_price_candidates(text: str) -> List[int]:
    out: List[int] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            v = _to_int(m.group(1))
            if v is not None and v > 0:
                out.append(v)
    return out


# ---------------------------------------------------------------------------
# 상승/하락 근거 문장 추출 (LLM 키가 없을 때의 사실 기반 요약)
# ---------------------------------------------------------------------------
_BULL_KW = [
    "성장", "개선", "확대", "상향", "증가", "회복", "수요", "모멘텀", "수혜", "호조",
    "견조", "최대", "신규", "수주", "흑자", "반등", "상승", "경쟁력", "점유율", "마진",
    "수익성", "기대", "긍정", "강세", "개화", "확장", "출하",
]
_BEAR_KW = [
    "둔화", "하락", "감소", "부진", "리스크", "우려", "약세", "불확실", "경쟁", "부담",
    "규제", "차질", "지연", "하향", "적자", "악화", "변동성", "위험", "제약", "관세",
    "축소", "위축", "조정", "공급과잉", "재고",
]
_HANGUL = re.compile(r"[가-힣]")
# 문장 경계: 한국어 보고서는 대개 '다.' 로 끝남. '.' 뒤 공백+한글/대문자/괄호도 경계로.
_SENT_SPLIT = re.compile(r"(?<=다\.)\s+|(?<=다\))\s+|(?<=\.)\s+(?=[가-힣A-Z(])")


def _clean_sentence(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ·•-—\t")


def _join_pdf_linebreaks(text: str) -> str:
    """PDF 추출 시 문장/단어 중간에 들어간 줄바꿈을 복원한다."""
    if not text:
        return ""
    # 한글-한글 사이 줄바꿈은 단어가 쪼개진 것 → 그대로 붙임
    text = re.sub(r"(?<=[가-힣])\n(?=[가-힣])", "", text)
    # 그 외 줄바꿈은 공백으로
    text = re.sub(r"\s*\n\s*", " ", text)
    return text


def _is_prose(s: str) -> bool:
    """표/숫자 나열이 아닌 서술형 문장인지 판정."""
    if not (18 <= len(s) <= 180):
        return False
    hangul = len(_HANGUL.findall(s))
    if hangul < 10:
        return False
    # 한글 비중이 너무 낮으면(표/수치 행) 제외
    if hangul / len(s) < 0.4:
        return False
    # 온전한 서술형 종결('다.'/'다'/'음'/'함' 등)로 끝나는 문장만
    return bool(re.search(r"(다|음|함|됨|점|망|상|소|화)\.?$", s))


def split_sentences(text: str) -> List[str]:
    joined = _join_pdf_linebreaks(text)
    out = []
    for raw in _SENT_SPLIT.split(joined):
        s = _clean_sentence(raw)
        if _is_prose(s):
            out.append(s)
    return out


def classify_thesis_sentences(sources):
    """[(source_id, text)] -> (bull, bear). 각 항목 = (sentence, source_id).

    키워드 빈도로 상승/하락 분류. 본문 등장 순서를 보존하고 근접 중복을 제거한다.
    """
    bull, bear = [], []
    seen = set()
    for source_id, text in sources:
        for s in split_sentences(text):
            key = s[:16]
            if key in seen:
                continue
            b = sum(s.count(k) for k in _BULL_KW)
            r = sum(s.count(k) for k in _BEAR_KW)
            if b == 0 and r == 0:
                continue
            seen.add(key)
            if r > b:
                bear.append((s, source_id))
            else:
                bull.append((s, source_id))
    return bull, bear


_UPSIDE_RE = re.compile(
    r"(?:상승\s*여력|상승\s*여지|Upside)[^\d\-+]{0,8}([+-]?\d{1,3}(?:\.\d+)?)\s*%?",
    re.IGNORECASE,
)


def extract_upside_return(
    text: str, *, min_pct: float = -90.0, max_pct: float = 500.0
) -> Optional[float]:
    """보고서 본문의 '상승여력 XX%' 를 수익률(decimal)로 추출. 목표가 숫자가 이미지라 못 뽑을 때 사용.

    예) '상승여력 98.8' -> 0.988. 비정상 범위는 None.
    """
    for m in _UPSIDE_RE.finditer(text or ""):
        try:
            pct = float(m.group(1))
        except ValueError:
            continue
        if min_pct <= pct <= max_pct:
            return pct / 100.0
    return None


def extract_target_price(
    text: str,
    current_price: Optional[float] = None,
    *,
    min_won: int = 100,
    max_won: int = 100_000_000,
) -> Optional[float]:
    """가장 그럴듯한 목표주가 1개를 반환. 없으면 None.

    - '목표주가' 라벨 근처 숫자를 후보로 모은다.
    - current_price 가 주어지면 현재가의 0.3~5배 범위 후보를 우선 채택.
    - 라벨 표기는 보고서 앞부분(표지/요약)에 처음 등장하는 값이 대표값인 경우가 많아
      후보 중 빈도가 가장 높은 값을 선택한다.
    """
    cands = [c for c in extract_target_price_candidates(text) if min_won <= c <= max_won]
    if not cands:
        return None

    if current_price and current_price > 0:
        plausible = [c for c in cands if 0.3 * current_price <= c <= 5.0 * current_price]
        # 현재가를 알고 있는데 합리적 범위 후보가 하나도 없으면 추측하지 않고 포기.
        if not plausible:
            return None
        cands = plausible

    # 최빈값(동률이면 먼저 등장한 값) 선택
    freq: dict[int, int] = {}
    first_idx: dict[int, int] = {}
    for i, c in enumerate(cands):
        freq[c] = freq.get(c, 0) + 1
        first_idx.setdefault(c, i)
    best = sorted(freq.keys(), key=lambda v: (-freq[v], first_idx[v]))[0]
    return float(best)
