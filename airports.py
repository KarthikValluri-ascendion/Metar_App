"""Airport lookup: resolve a free-text query (ICAO, IATA, name, or city) to an airport.

Data comes from the bundled ``airports.json`` (a trimmed slice of the OurAirports
public dataset). The matcher is deliberately forgiving so that inputs like
"jfk", "kennedy", "new york", or "KJFK" all resolve sensibly.
"""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache

_DATA_FILE = os.path.join(os.path.dirname(__file__), "airports.json")


@lru_cache(maxsize=1)
def _load():
    with open(_DATA_FILE, encoding="utf-8") as f:
        airports = json.load(f)

    by_icao = {}
    by_iata = {}
    for a in airports:
        by_icao.setdefault(a["icao"], a)
        if a["iata"]:
            by_iata.setdefault(a["iata"], a)
    return airports, by_icao, by_iata


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


# Common nicknames / colloquial names that don't appear verbatim in the dataset.
_ALIASES = {
    "kennedy": "KJFK",
    "jfk": "KJFK",
    "newark": "KEWR",
    "laguardia": "KLGA",
    "ohare": "KORD",
    "o hare": "KORD",
    "midway": "KMDW",
    "heathrow": "EGLL",
    "gatwick": "EGKK",
    "charles de gaulle": "LFPG",
    "cdg": "LFPG",
    "schiphol": "EHAM",
    "logan": "KBOS",
    "dulles": "KIAD",
    "reagan": "KDCA",
    "sea tac": "KSEA",
    "seatac": "KSEA",
    "haneda": "RJTT",
    "narita": "RJAA",
    "changi": "WSSS",
    "dubai": "OMDB",
    "sfo": "KSFO",
    "lax": "KLAX",
}


def _score(query: str, airport: dict) -> float:
    """Heuristic relevance score for a name/city match (0..~120)."""
    q = _norm(query)
    name = _norm(airport["name"])
    city = _norm(airport["city"])
    best = 0.0

    for field, weight in ((name, 1.0), (city, 0.95)):
        if not field:
            continue
        if q == field:
            best = max(best, 100 * weight)
        elif field.startswith(q) or q in field.split():
            best = max(best, 85 * weight)
        elif q in field:
            best = max(best, 70 * weight)
        else:
            ratio = SequenceMatcher(None, q, field).ratio()
            best = max(best, ratio * 60 * weight)

    # Prefer bigger airports when scores are otherwise close.
    bonus = {"large": 12, "medium": 5, "small": 0}.get(airport["type"], 0)
    return best + bonus


def search(query: str, limit: int = 6):
    """Return a ranked list of candidate airports for a free-text query."""
    airports, by_icao, by_iata = _load()
    q = (query or "").strip()
    if not q:
        return []

    up = q.upper()
    nq = _norm(q)

    # 1. Exact ICAO code.
    if len(up) == 4 and up in by_icao:
        return [by_icao[up]]
    # 2. Exact IATA code.
    if len(up) == 3 and up in by_iata:
        return [by_iata[up]]
    # 3. Known alias / nickname.
    if nq in _ALIASES and _ALIASES[nq] in by_icao:
        return [by_icao[_ALIASES[nq]]]
    # 4. US 3-letter IATA without a dataset entry -> try K-prefixed ICAO.
    if len(up) == 3 and up.isalpha() and ("K" + up) in by_icao:
        return [by_icao["K" + up]]

    # 5. Fuzzy name / city search.
    scored = ((_score(q, a), a) for a in airports)
    ranked = sorted((s for s in scored if s[0] >= 45), key=lambda x: x[0], reverse=True)
    return [a for _, a in ranked[:limit]]


def resolve(query: str):
    """Return the single best-matching airport, or ``None``."""
    results = search(query, limit=1)
    return results[0] if results else None
