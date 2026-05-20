"""
체험단 당첨확률 높은 곳 긁어서 카카오톡으로 전송.

실행:
  python3 main.py              # 카카오톡 전송
  python3 main.py --dry-run    # 터미널 출력만 (전송 안 함)
  python3 main.py --all        # 필터 없이 전체 목록 보기
"""
import sys
import warnings
warnings.filterwarnings("ignore")

import yaml
from pathlib import Path

from scrapers import scrape_reviewnote, scrape_dinnerqueen, scrape_gangnam
import filters
from distance import enrich_distance
from notifier import send
from kakao_auth import ensure_valid_token

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    show_all = "--all" in sys.argv

    config = load_config()
    loc = config.get("my_location", {})
    my_lat = loc.get("lat", 37.5563)
    my_lng = loc.get("lng", 126.9723)

    filt = config.get("filter", {})
    cities = config.get("preferred_cities", [])
    districts = config.get("preferred_districts", [])
    home_districts = config.get("home_districts", [])
    categories = config.get("categories", [])
    max_deadline = filt.get("max_deadline_days", 2)
    max_ratio = filt.get("max_ratio", 3.0)
    include_delivery = filt.get("include_delivery", False)
    max_results = filt.get("max_results", None)
    weights = config.get("scoring_weights", {"probability": 0.5, "benefit": 0.25, "distance": 0.15, "home_bonus": 0.10})

    print("🔍 체험단 수집 중...")

    all_campaigns = []
    try:
        rn = scrape_reviewnote(max_deadline_days=max_deadline + 1)
        print(f"  리뷰노트: {len(rn)}개")
        all_campaigns += rn
    except Exception as e:
        print(f"  리뷰노트 오류: {e}")

    try:
        dq = scrape_dinnerqueen(cities=["서울", "경기"])
        print(f"  디너의여왕: {len(dq)}개")
        all_campaigns += dq
    except Exception as e:
        print(f"  디너의여왕 오류: {e}")

    try:
        gn = scrape_gangnam()
        print(f"  강남맛집: {len(gn)}개")
        all_campaigns += gn
    except Exception as e:
        print(f"  강남맛집 오류: {e}")

    print(f"\n📦 총 {len(all_campaigns)}개 수집")

    # 거리 계산
    enrich_distance(all_campaigns, my_lat, my_lng)

    if show_all:
        for c in all_campaigns:
            print(c.format_line())
            print()
        return

    # 필터 적용
    picked = filters.apply(
        all_campaigns,
        districts=districts,
        campaign_types=["방문"],
        categories=categories,
        max_deadline_days=max_deadline,
        max_ratio=max_ratio,
        include_delivery=include_delivery,
        cities=cities,
        weights=weights,
        max_results=max_results,
        home_districts=home_districts,
    )

    print(f"🎯 추천 체험단: {len(picked)}개\n")

    if not picked:
        print("조건에 맞는 체험단이 없어요.")
        if not dry_run:
            kakao = config.get("kakao", {})
            token = ensure_valid_token(config)
            send([], token)
        return

    for c in picked:
        print(c.format_line())
        print()

    if dry_run:
        print("(dry-run: 카카오톡 전송 안 함)")
        return

    kakao = config.get("kakao", {})
    if not kakao.get("rest_api_key"):
        print("\n⚠️  카카오 API 키 없음. config.yaml 설정 후 python kakao_auth.py 실행하세요.")
        return

    try:
        token = ensure_valid_token(config)
        send(picked, token)
    except Exception as e:
        print(f"카카오톡 전송 오류: {e}")


if __name__ == "__main__":
    main()
