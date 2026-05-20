from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Campaign:
    title: str
    url: str
    platform: str          # 'reviewnote' | 'dinnerqueen' | 'gangnam'
    location_raw: str      # "[서울 강남]"
    city: str              # "서울"
    district: str          # "강남"  (구 제외)
    deadline_days: int
    applicants: int
    spots: int
    campaign_type: str     # "방문" | "배송"
    category: str          # "식당" | "카페" | "뷰티" | "기타"
    benefit: str = ""      # 혜택 내용 (예: "5만원 식사권", "15만원 체험권 2인")
    thumbnail_url: Optional[str] = None
    distance_km: Optional[float] = None
    channel: str = ""          # 채널 종류 (블로그, 릴스, 쇼츠, 클립 등)
    review_days: Optional[int] = None  # 리뷰 등록 마감까지 남은 일수

    @property
    def benefit_amount(self) -> int:
        """혜택 텍스트에서 원화 금액 추출. 예: '15만원 체험권' → 150000"""
        t = self.benefit
        # "N만원" / "N만 원"
        m = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원", t)
        if m:
            return int(float(m.group(1)) * 10_000)
        # "N,000원" 또는 "N000원"
        m = re.search(r"(\d[\d,]+)\s*원", t)
        if m:
            return int(m.group(1).replace(",", ""))
        # 포인트: "N만P" / "N만 포인트" / "N,000P"
        m = re.search(r"(\d+(?:\.\d+)?)\s*만\s*[Pp포]", t)
        if m:
            return int(float(m.group(1)) * 10_000)
        m = re.search(r"(\d[\d,]+)\s*[Pp]", t)
        if m:
            return int(m.group(1).replace(",", ""))
        return 0

    @property
    def ratio(self) -> float:
        if self.spots == 0:
            return float("inf")
        return self.applicants / self.spots

    @property
    def is_high_prob(self) -> bool:
        return self.deadline_days <= 2 and self.ratio < 2.0

    @property
    def prob_label(self) -> str:
        r = self.ratio
        if r < 1:
            return "당첨유력"
        elif r < 2:
            return "경쟁낮음"
        elif r < 5:
            return "보통"
        else:
            return "경쟁치열"

    def format_line(self) -> str:
        dist = f" · {self.distance_km:.1f}km" if self.distance_km is not None else ""
        benefit_line = f"\n  💰 {self.benefit}" if self.benefit else ""
        return (
            f"[{self.platform}] {self.prob_label} D-{self.deadline_days} "
            f"{self.applicants}/{self.spots}명 "
            f"{self.district}{dist}"
            f"{benefit_line}\n"
            f"  {self.title}\n"
            f"  {self.url}"
        )
