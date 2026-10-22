"""HTTP error mapping and retry behaviour of CricbuzzClient (no network)."""
import pytest
import requests

from api.client import CricbuzzClient
from core.exceptions import APIAuthError, APINotFoundError, APIRateLimitError, APIResponseError


class FakeResponse:
    def __init__(self, status, body=b"{}", headers=None):
        self.status_code, self.content = status, body
        self.text = body.decode()
        self.headers = headers or {}

    def json(self):
        import json
        return json.loads(self.content)


@pytest.fixture
def client(monkeypatch):
    c = CricbuzzClient(api_key="test-key", host="example.test")
    monkeypatch.setattr("time.sleep", lambda s: None)        # no real back-off waits
    c._get_with_retry.retry.sleep = lambda s: None
    return c


def respond(client, monkeypatch, *responses):
    calls = iter(responses)
    counter = {"n": 0}

    def fake_get(*args, **kwargs):
        counter["n"] += 1
        r = next(calls)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(client.session, "get", fake_get)
    return counter


def test_success_and_quota(client, monkeypatch):
    respond(client, monkeypatch, FakeResponse(200, b'{"ok": 1}', {
        "x-ratelimit-requests-limit": "200", "x-ratelimit-requests-remaining": "150"}))
    assert client.get("/x") == {"ok": 1}
    assert client.quota == {"limit": 200, "remaining": 150}


def test_204_is_empty_not_error(client, monkeypatch):
    respond(client, monkeypatch, FakeResponse(204, b""))
    assert client.get("/x") == {}


@pytest.mark.parametrize("status, exc", [(401, APIAuthError), (403, APIAuthError),
                                         (404, APINotFoundError)])
def test_client_errors_are_not_retried(client, monkeypatch, status, exc):
    counter = respond(client, monkeypatch, FakeResponse(status), FakeResponse(200))
    with pytest.raises(exc):
        client.get("/x")
    assert counter["n"] == 1


def test_server_errors_are_retried_then_raised(client, monkeypatch):
    counter = respond(client, monkeypatch, *[FakeResponse(503)] * 3)
    with pytest.raises(APIResponseError):
        client.get("/x")
    assert counter["n"] == 3


def test_transient_failure_recovers(client, monkeypatch):
    respond(client, monkeypatch, requests.Timeout("slow"), FakeResponse(200, b'{"a": 2}'))
    assert client.get("/x") == {"a": 2}


def test_monthly_quota_exhausted_is_not_retried(client, monkeypatch):
    counter = respond(client, monkeypatch, FakeResponse(
        429, headers={"x-ratelimit-requests-remaining": "0"}))
    with pytest.raises(APIRateLimitError):
        client.get("/x")
    assert counter["n"] == 1


def test_missing_key_fails_fast():
    with pytest.raises(APIAuthError):
        CricbuzzClient(api_key="").get("/x")
