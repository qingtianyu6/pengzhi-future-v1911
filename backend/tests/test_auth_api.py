from fastapi.testclient import TestClient


def registration_payload(**overrides):
    payload = {
        "display_name": "莘县种植户",
        "phone": "13800138000",
        "organization": "示范园区",
        "password": "Greenhouse2026",
    }
    payload.update(overrides)
    return payload


def test_register_login_me_and_logout(client: TestClient) -> None:
    registered = client.post("/api/auth/register", json=registration_payload())
    assert registered.status_code == 200
    data = registered.json()["data"]
    assert data["user"]["phone"] == "13800138000"
    assert data["token"]

    headers = {"Authorization": f"Bearer {data['token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["data"]["display_name"] == "莘县种植户"
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    logged_in = client.post("/api/auth/login", json={
        "phone": "13800138000", "password": "Greenhouse2026", "remember_me": True,
    })
    assert logged_in.status_code == 200
    assert logged_in.json()["data"]["user"]["organization"] == "示范园区"


def test_duplicate_phone_and_wrong_password(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=registration_payload()).status_code == 200
    assert client.post("/api/auth/register", json=registration_payload()).status_code == 409
    response = client.post("/api/auth/login", json={
        "phone": "13800138000", "password": "wrong", "remember_me": False,
    })
    assert response.status_code == 401


def test_registration_validation(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=registration_payload(phone="123")).status_code == 422
    assert client.post("/api/auth/register", json=registration_payload(password="short")).status_code == 422
