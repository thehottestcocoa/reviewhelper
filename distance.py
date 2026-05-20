"""
구 단위 대략 거리 계산.
캠페인 상세 주소 없이 구 중심좌표 기준으로 직선거리 계산.
"""
import math

# 서울 25개 구 중심 좌표 (위도, 경도)
DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "강남": (37.5172, 127.0473),
    "강동": (37.5301, 127.1238),
    "강북": (37.6396, 127.0259),
    "강서": (37.5509, 126.8495),
    "관악": (37.4784, 126.9516),
    "광진": (37.5385, 127.0823),
    "구로": (37.4954, 126.8874),
    "금천": (37.4569, 126.8956),
    "노원": (37.6541, 127.0568),
    "도봉": (37.6688, 127.0471),
    "동대문": (37.5744, 127.0396),
    "동작": (37.5124, 126.9393),
    "마포": (37.5663, 126.9014),
    "서대문": (37.5791, 126.9368),
    "서초": (37.4837, 127.0324),
    "성동": (37.5634, 127.0369),
    "성북": (37.5894, 127.0167),
    "송파": (37.5145, 127.1051),
    "양천": (37.5170, 126.8664),
    "영등포": (37.5264, 126.8962),
    "용산": (37.5324, 126.9903),
    "은평": (37.6027, 126.9291),
    "종로": (37.5735, 126.9790),
    "중": (37.5641, 126.9979),
    "중랑": (37.6063, 127.0927),
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def enrich_distance(campaigns, my_lat: float, my_lng: float) -> None:
    """campaigns 리스트의 distance_km 필드를 인플레이스로 채운다."""
    for c in campaigns:
        if c.city != "서울":
            c.distance_km = None
            continue
        district_key = c.district.replace("구", "").replace("시", "")
        # 부분 매칭
        coords = None
        for key, coord in DISTRICT_COORDS.items():
            if key in district_key or district_key in key:
                coords = coord
                break
        if coords:
            c.distance_km = round(haversine_km(my_lat, my_lng, coords[0], coords[1]), 1)
