import httpx
import respx

from conftest import SECRET_VALUES
from flopstats.setup_check import check_all

AF_STATUS = "https://v3.football.api-sports.io/status"
STORAGE = "https://example.supabase.co/storage/v1/bucket"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"
NAMES = ["api-football", "supabase-db", "supabase-storage", "gemini", "footballia-login"]


class FakeConn:
    def __init__(self):
        self.closed = False

    def execute(self, sql):
        assert sql == "SELECT 1"
        return self

    def fetchone(self):
        return (1,)

    def close(self):
        self.closed = True


def fake_connect(settings):
    return FakeConn()


def _ok_routes(mock):
    mock.get(AF_STATUS).respond(
        200,
        json={
            "errors": [],
            "response": {
                "subscription": {"plan": "Pro", "active": True},
                "requests": {"current": 3, "limit_day": 7500},
            },
        },
    )
    mock.get(STORAGE).respond(200, json=[{"name": "clips"}])
    mock.get(GEMINI).respond(200, json={"models": [{"name": "models/x"}]})


def _assert_no_secrets(results):
    for r in results:
        for secret in SECRET_VALUES:
            assert secret not in r.detail


@respx.mock
def test_check_all_reports_each_service(settings):
    _ok_routes(respx)
    results = check_all(settings, connect=fake_connect)
    assert [r.name for r in results] == NAMES
    by = {r.name: r for r in results}
    for name in NAMES[:4]:
        assert by[name].ok, by[name]
    assert by["footballia-login"].skipped
    assert "skipped" in by["footballia-login"].detail
    _assert_no_secrets(results)


@respx.mock
def test_check_all_api_football_401(settings):
    _ok_routes(respx)
    respx.get(AF_STATUS).respond(401, json={"message": "unauthorized"})
    by = {r.name: r for r in check_all(settings, connect=fake_connect)}
    assert by["api-football"].ok is False
    assert "401" in by["api-football"].detail
    assert "af-secret-123" not in by["api-football"].detail


@respx.mock
def test_check_all_api_football_200_with_errors_is_fail(settings):
    _ok_routes(respx)
    respx.get(AF_STATUS).respond(
        200, json={"errors": {"token": "Error/Missing application key."}, "response": []}
    )
    by = {r.name: r for r in check_all(settings, connect=fake_connect)}
    assert by["api-football"].ok is False
    assert "token" in by["api-football"].detail


@respx.mock
def test_check_all_redacts_secrets_from_exceptions(settings):
    _ok_routes(respx)

    def boom(s):
        raise RuntimeError("connection failed for " + s.database_url.get_secret_value())

    respx.get(GEMINI).mock(side_effect=httpx.ConnectError("gem-secret-abc refused"))
    results = check_all(settings, connect=boom)
    by = {r.name: r for r in results}
    assert by["supabase-db"].ok is False
    assert by["gemini"].ok is False
    _assert_no_secrets(results)


def test_check_all_missing_key_is_fail_not_crash(settings):
    settings.gemini_key = None
    with respx.mock:
        _ok_routes(respx)
        by = {r.name: r for r in check_all(settings, connect=fake_connect)}
    assert by["gemini"].ok is False
    assert "GEMINI_KEY" in by["gemini"].detail
