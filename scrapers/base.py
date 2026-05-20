import re
import ssl
import urllib3
import requests
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SSL_VERIFY = False


import subprocess


def curl_get(url: str, timeout: int = 15, cookies: str = "") -> str:
    """macOS LibreSSL 우회용 curl subprocess fetch."""
    cmd = [
        "curl", "-s", "-L",
        "-A", HEADERS["User-Agent"],
        "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
        "--max-time", str(timeout),
    ]
    if cookies:
        cmd += ["-H", f"Cookie: {cookies}"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "운동/관리": [
        "헬스", "필라테스", "요가", "pt", "크로스핏", "수영", "골프", "클라이밍", "복싱",
        "주짓수", "무에타이", "스피닝", "줌바", "서핑", "테니스", "배드민턴",
        "휘트니스", "피트니스", "트레이닝", "pt샵", "pt스튜디오",
        "스포츠센터", "점핑", "바디핏", "런닝", "사이클",
    ],
    "미용/뷰티": [
        "미용", "네일", "왁싱", "피부", "헤어", "뷰티", "에스테틱", "눈썹", "속눈썹",
        "필러", "보톡스", "마사지", "관리", "클리닉", "라운지", "시술", "트리트먼트",
        "케어", "컷트", "펌", "염색", "각질", "제모", "클렌징", "페이셜", "반영구",
        "리프팅", "슬리밍", "다이어트", "비만", "탈모", "족욕", "스파",
    ],
    "카페/디저트": [
        "카페", "커피", "디저트", "베이커리", "케이크", "마카롱", "아이스크림",
        "빙수", "브런치", "음료", "샌드위치", "도넛", "와플", "라떼", "아메리카노",
        "에스프레소", "쿠키", "크로플", "타르트", "크루아상",
    ],
    "식당/술집": [
        # 식당
        "식당", "레스토랑", "음식점", "한식", "양식", "중식", "일식", "고깃집", "한우",
        "삼겹살", "치킨", "피자", "버거", "분식", "국밥", "곱창", "횟집", "초밥", "회",
        "냉면", "보쌈", "갈비", "스테이크", "파스타", "리조또", "돈까스", "제육", "닭갈비",
        "찜닭", "라멘", "식사권", "자유이용권", "고기", "정식", "런치", "디너",
        "오마카세", "인분", "상차림", "쌀국수", "월남쌈", "훠궈", "샤브샤브", "우동",
        "덮밥", "김밥", "떡볶이", "순대", "족발", "수육", "차돌", "매운", "수산",
        "해물", "해산물", "조개", "굴", "새우", "랍스터", "막창",
        "찜", "구이", "전골", "부대찌개", "비빔밥", "냉모밀", "소바",
        "규동", "규카츠", "맛집", "음식",
        # 술집
        "술집", "주점", "이자카야", "맥주", "와인", "칵테일", "위스키", "야끼도리", "포차",
        "호프", "혼술", "주류", "펍", "pub", "하이볼", "수제맥주", "막걸리", "소주",
        "사케", "와인바", "루프탑바",
    ],
    "기타": ["보드게임", "사진관", "공방", "클래스", "학원", "찜질", "전시", "방탈출", "노래"],
}


def infer_category(title: str, benefit: str = "") -> str:
    """Case-insensitive keyword search across title+benefit. First match wins."""
    text = " " + (title + " " + benefit).lower() + " "
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return cat
    return "기타"


def parse_location(raw: str) -> tuple[str, str]:
    """Return (city, district) from raw bracket text like '서울 강남' or '경기/수원시'."""
    raw = raw.strip()
    if not raw or raw in ("재택", "배송"):
        return "재택", "재택"

    # reviewnote: '경기/수원시', '서울/강남구'
    if "/" in raw:
        parts = raw.split("/", 1)
        city = parts[0].strip()
        district = _strip_suffix(parts[1].strip())
        return city, district

    # dinnerqueen / gangnam: '서울 강남', '경기 성남'
    parts = raw.split(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), _strip_suffix(parts[1].strip())
    return raw, raw


def _strip_suffix(s: str) -> str:
    """Remove 구/시/군 suffix only when result stays >= 2 chars."""
    stripped = s.rstrip("구시군")
    return stripped if len(stripped) >= 2 else s


def parse_deadline(text: str) -> int:
    """Parse days remaining from various text formats."""
    m = re.search(r"(\d+)\s*일\s*남음", text)
    if m:
        return int(m.group(1))
    if re.search(r"D'?\s*[-·]?\s*[Dd]ay", text) or re.search(r"D-0\b", text, re.IGNORECASE):
        return 0
    m = re.search(r"D-\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if "하루" in text or "오늘" in text or "마감임박" in text:
        return 1
    if "이틀" in text:
        return 2
    return 999


def parse_applicants(text: str) -> tuple[int, int]:
    """Return (applicants, spots) from text like '신청 23 / 모집 5' or '신청 23 / 5'."""
    m = re.search(r"신청\s*([\d,]+)\s*/\s*(?:모집\s*)?([\d,]+)", text)
    if m:
        return (
            int(m.group(1).replace(",", "")),
            int(m.group(2).replace(",", "")),
        )
    return 0, 0
