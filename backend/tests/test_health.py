# `client` fixture comes from conftest.py automatically.


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-ecommerce-automation-backend"
    assert "llm_provider" in body
    assert body["demo_mode"] is True


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["health"] == "/health"
