"""
카카오톡 나에게 보내기로 추천 체험단 알림 전송.
"""
import requests
from models import Campaign

SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def send(campaigns: list[Campaign], access_token: str) -> None:
    if not campaigns:
        _send_raw(access_token, "📭 오늘은 추천할 체험단이 없어요.")
        return

    lines = [f"🎯 당첨확률 높은 체험단 {len(campaigns)}개"]
    for i, c in enumerate(campaigns, 1):
        dist = f" · {c.distance_km:.1f}km" if c.distance_km is not None else ""
        benefit_line = f"\n💰 {c.benefit}" if c.benefit else ""
        lines.append(
            f"\n"
            f"{'─'*20}\n"
            f"{i}. {c.prob_label}  D-{c.deadline_days}  {c.district}{dist}\n"
            f"📌 {c.title}"
            f"{benefit_line}\n"
            f"👥 신청 {c.applicants}/{c.spots}명 ({c.ratio:.1f}:1)\n"
            f"🔗 {c.url}"
        )

    message = "\n".join(lines)
    _send_raw(access_token, message)


def _send_raw(access_token: str, text: str) -> None:
    payload = {
        "template_object": str({
            "object_type": "text",
            "text": text[:2000],
            "link": {"web_url": "https://www.reviewnote.co.kr/campaigns"},
        }).replace("'", '"')
    }
    # 카카오 API는 JSON 문자열로 전달
    import json
    resp = requests.post(
        SEND_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "template_object": json.dumps({
                "object_type": "text",
                "text": text[:2000],
                "link": {
                    "web_url": "https://www.reviewnote.co.kr/campaigns",
                    "mobile_web_url": "https://www.reviewnote.co.kr/campaigns",
                },
            }, ensure_ascii=False)
        },
    )
    if resp.status_code == 200:
        print("✅ 카카오톡 전송 완료")
    else:
        print(f"❌ 카카오톡 전송 실패: {resp.status_code} {resp.text}")
