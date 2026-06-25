"""Route / integration tests for the Flask layer in app.py.

The only side-effecting dependency is ``fetch_metar`` (a live network call), so
every test here monkeypatches it. That keeps the suite fast, deterministic, and
fully offline while still exercising the real routing, resolution, and JSON
shaping logic.
"""

import app as flask_app_module

JFK_RAW = "METAR KJFK 251151Z 07004KT 10SM FEW110 BKN250 22/14 A3007 RMK SLP182 T02170144 10217 20172 53008"


# --- index page ---------------------------------------------------------

def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"METAR Reader" in resp.data


# --- /api/metar happy path ---------------------------------------------

def test_api_returns_decoded_metar(client, monkeypatch):
    # Pretend the upstream returned the canonical JFK report.
    monkeypatch.setattr(flask_app_module, "fetch_metar", lambda icao: JFK_RAW)

    resp = client.get("/api/metar?q=jfk")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["airport"]["icao"] == "KJFK"
    assert data["raw"] == JFK_RAW
    assert isinstance(data["plain"], list) and data["plain"]
    assert "11:51 UTC" in data["summary"]
    assert "alternatives" in data


def test_api_fetches_using_resolved_icao(client, monkeypatch):
    # Capture what ICAO the route asked the fetcher for.
    seen = {}

    def fake_fetch(icao):
        seen["icao"] = icao
        return JFK_RAW

    monkeypatch.setattr(flask_app_module, "fetch_metar", fake_fetch)
    client.get("/api/metar?q=kennedy")  # nickname -> KJFK
    assert seen["icao"] == "KJFK"


# --- /api/metar error paths --------------------------------------------

def test_api_empty_query_is_400(client):
    resp = client.get("/api/metar?q=")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_missing_query_param_is_400(client):
    resp = client.get("/api/metar")
    assert resp.status_code == 400


def test_api_no_airport_match_is_404(client):
    resp = client.get("/api/metar?q=qzxwvk")
    assert resp.status_code == 404
    assert "No airport found" in resp.get_json()["error"]


def test_api_airport_found_but_no_metar_is_502(client, monkeypatch):
    # Airport resolves, but the station has no current report.
    monkeypatch.setattr(flask_app_module, "fetch_metar", lambda icao: None)

    resp = client.get("/api/metar?q=jfk")
    assert resp.status_code == 502

    data = resp.get_json()
    assert data["airport"]["icao"] == "KJFK"
    assert "no current METAR" in data["error"]


# --- fetch_metar unit-ish tests (network mocked) -----------------------

def test_fetch_metar_returns_first_nonempty_line(monkeypatch):
    class FakeResp:
        def read(self):
            return b"\nMETAR KJFK 251151Z 07004KT\n"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(flask_app_module.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    assert flask_app_module.fetch_metar("KJFK") == "METAR KJFK 251151Z 07004KT"


def test_fetch_metar_returns_none_on_network_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(flask_app_module.urllib.request, "urlopen", boom)
    assert flask_app_module.fetch_metar("KJFK") is None


def test_fetch_metar_returns_none_on_empty_body(monkeypatch):
    class FakeResp:
        def read(self):
            return b"   \n  \n"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(flask_app_module.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    assert flask_app_module.fetch_metar("KJFK") is None
