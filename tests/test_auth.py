import uuid
from datetime import datetime, timezone, timedelta

from jose import jwt

from app.config import settings
from app.auth.models import RefreshToken


def _token(sub, token_type):
    """테스트용 JWT 생성 (앱과 동일 비밀키·알고리즘). sub=None 이면 sub 생략."""
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "type": token_type,
    }
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def test_signup_login_flow(client):
    """정상 회원가입 → 로그인 → 토큰 발급 (auth 기본 동작 회귀)."""
    email = f"u_{uuid.uuid4().hex[:6]}@example.com"
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "pass1234",
        "password_confirm": "pass1234", "name": "테스터",
    })
    assert r.status_code == 201

    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_signup_rejects_too_long_password(client):
    """72바이트 초과 비밀번호 → 422 (bcrypt 72바이트 한계)."""
    email = f"u_{uuid.uuid4().hex[:6]}@example.com"
    long_pw = "a1" * 70  # 140바이트, 영문+숫자 충족하지만 한계 초과
    r = client.post("/api/auth/signup", json={
        "email": email, "password": long_pw,
        "password_confirm": long_pw, "name": "테스터",
    })
    assert r.status_code == 422


def test_password_change_rejects_too_long_password(auth_client):
    """비밀번호 변경 시 72바이트 초과 → 422 (요청 검증 단계)."""
    long_pw = "a1" * 70
    r = auth_client.put("/api/auth/password", json={
        "current_password": "whatever",
        "new_password": long_pw,
        "new_password_confirm": long_pw,
    })
    assert r.status_code == 422


def test_signup_rejects_password_over_72_bytes_korean(client):
    """글자 수는 128자 이하지만 UTF-8 72바이트를 넘는 비밀번호 → 422 (bcrypt 500 방지).

    한글 1자 = 3바이트. 31자(=93바이트)는 글자 수 제한은 통과하지만 바이트 한계 초과.
    """
    email = f"u_{uuid.uuid4().hex[:6]}@example.com"
    pw = "가" * 30 + "1"  # 31자, 91바이트, 영문/숫자 규칙상 한글(letter)+숫자 충족
    r = client.post("/api/auth/signup", json={
        "email": email, "password": pw,
        "password_confirm": pw, "name": "테스터",
    })
    assert r.status_code == 422


def test_login_with_over_72_byte_password_returns_401(client):
    """72바이트 초과 비밀번호로 로그인 시도 → 401 (verify_password 가 500 대신 False)."""
    email = f"u_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/auth/signup", json={
        "email": email, "password": "pass1234",
        "password_confirm": "pass1234", "name": "테스터",
    })
    r = client.post("/api/auth/login", json={
        "email": email, "password": "가" * 30 + "1",
    })
    assert r.status_code == 401


def test_missing_auth_header_returns_401(client):
    """Authorization 헤더 없이 보호된 엔드포인트 접근 → 401 (403 아님)."""
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_malformed_sub_access_token_returns_401(client):
    """sub 가 uuid 형식이 아닌 access token → 401 (500 아님)."""
    token = _token("not-a-uuid", "access")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_non_string_sub_access_token_returns_401(client):
    """sub 가 문자열이 아닌(숫자) access token → 401 (TypeError 500 방지)."""
    token = _token(12345, "access")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_refresh_with_malformed_sub_returns_401(client, test_user, db):
    """sub 가 uuid 형식이 아닌 refresh token(DB 존재) → 401 (500 아님)."""
    token = _token("not-a-uuid", "refresh")
    db.add(RefreshToken(
        user_id=test_user.id, token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    ))
    db.commit()

    r = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


def test_refresh_with_missing_sub_returns_401(client, test_user, db):
    """sub 없는 refresh token(DB 존재) → 401 (500 아님)."""
    token = _token(None, "refresh")
    db.add(RefreshToken(
        user_id=test_user.id, token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    ))
    db.commit()

    r = client.post("/api/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401
