"""
카카오 OAuth 토큰 발급 헬퍼.

사용법:
  python kakao_auth.py

1. Kakao Developers(https://developers.kakao.com)에서 앱 생성
2. 플랫폼 > Web > 사이트 도메인: http://localhost
3. 카카오 로그인 > 활성화 ON
4. 동의항목 > 카카오톡 메시지 전송 ON
5. REST API 키를 config.yaml의 kakao.rest_api_key에 입력
6. 이 스크립트 실행 → 브라우저에서 인증 → 터미널에 code 붙여넣기
7. 발급된 토큰을 config.yaml에 저장
"""
import sys
import webbrowser
import requests
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
REDIRECT_URI = "http://localhost"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_tokens(access_token: str, refresh_token: str) -> None:
    config = load_config()
    config["kakao"]["access_token"] = access_token
    config["kakao"]["refresh_token"] = refresh_token
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    print("✅ 토큰 저장 완료 (config.yaml)")


def get_tokens_from_code(rest_api_key: str, code: str, client_secret: str = "") -> dict:
    data = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    if client_secret:
        data["client_secret"] = client_secret

    # 방법 1: body에 client_secret 포함
    resp = requests.post(TOKEN_URL, data=data)
    if resp.ok:
        return resp.json()
    print(f"[방법1] 카카오 응답: {resp.status_code} {resp.text}")

    # 방법 2: HTTP Basic Auth 방식
    if client_secret:
        import base64
        creds = base64.b64encode(f"{rest_api_key}:{client_secret}".encode()).decode()
        resp2 = requests.post(TOKEN_URL, data=data, headers={"Authorization": f"Basic {creds}"})
        if resp2.ok:
            return resp2.json()
        print(f"[방법2] 카카오 응답: {resp2.status_code} {resp2.text}")

    resp.raise_for_status()
    return resp.json()


def refresh_access_token(rest_api_key: str, refresh_token: str) -> str:
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    })
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]


def ensure_valid_token(config: dict) -> str:
    """access_token 반환. 만료됐으면 refresh."""
    kakao = config.get("kakao", {})
    rest_api_key = kakao.get("rest_api_key", "")
    access_token = kakao.get("access_token", "")
    refresh_token = kakao.get("refresh_token", "")

    if not rest_api_key:
        raise ValueError("config.yaml에 kakao.rest_api_key를 입력하세요.")

    # 토큰 유효성 확인
    if access_token:
        check = requests.get(
            "https://kapi.kakao.com/v1/user/access_token_info",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if check.status_code == 200:
            return access_token

    # refresh
    if refresh_token:
        try:
            new_token = refresh_access_token(rest_api_key, refresh_token)
            save_tokens(new_token, refresh_token)
            return new_token
        except Exception:
            pass

    raise RuntimeError("토큰이 만료되었습니다. python kakao_auth.py 를 다시 실행하세요.")


if __name__ == "__main__":
    config = load_config()
    key = config.get("kakao", {}).get("rest_api_key", "")
    if not key:
        print("config.yaml의 kakao.rest_api_key를 먼저 입력하세요.")
        sys.exit(1)

    auth_url = (
        f"{AUTH_URL}?client_id={key}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    print(f"\n브라우저에서 카카오 로그인:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("로그인 후 리다이렉트된 URL에서 code= 값을 복사해 붙여넣으세요:")
    code = input("code: ").strip()

    client_secret = config.get("kakao", {}).get("client_secret", "")
    data = get_tokens_from_code(key, code, client_secret)
    save_tokens(data["access_token"], data.get("refresh_token", ""))
    print("인증 완료!")
