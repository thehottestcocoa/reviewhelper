from __future__ import annotations
from typing import List, Optional
from models import Campaign


def apply(
    campaigns: List[Campaign],
    districts: List[str],
    campaign_types: List[str],
    categories: List[str],
    max_deadline_days: int = 2,
    max_ratio: float = 3.0,
    include_delivery: bool = False,
    cities: Optional[List[str]] = None,
    weights: Optional[dict] = None,
    max_results: Optional[int] = None,
    home_districts: Optional[List[str]] = None,  # 선호 구 보너스
) -> List[Campaign]:
    result = []
    for c in campaigns:
        if c.campaign_type == "배송" and not include_delivery:
            continue
        if cities and c.city not in cities:
            continue
        if districts and not _district_match(c.district, districts):
            continue
        if categories and c.category not in categories:
            continue
        if c.deadline_days > max_deadline_days:
            continue
        if c.ratio >= max_ratio:
            continue
        result.append(c)

    w = weights or {"probability": 0.5, "benefit": 0.25, "distance": 0.15, "home_bonus": 0.10}
    hd = home_districts or []
    result.sort(key=lambda c: _score(c, w, hd), reverse=True)

    if max_results:
        result = result[:max_results]

    return result


def _score(c: Campaign, w: dict, home_districts: List[str]) -> float:
    """
    네 요소를 0~1 정규화 후 가중합산.
    - 당첨확률:  1 / (1 + ratio)
    - 지원금액:  min(amount / 100_000, 1)  ← 10만원 기준
    - 거리:      max(0, 1 - km / 20)       ← 20km 기준, 정보없으면 0.5
    - 홈보너스:  선호 구(도봉/강북/성북) 이면 1, 아니면 0
    """
    prob = 1.0 / (1.0 + c.ratio)
    amt  = min(c.benefit_amount / 100_000, 1.0) if c.benefit_amount else 0.0
    dist = max(0.0, 1.0 - c.distance_km / 20.0) if c.distance_km is not None else 0.5
    home = 1.0 if any(_districts_equal(c.district, h) for h in home_districts) else 0.0

    return (
        w.get("probability", 0.5)  * prob
        + w.get("benefit",   0.25) * amt
        + w.get("distance",  0.15) * dist
        + w.get("home_bonus",0.10) * home
    )


def _district_match(district: str, wanted: List[str]) -> bool:
    for w in wanted:
        if _districts_equal(district, w.strip()):
            return True
    return False


def _districts_equal(d: str, w: str) -> bool:
    if d == w:
        return True
    # "강남구" → normalize to "강남" and compare
    w_stripped = w.rstrip("구시군")
    if len(w_stripped) >= 2 and d == w_stripped:
        return True
    # "중" should match "중구" but NOT "중랑" (only if suffix char follows)
    if d.startswith(w) and len(w) < len(d) and d[len(w):] in ("구", "시", "군"):
        return True
    return False
