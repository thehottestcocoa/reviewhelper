"""
강남맛집 scraper.
sst=cmp_date_select&sod=asc 로 마감임박순 정렬.

카드 구조:
  <dt class="tit"><a href="/cp/?id=ID">제목</a></dt>   ← 제목 링크 (이미지 링크 말고)
  <span class="dday"><em class="day_c">마감임박(하루전)</em></span>
  <span class="numb"><b>신청 N</b> / 모집 N</span>
"""
from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urlencode

from models import Campaign
from .base import HEADERS, infer_category, parse_location, parse_deadline, parse_applicants

BASE_URL = "https://xn--939au0g4vj8sq.net"
AJAX_URL = BASE_URL + "/theme/go/_list_cmp_tpl.php"
AJAX_PARAMS = "ca=20&loca_prt=%EC%84%9C%EC%9A%B8&local_1=%EC%A0%84%EC%B2%B4&local_2=%EC%84%9C%EC%9A%B8&sst=cmp_date_select&sod=asc&row_num=28"
AJAX_HEADERS = {**HEADERS, "Referer": BASE_URL + "/cp/", "X-Requested-With": "XMLHttpRequest"}


def scrape(max_pages: int = 10) -> List[Campaign]:
    campaigns: List[Campaign] = []
    seen: set = set()

    for rpage in range(max_pages):
        try:
            resp = requests.get(
                AJAX_URL + "?" + AJAX_PARAMS + f"&rpage={rpage}",
                headers=AJAX_HEADERS,
                timeout=15,
                verify=False,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[강남맛집] rpage={rpage} 오류: {e}")
            break

        if "조회된 캠페인이 없습니다" in resp.text:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        title_tags = soup.find_all("dt", class_="tit")
        if not title_tags:
            break

        new_count = 0
        for dt in title_tags:
            a = dt.find("a", href=re.compile(r"/cp/\?id=\d+"))
            if not a:
                continue
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            c = _parse_card(a, dt, href)
            if c:
                campaigns.append(c)
                new_count += 1

        if new_count == 0:
            break

    return campaigns


def _parse_card(a_tag, dt_tag, href: str) -> Optional[Campaign]:
    title = a_tag.get_text(strip=True)
    if not title:
        return None

    # dt 기준으로 신청자 수까지 포함하는 컨테이너 찾기
    # 구조: dl(제목+마감) + div.item_detail(신청수) 은 같은 부모 div.textArea 아래
    container = dt_tag.parent  # dl
    for _ in range(4):
        if container is None:
            break
        text = container.get_text(" ", strip=True)
        if re.search(r"신청\s*[\d,]+\s*/\s*모집", text):
            break
        container = container.parent

    if container is None:
        container = dt_tag

    text = container.get_text(" ", strip=True)
    deadline_days = parse_deadline(text)
    applicants, spots = parse_applicants(text)
    if applicants == 0 and spots == 0:
        return None

    loc_match = re.search(r"\[([^\]]+)\]", title)
    location_raw = loc_match.group(1) if loc_match else ""
    city, district = parse_location(location_raw)
    campaign_type = "배송" if "배송형" in text else "방문"

    # 채널 타입: span.label > em.blog / em.sns / em.reels 등
    GANGNAM_CHANNEL = {"blog": "블로그", "sns": "SNS", "reels": "릴스", "clip": "클립", "shorts": "쇼츠"}
    channel = "블로그"  # gangnam is blog-only platform; read em class for future-proofing
    label_span = dt_tag.parent.find("span", class_="label") if dt_tag.parent else None
    if label_span:
        for em in label_span.find_all("em"):
            cls = (em.get("class") or [""])[0]
            if cls in GANGNAM_CHANNEL:
                channel = GANGNAM_CHANNEL[cls]
                break

    # 혜택: <dd class="sub_tit"> (제목 dt 바로 다음 형제)
    sub = dt_tag.find_next_sibling("dd", class_="sub_tit")
    benefit = sub.get_text(strip=True) if sub else ""

    # 이미지는 imgArea 에 있음 (형제 div)
    outer = container.parent or container
    img = outer.find("img", class_="thumb_img") or outer.find("img")
    thumb = None
    if img:
        src = img.get("src", "")
        thumb = ("https:" + src) if src.startswith("//") else src

    return Campaign(
        title=title,
        url=BASE_URL + href if not href.startswith("http") else href,
        platform="강남맛집",
        location_raw=location_raw,
        city=city,
        district=district,
        deadline_days=deadline_days,
        applicants=applicants,
        spots=spots,
        campaign_type=campaign_type,
        category=infer_category(title, benefit),
        benefit=benefit,
        thumbnail_url=thumb,
        channel=channel,
    )
