"""Unit tests for metar_parser — the raw-METAR → plain-English decoder.

These are pure-function tests: no network, no Flask. Each weather element is
checked in isolation, plus a couple of full real-world reports end to end.
"""

import pytest

import metar_parser as mp


# --- time ---------------------------------------------------------------

def test_time_decodes_day_and_utc():
    assert mp._decode_time("251151Z") == "Observed on the 25th at 11:51 UTC."


@pytest.mark.parametrize("day, suffix", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (21, "21st")])
def test_time_ordinal_suffixes(day, suffix):
    tok = f"{day:02d}1200Z"
    assert suffix in mp._decode_time(tok)


def test_time_rejects_non_time_token():
    assert mp._decode_time("KJFK") is None


# --- wind ---------------------------------------------------------------

def test_wind_basic_direction_and_speed():
    out = mp._decode_wind("07004KT")
    assert "east-northeast" in out and "70°" in out and "4 knots" in out


def test_wind_calm():
    assert mp._decode_wind("00000KT") == "Wind is calm."


def test_wind_variable_direction():
    assert mp._decode_wind("VRB03KT") == "Wind variable in direction at 3 knots."


def test_wind_with_gusts():
    out = mp._decode_wind("27015G25KT")
    assert "gusting to 25 knots" in out and "west" in out


def test_wind_metres_per_second_unit():
    assert "m/s" in mp._decode_wind("09005MPS")


# --- wind variation -----------------------------------------------------

def test_wind_variation_range():
    assert mp._decode_wind_var("180V240") == "Wind direction varying between 180° and 240°."


# --- visibility ---------------------------------------------------------

def test_visibility_statute_miles():
    assert mp._decode_visibility("10SM") == "Visibility 10 statute miles."


def test_visibility_fractional_miles():
    assert mp._decode_visibility("1/2SM") == "Visibility 0.50 statute miles."


def test_visibility_cavok():
    assert "CAVOK" in mp._decode_visibility("CAVOK")


def test_visibility_9999_is_unlimited():
    assert "10 km or more" in mp._decode_visibility("9999")


def test_visibility_metres():
    out = mp._decode_visibility("3000")
    assert "3,000 metres" in out and "3.0 km" in out


# --- weather phenomena --------------------------------------------------

def test_weather_heavy_rain():
    assert mp._decode_weather("+RA") == "Heavy rain."


def test_weather_light_snow():
    assert mp._decode_weather("-SN") == "Light snow."


def test_weather_thunderstorm():
    assert "thunderstorm" in mp._decode_weather("TS").lower()


def test_weather_vicinity_prefix():
    assert "vicinity" in mp._decode_weather("VCFG").lower()


def test_weather_rejects_unknown_code():
    assert mp._decode_weather("ZZ") is None


# --- clouds -------------------------------------------------------------

def test_cloud_overcast_height():
    assert mp._decode_cloud("OVC011") == "Overcast at 1,100 ft."


def test_cloud_cumulonimbus_flag():
    out = mp._decode_cloud("SCT020CB")
    assert "cumulonimbus" in out and "2,000 ft" in out


def test_cloud_sky_clear():
    assert "clear" in mp._decode_cloud("SKC").lower()


def test_cloud_vertical_visibility():
    assert "Sky obscured" in mp._decode_cloud("VV002")


# --- temperature / dew point -------------------------------------------

def test_temp_positive():
    assert mp._decode_temp("22/14").startswith("Temperature 22°C, dew point 14°C.")


def test_temp_negative_values():
    assert mp._decode_temp("M05/M12") == "Temperature -5°C, dew point -12°C."


def test_temp_near_saturation_warns():
    assert "saturation" in mp._decode_temp("15/14")


# --- altimeter ----------------------------------------------------------

def test_altimeter_inhg():
    out = mp._decode_altimeter("A3007")
    assert "30.07 inHg" in out and "hPa" in out


def test_altimeter_hpa():
    out = mp._decode_altimeter("Q1013")
    assert out == "Altimeter 1013 hPa (29.91 inHg)."


# --- full reports / top-level API --------------------------------------

JFK = "METAR KJFK 251151Z 07004KT 10SM FEW110 BKN250 22/14 A3007 RMK SLP182 T02170144 10217 20172 53008"


def test_parse_full_jfk_report():
    lines = mp.parse(JFK)
    joined = " ".join(lines)
    assert "11:51 UTC" in joined
    assert "east-northeast" in joined
    assert "10 statute miles" in joined
    assert "Few clouds at 11,000 ft." in lines
    assert "Broken clouds at 25,000 ft." in lines
    assert "Temperature 22°C, dew point 14°C." in joined
    assert "30.07 inHg" in joined


def test_parse_skips_station_and_report_type():
    # Neither the "METAR" keyword nor the "KJFK" station id should appear as text.
    lines = mp.parse(JFK)
    assert not any("KJFK" in ln for ln in lines)


def test_parse_stops_decoding_at_remarks():
    lines = mp.parse(JFK)
    assert lines[-1] == "Remarks follow (coded supplementary data)."


def test_parse_empty_returns_empty_list():
    assert mp.parse("") == []
    assert mp.parse("   ") == []


def test_summary_is_lines_joined():
    raw = "METAR EGLL 251220Z AUTO 09017KT 9999 NCD 31/20 Q1017"
    assert mp.summary(raw) == " ".join(mp.parse(raw))


def test_parse_handles_automated_and_unlimited_vis():
    raw = "METAR EGLL 251220Z AUTO 09017KT 9999 NCD 31/20 Q1017"
    joined = " ".join(mp.parse(raw))
    assert "Automated station report." in joined
    assert "10 km or more" in joined
    assert "Temperature 31°C, dew point 20°C." in joined
