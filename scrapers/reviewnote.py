"""
리뷰노트 scraper.
/api/v2/campaigns?city=서울&s=endingSoon 직접 호출 (JSON API).
마감임박순 정렬이라 deadline_days > max_deadline_days 첫 페이지에서 조기 종료.

API 응답 주요 필드:
  id, title, sort(VISIT/DELIVERY/PAYBACK), infNum(모집), applicantCount(신청),
  offer(혜택), applyEndAt(마감일시), reviewEndAt(리뷰등록기간),
  sido.name(구), city(서울), category.title, channel(BLOG/REELS/SHORTS/BLOG_CLIP)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from urllib.parse import quote

import requests

from models import Campaign
from .base import HEADERS, infer_category

BASE_URL = "https://www.reviewnote.co.kr"
API_URL = f"{BASE_URL}/api/v2/campaigns"
FIREBASE_BASE = "https://firebasestorage.googleapis.com/v0/b/reviewnote-e92d9.appspot.com/o"
CHANNEL_MAP = {
    "BLOG": "블로그", "REELS": "릴스", "SHORTS": "쇼츠", "BLOG_CLIP": "블로그클립",
}
CATEGORY_MAP = {
    "맛집": "식당/술집",
    "식품": "식당/술집",
    "뷰티": "미용/뷰티",
    "여행": "기타",
    "디지털": "기타",
}
API_HEADERS = {
    **HEADERS,
    "Referer": f"{BASE_URL}/campaigns",
    "Origin": BASE_URL,
}


def _thumb_url(image_key: str | None) -> str | None:
    if not image_key:
        return None
    if image_key.startswith("http"):
        return image_key
    return f"{FIREBASE_BASE}/{quote(image_key, safe='')}?alt=media"


def scrape(max_pages: int = 10, max_deadline_days: int = 7) -> List[Campaign]:
    campaigns: List[Campaign] = []

    for page in range(max_pages):
        try:
            resp = requests.get(
                API_URL,
                params={"page": page, "s": "endingSoon", "city": "서울"},
                headers=API_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[리뷰노트] 페이지 {page} 오류: {e}")
            break

        objects = resp.json().get("objects", [])
        if not objects:
            break

        all_over = True
        for obj in objects:
            deadline_days = _calc_deadline(obj.get("applyEndAt", ""))
            if deadline_days <= max_deadline_days:
                all_over = False
            c = _parse_obj(obj, deadline_days)
            if c:
                campaigns.append(c)

        # 마감임박순이라 이 페이지 전체가 마감 초과면 뒷 페이지도 불필요
        if all_over:
            break

    return campaigns


def _calc_deadline(apply_end_at: str) -> int:
    if not apply_end_at:
        return 999
    try:
        end = datetime.fromisoformat(apply_end_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, (end.date() - now.date()).days)
    except Exception:
        return 999


def _parse_obj(obj: dict, deadline_days: int) -> Campaign | None:
    title = obj.get("title", "").strip()
    if not title:
        return None

    spots = obj.get("infNum") or 0
    applicants = obj.get("applicantCount") or 0
    if spots == 0 and applicants == 0:
        return None

    sido = obj.get("sido") or {}
    district_raw = sido.get("name", "")
    district = district_raw.replace("구", "").replace("시", "") if len(district_raw) > 2 else district_raw

    campaign_type = "배송" if obj.get("sort") == "DELIVERY" else "방문"
    category_obj = obj.get("category") or {}
    api_cat = (category_obj.get("title") or "").strip()
    mapped = CATEGORY_MAP.get(api_cat)
    if mapped is not None:
        category = mapped
    else:
        category = infer_category(title, obj.get("offer", "")) or "기타"

    channel = CHANNEL_MAP.get(obj.get("channel", ""), "")

    review_days_raw = _calc_deadline(obj.get("reviewEndAt", ""))
    review_days = review_days_raw if review_days_raw != 999 else None

    return Campaign(
        title=title,
        url=f"{BASE_URL}/campaigns/{obj['id']}",
        platform="리뷰노트",
        location_raw=district_raw,
        city=obj.get("city", "서울"),
        district=district,
        deadline_days=deadline_days,
        applicants=applicants,
        spots=spots,
        campaign_type=campaign_type,
        category=category,
        benefit=obj.get("offer", ""),
        thumbnail_url=_thumb_url(obj.get("imageKey")),
        channel=channel,
        review_days=review_days,
    )
