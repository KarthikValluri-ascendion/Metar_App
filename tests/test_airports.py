"""Unit tests for airports — the free-text → airport resolver.

These run against the bundled ``airports.json`` (a fixed snapshot of the public
OurAirports data), so results are deterministic and need no network.
"""

import airports


# --- exact code matches -------------------------------------------------

def test_exact_icao_code():
    a = airports.resolve("KJFK")
    assert a["icao"] == "KJFK"
    assert "Kennedy" in a["name"]


def test_exact_icao_is_case_insensitive():
    assert airports.resolve("kjfk")["icao"] == "KJFK"


def test_exact_iata_code():
    a = airports.resolve("LAX")
    assert a["icao"] == "KLAX"


def test_us_iata_without_dataset_entry_falls_back_to_k_prefix():
    # A 3-letter US code resolves to its K-prefixed ICAO when looked up directly.
    a = airports.resolve("SFO")
    assert a["icao"] == "KSFO"


# --- aliases / nicknames ------------------------------------------------

def test_alias_kennedy():
    assert airports.resolve("kennedy")["icao"] == "KJFK"


def test_alias_is_case_and_space_insensitive():
    assert airports.resolve("O Hare")["icao"] == "KORD"


def test_alias_heathrow():
    assert airports.resolve("Heathrow")["icao"] == "EGLL"


# --- fuzzy name / city search ------------------------------------------

def test_name_search_finds_changi():
    assert airports.resolve("changi")["icao"] == "WSSS"


def test_city_search_prefers_large_airport():
    # "san francisco" should surface SFO (a large airport) at the top.
    assert airports.resolve("san francisco")["icao"] == "KSFO"


def test_search_returns_ranked_candidates():
    results = airports.search("london", limit=5)
    assert len(results) >= 2
    icaos = {r["icao"] for r in results}
    assert "EGLL" in icaos  # Heathrow should be among London matches


def test_search_respects_limit():
    assert len(airports.search("airport", limit=3)) <= 3


# --- no-match / empty behaviour ----------------------------------------

def test_no_match_returns_empty_list():
    assert airports.search("qzxwvk") == []


def test_resolve_returns_none_when_no_match():
    assert airports.resolve("qzxwvk") is None


def test_empty_query_returns_empty():
    assert airports.search("") == []
    assert airports.resolve("   ") is None


# --- record shape -------------------------------------------------------

def test_airport_record_has_expected_fields():
    a = airports.resolve("KJFK")
    for field in ("icao", "iata", "name", "city", "country", "type"):
        assert field in a
