# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
사용자는 한예은, 디자이너, 비개발자로 개발 지식이 없음.
코드를 짜고 나서는 왜 이렇게 만들었는지 설명한다.
한국어로 대화한다.

## What this project does

체험단(review campaign) 당첨확률 알림 봇. 세 플랫폼에서 캠페인을 수집하고, 마감 임박 + 경쟁률 낮은 것을 필터링해서 웹 UI로 보거나 카카오톡으로 전송한다.

## Running

```bash
# 웹 앱 (Flask dev server)
python3 app.py              # http://localhost:8080

# CLI (카톡 전송)
python3 main.py --dry-run   # 터미널 출력만 (카톡 전송 없음)
python3 main.py             # 카카오톡 전송
python3 main.py --all       # 필터 없이 전체 목록

python3 kakao_auth.py       # 최초 1회: 카카오 OAuth 토큰 발급
```

Dependencies: `python3 -m pip install -r requirements.txt`

Production: `Procfile` → `gunicorn app:app`

## Architecture

**Data flow:** scrapers → `Campaign` objects → `filters.apply()` → `distance.enrich_distance()` → JSON API / `notifier.send()`

**`models.py`** — `Campaign` dataclass. Key computed properties:
- `ratio`: applicants / spots
- `benefit_amount`: int parsed from `benefit` text (e.g. "5만원" → 50000)
- `prob_label`: label based on ratio ("당첨유력"/"경쟁낮음"/"보통"/"경쟁치열")

**`app.py`** — Flask web app. Key routes:
- `POST /api/run` — scrapes all platforms, applies filters, returns `{campaigns, total_scraped, errors}`
- `POST /api/send` — sends last results via KakaoTalk
- `POST /api/settings` — saves config.yaml changes
- `_score_label(ratio)` → "fire"/"star"/"normal"/"tough" (used by frontend for badge color via `.b-fire`/`.b-star` CSS classes)

**`scrapers/`** — one file per platform, all return `list[Campaign]`.
- `base.py`: shared helpers (`parse_deadline`, `parse_applicants`, `parse_location`, `infer_category(title, benefit="")`, `curl_get(url, cookies="")`). `parse_deadline` handles D'day → 0.
- `reviewnote.py`: JSON API (`/api/v2/campaigns?city=서울&s=endingSoon`). Has `CATEGORY_MAP` to convert API category titles ("맛집"→"식당/술집", "뷰티"→"미용/뷰티") before falling back to `infer_category`. API fields: `infNum`(모집), `applicantCount`(신청), `offer`(혜택), `sido.name`(구), `category.title`, `channel`.
- `dinnerqueen.py`: uses `curl_get()` (SSL workaround). URL: `ct=지역&order=dday&area1={city}&area2=전체&sns[]=all`. Pages through deeply (up to 200) —비로그인 기준 D'day가 ~42페이지분 있고 그 뒤로 D-1, D-2 순 노출. `max_deadline_days` 초과 페이지 도달 시 조기 종료. Card root is `div.qz-dq-card`, title from `<a title="...">`, apply count in `<p class="apply_badge">`.
- `gangnam.py`: uses `requests`. AJAX endpoint (`_list_cmp_tpl.php`). Title in `<dt class="tit"><a>`, benefit in `<dd class="sub_tit">`.

**`filters.py`** — `apply()` filters by city/district/category/deadline/ratio, then sorts by weighted score (`_score()`). Four score components: `probability`, `benefit`, `distance`, `home_bonus`.

**`distance.py`** — precomputed Seoul 구 centroids, haversine formula. Mutates `campaign.distance_km` in-place.

**`config.yaml`** — all user-tunable settings. Edit this file to change districts, weights, location, API keys.

**`templates/index.html`** + **`static/css/style.css`** — web UI. JS-side filtering (platform / category checkboxes, sort) runs on the already-fetched campaign list without re-fetching.

## Known quirks

- **reviewnote** client-side filtering means all pages are fetched; `max_deadline_days+1` is passed to scraper to catch borderline items.
- **dinnerqueen** SSL fails with Python 3.9 LibreSSL → fetched via `subprocess curl`. The `order=dday` URL returns D'day first (~42 pages worth), then D-1, D-2, etc. — paging deeply is required to reach non-D'day campaigns. `scrape()` accepts `max_deadline_days` and stops as soon as a full page exceeds that threshold.
- `parse_deadline` handles `D'day` / `D-day` → 0. `parse_location` strips 구/시/군 suffix only when result ≥ 2 chars to prevent "서구" → "서" falsely matching "서대문".
- `benefit_amount` returns 0 for non-numeric benefits (e.g. "냉삼2인분") — these rank lower in scoring.
- dinnerqueen does not expose benefit/금액 in listing pages; `benefit` field is always empty for that platform.
- `infer_category` is case-insensitive and checks `title + benefit` together. Categories: "식당/술집", "카페/디저트", "미용/뷰티", "운동/관리", "기타". "식당"과 "술집"은 단일 카테고리로 합쳐져 있음.
- gangnam `ca=20` parameter means local campaigns (not a food/beauty filter) — category inference relies entirely on keyword matching.
- `config.yaml`의 `dinnerqueen.email` / `dinnerqueen.password`는 향후 자동 로그인용으로 예약된 필드 (현재 비어있어도 scraper 정상 동작).
