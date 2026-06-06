import uuid


def test_create_category_success(auth_client):
    r = auth_client.post("/api/categories/", json={"name": "내커스텀", "type": "EXPENSE"})
    assert r.status_code == 201
    assert r.json()["name"] == "내커스텀"


def test_create_duplicate_category_returns_409(auth_client):
    """같은 이름+타입 커스텀 카테고리 재생성 → 409 (500 아님)."""
    name = f"중복_{uuid.uuid4().hex[:6]}"
    first = auth_client.post("/api/categories/", json={"name": name, "type": "EXPENSE"})
    assert first.status_code == 201
    dup = auth_client.post("/api/categories/", json={"name": name, "type": "EXPENSE"})
    assert dup.status_code == 409


def test_update_category_to_existing_name_returns_409(auth_client):
    """다른 카테고리의 이름으로 개명 → 409 (500 아님)."""
    a = auth_client.post(
        "/api/categories/", json={"name": f"A_{uuid.uuid4().hex[:6]}", "type": "EXPENSE"}
    ).json()
    b = auth_client.post(
        "/api/categories/", json={"name": f"B_{uuid.uuid4().hex[:6]}", "type": "EXPENSE"}
    ).json()
    r = auth_client.patch(f"/api/categories/{b['id']}", json={"name": a["name"]})
    assert r.status_code == 409
