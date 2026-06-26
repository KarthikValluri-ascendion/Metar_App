# METAR Reader ✈️

[![CI](https://github.com/KarthikValluri-ascendion/Metar_App/actions/workflows/ci.yml/badge.svg)](https://github.com/KarthikValluri-ascendion/Metar_App/actions/workflows/ci.yml)

A small **Flask** web app that reads airport weather (a *METAR*) and explains it
in plain English — similar to how [metar.live](https://metar.live/) works.

Type an **airport name, city, IATA code, or ICAO code** (e.g. `JFK`, `Heathrow`,
`San Francisco`, `KSFO`) and the app will:

1. **Resolve** your text to a weather station — fuzzy name/city search plus
   IATA/ICAO codes and common nicknames (`kennedy` → `KJFK`).
2. **Fetch** the live raw METAR from the NOAA Aviation Weather Center.
3. **Translate** it — show the raw report *and* a plain-English breakdown.

---

## What is a METAR?

A **METAR** is the standard coded weather report issued by airports worldwide.
It's compact but cryptic. For example, John F. Kennedy International (KJFK):

```
METAR KJFK 251151Z 07004KT 10SM FEW110 BKN250 22/14 A3007 RMK SLP182 T02170144 10217 20172 53008
```

This app decodes that into:

> Observed on the 25th at 11:51 UTC. Wind from the east-northeast (70°) at 4
> knots. Visibility 10 statute miles. Few clouds at 11,000 ft. Broken clouds at
> 25,000 ft. Temperature 22°C, dew point 14°C. Altimeter 30.07 inHg (1018 hPa).

---

## Quick start (with a virtual environment — recommended)

A virtual environment keeps this app's dependencies isolated from your system
Python. From the project folder:

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

> If activation is blocked by an execution-policy error, run once:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**macOS / Linux (bash):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Then open **<http://127.0.0.1:5000>** and search for an airport.
Press **Ctrl+C** to stop the server; run `deactivate` to leave the venv.

---

## How it works

The code is split into three small, single-purpose modules:

| File | Purpose |
| --- | --- |
| `app.py` | Flask web layer — routes, HTTP, and fetching live METAR data |
| `airports.py` | Resolve a free-text query → airport (name/city + IATA/ICAO + aliases) |
| `metar_parser.py` | Decode a raw METAR string into plain-English sentences |
| `airports.json` | Bundled airport database (trimmed from the public OurAirports dataset) |
| `templates/`, `static/` | The single-page web UI (HTML / CSS / JS) |
| `requirements.txt` | Python dependencies (just Flask) |

**Request flow:** the browser calls `/api/metar?q=<text>` → `airports.search()`
ranks candidate airports → `fetch_metar()` pulls the live report from NOAA for
the best match → `metar_parser.parse()` turns it into readable lines → the UI
renders the raw report, the plain-English summary, and any "did you mean…?"
alternatives.

---

## Running the tests

The project ships with a [pytest](https://pytest.org) suite (64 tests) covering
the METAR decoder, the airport resolver, and the Flask routes. The live network
call is **mocked**, so the suite is fast, deterministic, and runs fully offline.

### Run them

From the project root (the folder containing `pyproject.toml`), with your
virtual environment activated:

```bash
# 1. Install the test dependency (first time only — pulls in Flask + pytest)
python -m pip install -r requirements-dev.txt

# 2. Run the whole suite
python -m pytest
```

A successful run ends with a green summary line:

```
============================= 64 passed in 7.57s ==============================
```

> Tip: prefer `python -m pytest` over a bare `pytest` — it guarantees you run the
> pytest inside your active virtual environment against the right Python.

### Useful variations

| Goal | Command |
| --- | --- |
| Verbose — one line per test | `python -m pytest -v` |
| Stop at the first failure | `python -m pytest -x` |
| Run a single file | `python -m pytest tests/test_metar_parser.py` |
| Run tests matching a name | `python -m pytest -k wind_with_gusts` |
| Show `print` / log output | `python -m pytest -s` |

### Coverage (optional)

See which lines the tests exercise:

```bash
python -m pip install pytest-cov
python -m pytest --cov=. --cov-report=term-missing
```

### Test layout

| File | Covers |
| --- | --- |
| `tests/test_metar_parser.py` | Decoding of each METAR element + full reports |
| `tests/test_airports.py` | Code/alias/fuzzy resolution against the bundled DB |
| `tests/test_app.py` | Flask routes + JSON shape + error codes (network mocked) |
| `tests/conftest.py` | Shared fixtures (`app`, `client`) |

Configuration lives in `pyproject.toml` under `[tool.pytest.ini_options]`
(`pythonpath = ["."]` lets the tests import `app`, `airports`, and
`metar_parser` without packaging the project).

### Troubleshooting

- **`pytest: command not found`** → use `python -m pytest`, or re-run the install step.
- **`ModuleNotFoundError: No module named 'flask'`** → the venv isn't active or
  deps aren't installed; activate it and re-run the install step.
- **`No module named 'app'` / `collected 0 items`** → run pytest from the
  project root (the folder with `pyproject.toml`).

The same `python -m pytest` command runs automatically in GitHub Actions on
every push and pull request — see [CI](#) (`.github/workflows/ci.yml`).

---

## API reference

### `GET /api/metar?q=<query>`

| Status | Meaning |
| --- | --- |
| `200` | `{ airport, raw, plain[], summary, alternatives[] }` |
| `400` | Empty query |
| `404` | No airport matched the query |
| `502` | Airport matched, but no current METAR is published for it |

Example:

```bash
curl "http://127.0.0.1:5000/api/metar?q=jfk"
```

---

## Notes

- **Live data** comes from `https://aviationweather.gov/api/data/metar`, so the
  machine running the app needs internet access. Airport lookup itself works
  offline because `airports.json` is bundled.
- **Not every airport publishes a METAR.** If a resolved station has no current
  report, the app says so and offers close alternatives.
- This is a **development server** (`debug=True`). For production, run behind a
  proper WSGI server such as `waitress` or `gunicorn`.

---

## Credits

- Live weather: [NOAA Aviation Weather Center](https://aviationweather.gov/)
- Airport database: [OurAirports](https://ourairports.com/) (public domain)
