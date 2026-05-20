"""
디너의여왕 scraper.
ct=지역&order=dday (신청마감순) URL을 사용해 page를 깊이 내려가며 수집.
비로그인 상태에서도 D'day → D-1 → D-2 ... 순으로 나오므로,
max_deadline_days 초과 페이지가 나오면 조기 종료.

카드 구조 (div.qz-dq-card):
  <a class="qz-dq-card__link" href="/taste/ID" title="[서울 성동][클립] 제목 신청하기">
  <div class="qz-dq-card__text">
    <strong>D-8</strong>          ← 마감
    <p class="apply_badge">신청 3 / 모집 7</p>
    <p class="qz-body2-kr--line ellipsis color-title">제목</p>
"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urlencode

from models import Campaign
from .base import curl_get, infer_category, parse_location, parse_deadline, parse_applicants

BASE_URL = "https://dinnerqueen.net"


def scrape(cities: Optional[List[str]] = None, max_deadline_days: int = 3,
           email: str = "", password: str = "") -> List[Campaign]:
    if cities is None:
        cities = ["서울"]

    campaigns: List[Campaign] = []
    seen: set = set()

    for city in cities:
        for page in range(1, 200):
            params = {
                "ct": "지역",
                "order": "dday",
                "area1": city,
                "area2": "전체",
                "sns[]": "all",
                "page": page,
            }
            url = f"{BASE_URL}/taste?" + urlencode(params, encoding="utf-8")
            try:
                html = curl_get(url)
                if not html:
                    break
            except Exception as e:
                print(f"[디너의여왕] {city} 페이지 {page} 오류: {e}")
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("div", class_="qz-dq-card")
            if not cards:
                break

            page_deadlines = []
            new_count = 0
            for card in cards:
                a = card.find("a", class_="qz-dq-card__link")
                if not a:
                    continue
                href = a.get("href", "")
                if href in seen:
                    continue
                seen.add(href)
                c = _parse_card(card, a, href)
                if c:
                    campaigns.append(c)
                    page_deadlines.append(c.deadline_days)
                    new_count += 1

            if new_count == 0:
                break
            # 이 페이지의 모든 캠페인이 max_deadline_days 초과면 더 내려가도 의미 없음
            if page_deadlines and min(page_deadlines) > max_deadline_days:
                break

    return campaigns


DQ_CHANNEL_WORDS = {"클립", "릴스", "블로그", "쇼츠", "인스타", "유튜브", "배달"}


def _parse_card(card, a_tag, href: str) -> Optional[Campaign]:
    # 제목: <a title="..."> 에서 " 신청하기" 제거
    raw_title = a_tag.get("title", "")
    title = re.sub(r"\s*신청하기\s*$", "", raw_title).strip()

    if not title:
        # fallback: title 텍스트 요소
        p = card.find("p", class_=re.compile("color-title"))
        title = p.get_text(strip=True) if p else ""

    if not title:
        return None

    # 채널 타입: "[클립]", "[릴스]" 등 bracket에서 추출
    channel = ""
    for b in re.findall(r"\[([^\]]+)\]", raw_title):
        if b in DQ_CHANNEL_WORDS:
            channel = b
            break

    # 마감: <strong>D-8</strong>
    text = card.get_text(" ", strip=True)
    deadline_days = parse_deadline(text)

    # 신청 현황: <p class="apply_badge">
    apply_p = card.find("p", class_="apply_badge")
    if apply_p:
        apply_text = apply_p.get_text(" ", strip=True)
    else:
        apply_text = text
    applicants, spots = parse_applicants(apply_text)
    if applicants == 0 and spots == 0:
        return None

    # 위치
    loc_match = re.search(r"\[([^\]]+)\]", title)
    location_raw = loc_match.group(1) if loc_match else ""
    city, district = parse_location(location_raw)

    # 배송 여부
    campaign_type = "배송" if "배송" in text else "방문"

    # 썸네일
    img = card.find("img")
    thumb = img.get("src") if img else None

    return Campaign(
        title=title,
        url=BASE_URL + href if not href.startswith("http") else href,
        platform="디너의여왕",
        location_raw=location_raw,
        city=city,
        district=district,
        deadline_days=deadline_days,
        applicants=applicants,
        spots=spots,
        campaign_type=campaign_type,
        category=infer_category(title, text),
        thumbnail_url=thumb,
        channel=channel,
    )
