"""Translate a raw METAR observation string into plain-English sentences.

This is a pragmatic decoder covering the parts of a METAR a pilot or curious
reader cares about: time, wind, visibility, weather phenomena, clouds,
temperature/dew point, and altimeter. It is not a full spec implementation but
handles the overwhelming majority of real-world reports.
"""

from __future__ import annotations

import re

# --- lookup tables -------------------------------------------------------

_WX_DESCRIPTOR = {
    "MI": "shallow", "PR": "partial", "BC": "patches of", "DR": "low drifting",
    "BL": "blowing", "SH": "showers of", "TS": "thunderstorm", "FZ": "freezing",
}
_WX_PRECIP = {
    "DZ": "drizzle", "RA": "rain", "SN": "snow", "SG": "snow grains",
    "IC": "ice crystals", "PL": "ice pellets", "GR": "hail",
    "GS": "small hail", "UP": "unknown precipitation",
}
_WX_OBSCURATION = {
    "BR": "mist", "FG": "fog", "FU": "smoke", "VA": "volcanic ash",
    "DU": "widespread dust", "SA": "sand", "HZ": "haze", "PY": "spray",
}
_WX_OTHER = {
    "PO": "dust/sand whirls", "SQ": "squalls", "FC": "funnel cloud",
    "SS": "sandstorm", "DS": "duststorm",
}
_CLOUD_COVER = {
    "SKC": "sky clear", "CLR": "sky clear", "NSC": "no significant cloud",
    "NCD": "no cloud detected", "FEW": "few clouds", "SCT": "scattered clouds",
    "BKN": "broken clouds", "OVC": "overcast",
}
_COMPASS = [
    "north", "north-northeast", "northeast", "east-northeast", "east",
    "east-southeast", "southeast", "south-southeast", "south",
    "south-southwest", "southwest", "west-southwest", "west",
    "west-northwest", "northwest", "north-northwest",
]


def _compass(deg: int) -> str:
    return _COMPASS[int((deg % 360) / 22.5 + 0.5) % 16]


# --- field decoders ------------------------------------------------------

def _decode_time(tok: str):
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})Z", tok)
    if not m:
        return None
    day, hh, mm = m.groups()
    return f"Observed on the {_ordinal(int(day))} at {hh}:{mm} UTC."


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _decode_wind(tok: str):
    m = re.fullmatch(r"(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)", tok)
    if not m:
        return None
    direction, speed, gust, unit = m.groups()
    unit_word = {"KT": "knots", "MPS": "m/s", "KMH": "km/h"}[unit]
    spd = int(speed)
    if direction == "VRB":
        if spd == 0:
            return "Wind is calm."
        dir_txt = "variable in direction"
    elif spd == 0:
        return "Wind is calm."
    else:
        dir_txt = f"from the {_compass(int(direction))} ({int(direction)}°)"
    txt = f"Wind {dir_txt} at {spd} {unit_word}"
    if gust:
        txt += f", gusting to {int(gust)} {unit_word}"
    return txt + "."


def _decode_wind_var(tok: str):
    m = re.fullmatch(r"(\d{3})V(\d{3})", tok)
    if not m:
        return None
    return f"Wind direction varying between {int(m.group(1))}° and {int(m.group(2))}°."


def _decode_visibility(tok: str):
    if tok == "CAVOK":
        return "Ceiling and visibility OK (CAVOK) — visibility 10 km or more, no significant cloud or weather."
    if tok == "9999":
        return "Visibility 10 km or more (unlimited)."
    m = re.fullmatch(r"(\d{1,4})SM", tok)  # whole statute miles
    if m:
        return f"Visibility {int(m.group(1))} statute miles."
    m = re.fullmatch(r"(\d+)?(?:\s)?(\d+)/(\d+)SM", tok)
    if m:
        whole = int(m.group(1)) if m.group(1) else 0
        frac = int(m.group(2)) / int(m.group(3))
        return f"Visibility {whole + frac:.2f} statute miles."
    m = re.fullmatch(r"M?(\d{4})", tok)  # metres
    if m:
        metres = int(m.group(1))
        if metres >= 9999:
            return "Visibility 10 km or more."
        return f"Visibility {metres:,} metres ({metres/1000:.1f} km)."
    return None


def _decode_weather(tok: str):
    body = tok
    intensity = ""
    if body.startswith("+"):
        intensity, body = "heavy ", body[1:]
    elif body.startswith("-"):
        intensity, body = "light ", body[1:]
    elif body.startswith("VC"):
        intensity, body = "in the vicinity: ", body[2:]

    parts = re.findall(r"[A-Z]{2}", body)
    if not parts or "".join(parts) != body:
        return None

    words = []
    known = False
    for p in parts:
        if p in _WX_DESCRIPTOR:
            words.append(_WX_DESCRIPTOR[p]); known = True
        elif p in _WX_PRECIP:
            words.append(_WX_PRECIP[p]); known = True
        elif p in _WX_OBSCURATION:
            words.append(_WX_OBSCURATION[p]); known = True
        elif p in _WX_OTHER:
            words.append(_WX_OTHER[p]); known = True
        else:
            return None
    if not known:
        return None
    return (intensity + " ".join(words)).strip().capitalize() + "."


def _decode_cloud(tok: str):
    if tok in ("SKC", "CLR", "NSC", "NCD"):
        return _CLOUD_COVER[tok].capitalize() + "."
    m = re.fullmatch(r"(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?", tok)
    if not m:
        return None
    cover, height, kind = m.groups()
    feet = int(height) * 100
    if cover == "VV":
        return f"Sky obscured, vertical visibility {feet:,} ft."
    txt = f"{_CLOUD_COVER[cover].capitalize()} at {feet:,} ft"
    if kind == "CB":
        txt += " (cumulonimbus / thunderstorm cloud)"
    elif kind == "TCU":
        txt += " (towering cumulus)"
    return txt + "."


def _decode_temp(tok: str):
    m = re.fullmatch(r"(M?\d{2})/(M?\d{2})", tok)
    if not m:
        return None
    t = _signed(m.group(1))
    d = _signed(m.group(2))
    extra = ""
    spread = t - d
    if spread <= 2:
        extra = " Air is near saturation (fog/low cloud possible)."
    return f"Temperature {t}°C, dew point {d}°C.{extra}"


def _signed(s: str) -> int:
    return -int(s[1:]) if s.startswith("M") else int(s)


def _decode_altimeter(tok: str):
    m = re.fullmatch(r"A(\d{4})", tok)
    if m:
        inhg = int(m.group(1)) / 100
        return f"Altimeter {inhg:.2f} inHg ({inhg * 33.8639:.0f} hPa)."
    m = re.fullmatch(r"Q(\d{4})", tok)
    if m:
        hpa = int(m.group(1))
        return f"Altimeter {hpa} hPa ({hpa / 33.8639:.2f} inHg)."
    return None


# --- top level -----------------------------------------------------------

def parse(raw: str):
    """Decode a raw METAR string into a list of plain-English lines."""
    if not raw:
        return []
    tokens = raw.strip().split()
    lines = []

    # Drop leading "METAR"/"SPECI" report-type word and the station id.
    i = 0
    if tokens and tokens[0] in ("METAR", "SPECI"):
        i = 1
    if i < len(tokens) and re.fullmatch(r"[A-Z]{4}", tokens[i]):
        i += 1  # station id, already known to the caller

    in_remarks = False
    saw_wind = False
    for tok in tokens[i:]:
        if tok == "RMK":
            in_remarks = True
            lines.append("Remarks follow (coded supplementary data).")
            continue
        if in_remarks:
            continue
        if tok in ("AUTO", "COR"):
            lines.append(
                "Automated station report." if tok == "AUTO" else "Corrected report."
            )
            continue
        if tok == "NOSIG":
            lines.append("No significant change expected in the next two hours.")
            continue

        for decoder in (
            _decode_time, _decode_wind, _decode_wind_var, _decode_visibility,
            _decode_weather, _decode_cloud, _decode_temp, _decode_altimeter,
        ):
            out = decoder(tok)
            if out:
                lines.append(out)
                if decoder is _decode_wind:
                    saw_wind = True
                break

    return lines


def summary(raw: str) -> str:
    """One-paragraph human summary built from the decoded lines."""
    return " ".join(parse(raw))
