import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.storage import LinkStore


@pytest.fixture
def server():
    """A fresh in-memory fake Redis server for every test."""
    return fakeredis.FakeServer()


@pytest.fixture
def client(server):
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)
    app.dependency_overrides[get_store] = lambda: LinkStore(fake)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_and_follow_link(client):
    response = client.post("/links", json={"url": "https://github.com/ido-DevOps"})
    assert response.status_code == 201
    code = response.json()["code"]
    assert response.json()["short_url"].endswith(f"/r/{code}")

    response = client.get(f"/r/{code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://github.com/ido-DevOps"


def test_unknown_code_returns_404(client):
    response = client.get("/r/nope00", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.parametrize("bad_url", ["hello", "javascript:alert(1)", "ftp://example.com/file"])
def test_invalid_url_is_rejected(client, bad_url):
    response = client.post("/links", json={"url": bad_url})
    assert response.status_code == 422


def test_health_is_ok(client):
    assert client.get("/health").status_code == 200


def test_ready_when_redis_is_up(client):
    assert client.get("/ready").status_code == 200


def test_ready_and_api_return_503_when_redis_is_down(client, server):
    server.connected = False  # simulate Redis going away
    assert client.get("/ready").status_code == 503
    assert client.post("/links", json={"url": "https://example.com"}).status_code == 503
    # liveness must stay green: the app itself is fine, so Kubernetes should not restart it
    assert client.get("/health").status_code == 200


def test_metrics_use_route_templates(client):
    code = client.post("/links", json={"url": "https://example.com"}).json()["code"]
    client.get(f"/r/{code}", follow_redirects=False)

    body = client.get("/metrics").text
    assert "links_created_total" in body
    assert 'route="/r/{code}"' in body
    assert code not in body  # the real code must never become a label (cardinality)
