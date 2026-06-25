"""METAR reader — a small Flask web app.

Type an airport name, city, IATA code, or ICAO code; the app resolves it to a
weather station, fetches the live METAR from the NOAA Aviation Weather Center,
and renders both the raw report and a plain-English translation.

Architecture (three small modules, one job each):
    app.py          -> the web layer: routes, HTTP, and fetching live data.
    airports.py     -> turns free-text ("jfk", "Heathrow") into an airport.
    metar_parser.py -> turns a raw METAR string into plain-English sentences.
"""

from __future__ import annotations

import ssl
import urllib.parse
import urllib.request

from flask import Flask, jsonify, render_template, request

# Local modules — kept separate so each piece is testable on its own.
import airports          # resolve a query string to an airport record
import metar_parser      # decode a raw METAR into readable English

# The Flask application object. __name__ tells Flask where to find the
# bundled templates/ and static/ folders relative to this file.
app = Flask(__name__)

# NOAA Aviation Weather Center endpoint. `format=raw` returns the plain METAR
# text (one line per station) rather than JSON, which is all we need here.
# `{ids}` is filled in per-request with a URL-encoded ICAO code.
_METAR_URL = "https://aviationweather.gov/api/data/metar?ids={ids}&format=raw"

# Reuse a single TLS context for all outbound HTTPS calls instead of building
# one on every request (it validates the server certificate by default).
_SSL_CTX = ssl.create_default_context()


def fetch_metar(icao: str) -> str | None:
    """Fetch the latest raw METAR for an ICAO id, or ``None`` if unavailable.

    Network/HTTP problems are swallowed and reported as ``None`` so the caller
    can return a friendly message instead of a stack trace. Not every station
    publishes a METAR, so an empty response is a normal, expected outcome.
    """
    # URL-encode the code so an unexpected character can never break the URL.
    url = _METAR_URL.format(ids=urllib.parse.quote(icao))

    # A descriptive User-Agent is polite (and some public APIs require one).
    req = urllib.request.Request(url, headers={"User-Agent": "metar-reader/1.0"})

    try:
        # `timeout` guards against a slow/hung upstream holding our request open.
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            text = resp.read().decode("utf-8", "replace").strip()
    except Exception:
        # DNS failure, timeout, non-2xx status, TLS error, etc. -> treat as
        # "no data available" rather than crashing the request.
        return None

    # The raw endpoint returns one line per requested station; we asked for one,
    # so take the first non-empty line. Empty body -> None (no current report).
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return line or None


@app.route("/")
def index():
    """Serve the single-page web UI (templates/index.html)."""
    return render_template("index.html")


@app.route("/api/metar")
def api_metar():
    """JSON API: resolve a query, fetch its METAR, and return decoded results.

    Query string:
        q -- free text: airport name, city, IATA code, or ICAO code.

    Responses:
        200 -- airport + raw METAR + plain-English lines + summary + alternatives
        400 -- empty query
        404 -- no airport matched the query
        502 -- airport matched, but no current METAR is published for it
    """
    # Read and trim the `q` parameter. `request.args.get` returns None if absent.
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify(error="Please enter an airport name or code."), 400

    # Ask the airport resolver for candidates, best match first. We keep a few
    # so the UI can offer "did you mean …?" suggestions.
    matches = airports.search(query, limit=6)
    if not matches:
        return jsonify(error=f"No airport found matching “{query}”."), 404

    # Use the top-ranked airport and fetch its live observation.
    best = matches[0]
    raw = fetch_metar(best["icao"])
    if not raw:
        # Resolved an airport but it has no current report (e.g. small fields).
        # 502 = we reached out but the upstream had nothing usable for us.
        return jsonify(
            error=(
                f"Found {best['name']} ({best['icao']}), but no current METAR is "
                "available for that station."
            ),
            airport=best,
            alternatives=matches[1:],
        ), 502

    # Happy path: hand the raw METAR to the parser for both a sentence list
    # (`plain`) and a single-paragraph `summary`, and include the runner-up
    # matches so the user can switch airports without retyping.
    return jsonify(
        airport=best,
        raw=raw,
        plain=metar_parser.parse(raw),
        summary=metar_parser.summary(raw),
        alternatives=matches[1:],
    )


if __name__ == "__main__":
    # Development server only. `debug=True` enables auto-reload and the
    # interactive debugger — convenient locally, but do NOT use in production
    # (run behind a real WSGI server such as gunicorn/waitress instead).
    # Bound to 127.0.0.1 so it is reachable only from this machine.
    app.run(host="127.0.0.1", port=5000, debug=True)
