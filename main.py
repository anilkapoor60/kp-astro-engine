import math
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
from dateutil import parser as date_parser
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import swisseph as swe

app = FastAPI(
    title="KP Stellar Astrology Engine",
    description="High-precision KP calculations using Swiss Ephemeris",
    version="1.3.0",
)

swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0.0, 0.0)

# ==========================================
# CONSTANTS & KP DEFINITIONS
# ==========================================
ZODIAC_SIGNS = [
    ("Aries", "Mars"), ("Taurus", "Venus"), ("Gemini", "Mercury"),
    ("Cancer", "Moon"), ("Leo", "Sun"), ("Virgo", "Mercury"),
    ("Libra", "Venus"), ("Scorpio", "Mars"), ("Sagittarius", "Jupiter"),
    ("Capricorn", "Saturn"), ("Aquarius", "Saturn"), ("Pisces", "Jupiter")
]

NAKSHATRAS = [
    ("Ashwini", "Ketu"), ("Bharani", "Venus"), ("Krittika", "Sun"),
    ("Rohini", "Moon"), ("Mrigashira", "Mars"), ("Ardra", "Rahu"),
    ("Punarvasu", "Jupiter"), ("Pushya", "Saturn"), ("Ashlesha", "Mercury"),
    ("Magha", "Ketu"), ("Purva Phalguni", "Venus"), ("Uttara Phalguni", "Sun"),
    ("Hasta", "Moon"), ("Chitra", "Mars"), ("Swati", "Rahu"),
    ("Vishakha", "Jupiter"), ("Anuradha", "Saturn"), ("Jyeshtha", "Mercury"),
    ("Mula", "Ketu"), ("Purva Ashadha", "Venus"), ("Uttara Ashadha", "Sun"),
    ("Shravana", "Moon"), ("Dhanishta", "Mars"), ("Shatabhisha", "Rahu"),
    ("Purva Bhadrapada", "Jupiter"), ("Uttara Bhadrapada", "Saturn"), ("Revati", "Mercury")
]

DASHA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_YEARS = 120.0
NAKSHATRA_SPAN = 800.0  # 13°20' in arcminutes

# ==========================================
# MATHEMATICAL HELPER FUNCTIONS
# ==========================================
def to_dms(degrees: float) -> str:
    """Converts decimal degrees to clean DD° MM' SS\" string."""
    degrees = degrees % 360.0
    deg = int(degrees)
    rem = (degrees - deg) * 60.0
    minute = int(rem)
    sec = int(round((rem - minute) * 60.0))
    if sec >= 60:
        sec = 0
        minute += 1
    if minute >= 60:
        minute = 0
        deg += 1
    if deg >= 30:
        deg = deg % 30
    return f"{deg:02d}° {minute:02d}' {sec:02d}\""

def get_cusp_degree(cusp_tuple, house_num: int) -> float:
    """Safely retrieves cusp whether tuple has 12 items (pyswisseph) or 13 items."""
    if len(cusp_tuple) == 12:
        return cusp_tuple[house_num - 1]
    return cusp_tuple[house_num]

def get_kp_coordinates(lon: float) -> Dict:
    """Calculates Sign, Sign Lord, Star, Star Lord, Sub-Lord, and Sub-Sub-Lord."""
    lon = lon % 360.0
    sign_idx = int(round(lon, 7) // 30.0) % 12
    sign_name, sign_lord = ZODIAC_SIGNS[sign_idx]
    deg_in_sign = lon - (sign_idx * 30.0)

    nak_idx = int(round(lon, 7) // (360.0 / 27.0)) % 27
    nak_name, star_lord = NAKSHATRAS[nak_idx]
    nak_start = nak_idx * (360.0 / 27.0)
    deg_in_nak_mins = round((lon - nak_start) * 60.0, 6)

    start_lord_idx = DASHA_LORDS.index(star_lord)
    accum_mins = 0.0
    sub_lord = star_lord
    sub_sub_lord = star_lord

    for i in range(9):
        curr_lord = DASHA_LORDS[(start_lord_idx + i) % 9]
        span_mins = round((DASHA_YEARS[(start_lord_idx + i) % 9] / TOTAL_YEARS) * NAKSHATRA_SPAN, 6)
        if (accum_mins - 1e-6) <= deg_in_nak_mins < (accum_mins + span_mins - 1e-6):
            sub_lord = curr_lord
            deg_in_sub_mins = deg_in_nak_mins - accum_mins
            sub_start_idx = DASHA_LORDS.index(sub_lord)
            accum_ss_mins = 0.0
            for j in range(9):
                curr_ss_lord = DASHA_LORDS[(sub_start_idx + j) % 9]
                span_ss_mins = round((DASHA_YEARS[(sub_start_idx + j) % 9] / TOTAL_YEARS) * span_mins, 6)
                if (accum_ss_mins - 1e-6) <= deg_in_sub_mins < (accum_ss_mins + span_ss_mins - 1e-6):
                    sub_sub_lord = curr_ss_lord
                    break
                accum_ss_mins += span_ss_mins
            break
        accum_mins += span_mins

    return {
        "longitude": lon,
        "sign": sign_name,
        "degree_in_sign": to_dms(deg_in_sign),
        "sign_lord": sign_lord,
        "nakshatra": nak_name,
        "star_lord": star_lord,
        "sub_lord": sub_lord,
        "sub_sub_lord": sub_sub_lord,
    }

# ==========================================
# KP 249 HORARY TABLE GENERATOR
# ==========================================
def build_kp_249_table() -> List[Dict]:
    """
    Generates the exact 249 KP Horary Sub Table of Prof. K.S. Krishnamurti.
    Splits occur ONLY across the 6 nakshatras that cross 30° sign boundaries:
    Krittika (30°), Punarvasu (90°), Uttara Phalguni (150°),
    Vishakha (210°), Uttara Ashadha (270°), and Purva Bhadrapada (330°).
    """
    table = []
    curr_lon = 0.0

    for nak_idx, (nak_name, star_lord) in enumerate(NAKSHATRAS):
        start_lord_idx = DASHA_LORDS.index(star_lord)
        for i in range(9):
            sub_lord = DASHA_LORDS[(start_lord_idx + i) % 9]
            sub_span_deg = ((DASHA_YEARS[(start_lord_idx + i) % 9] / TOTAL_YEARS) * NAKSHATRA_SPAN) / 60.0
            end_lon = curr_lon + sub_span_deg

            curr_sign = int(round(curr_lon, 6) // 30.0)
            next_boundary = (curr_sign + 1) * 30.0

            if curr_lon < (next_boundary - 1e-5) and end_lon > (next_boundary + 1e-5) and next_boundary < 360.0:
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": curr_lon,
                    "end_lon": next_boundary,
                    "sign": ZODIAC_SIGNS[curr_sign][0],
                    "sign_lord": ZODIAC_SIGNS[curr_sign][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": next_boundary,
                    "end_lon": end_lon,
                    "sign": ZODIAC_SIGNS[curr_sign + 1][0],
                    "sign_lord": ZODIAC_SIGNS[curr_sign + 1][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
            else:
                sign_idx = int(round(curr_lon, 6) // 30.0) % 12
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": curr_lon,
                    "end_lon": end_lon,
                    "sign": ZODIAC_SIGNS[sign_idx][0],
                    "sign_lord": ZODIAC_SIGNS[sign_idx][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
            curr_lon = end_lon

    return table

KP_249_TABLE = build_kp_249_table()

# ==========================================
# 4-STEP SIGNIFICATORS ENGINE
# ==========================================
def calculate_4step_significators(planets: Dict, cusps: Dict) -> Dict:
    house_occupants = {i: [] for i in range(1, 13)}
    for p_name, p_data in planets.items():
        p_lon = p_data["longitude"]
        for i in range(1, 13):
            c_start = cusps[i]["longitude"]
            c_end = cusps[1]["longitude"] if i == 12 else cusps[i + 1]["longitude"]
            if c_start < c_end:
                if c_start <= p_lon < c_end:
                    house_occupants[i].append(p_name)
                    break
            else:
                if p_lon >= c_start or p_lon < c_end:
                    house_occupants[i].append(p_name)
                    break

    house_lords = {i: cusps[i]["sign_lord"] for i in range(1, 13)}
    significators = {}
    for p_name, p_data in planets.items():
        star_lord = p_data["star_lord"]
        l1 = [h for h, occs in house_occupants.items() if star_lord in occs]
        l2 = [h for h, occs in house_occupants.items() if p_name in occs]
        l3 = [h for h, lord in house_lords.items() if lord == star_lord]
        l4 = [h for h, lord in house_lords.items() if lord == p_name]

        significators[p_name] = {
            "level_1": sorted(list(set(l1))),
            "level_2": sorted(list(set(l2))),
            "level_3": sorted(list(set(l3))),
            "level_4": sorted(list(set(l4))),
            "all_signified_houses": sorted(list(set(l1 + l2 + l3 + l4)))
        }
    return significators

# ==========================================
# PYDANTIC REQUEST SCHEMAS
# ==========================================
class NatalRequest(BaseModel):
    dob: str
    tob: str
    lat: float = 30.9010
    lon: float = 75.8573
    tz: float = 5.5
    city: Optional[str] = "Ludhiana"

class HoraryRequest(BaseModel):
    seed: int
    query_date: Optional[str] = None
    query_time: Optional[str] = None
    city: Optional[str] = "Ludhiana"
    lat: float = 30.9010
    lon: float = 75.8573
    tz: float = 5.5

# ==========================================
# API ROUTES
# ==========================================
@app.get("/")
def root():
    return {
        "message": "KP Stellar Astrology Engine is live!",
        "documentation": "/docs",
        "health_check": "/health"
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "Swiss Ephemeris KP Engine"}

@app.post("/kp/natal")
def calculate_natal(req: NatalRequest):
    try:
        dt = date_parser.parse(f"{req.dob} {req.tob}", dayfirst=True)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date/time format '{req.dob} {req.tob}'. Use DD/MM/YYYY and HH:mm."
        )

    utc_hours = dt.hour + (dt.minute / 60.0) + (dt.second / 3600.0) - req.tz
    jd_ut = swe.julday(dt.year, dt.month, dt.day, utc_hours)
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0.0, 0.0)

    # 12 Placidus Cusps
    cusp_data, _ = swe.houses_ex(jd_ut, req.lat, req.lon, b'P', swe.FLG_SIDEREAL)
    cusps = {}
    for i in range(1, 13):
        deg_sid = get_cusp_degree(cusp_data, i)
        coords = get_kp_coordinates(deg_sid)
        cusps[i] = {
            "house": i,
            "longitude": round(deg_sid, 4),
            "sign": coords["sign"],
            "degree": coords["degree_in_sign"],
            "sign_lord": coords["sign_lord"],
            "star_lord": coords["star_lord"],
            "sub_lord": coords["sub_lord"]
        }

    # 9 Planetary Coordinates
    PLANET_MAP = [
        ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS),
        ("Mercury", swe.MERCURY), ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
        ("Saturn", swe.SATURN), ("Rahu", swe.MEAN_NODE)
    ]
    planets = {}
    for name, pid in PLANET_MAP:
        res, _ = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED)
        lon = res[0]
        coords = get_kp_coordinates(lon)
        planets[name] = {
            "longitude": round(lon, 4),
            "sign": coords["sign"],
            "degree": coords["degree_in_sign"],
            "sign_lord": coords["sign_lord"],
            "star_lord": coords["star_lord"],
            "sub_lord": coords["sub_lord"],
            "sub_sub_lord": coords["sub_sub_lord"],
            "retrograde": res[3] < 0
        }

    ketu_lon = (planets["Rahu"]["longitude"] + 180.0) % 360.0
    k_coords = get_kp_coordinates(ketu_lon)
    planets["Ketu"] = {
        "longitude": round(ketu_lon, 4),
        "sign": k_coords["sign"],
        "degree": k_coords["degree_in_sign"],
        "sign_lord": k_coords["sign_lord"],
        "star_lord": k_coords["star_lord"],
        "sub_lord": k_coords["sub_lord"],
        "sub_sub_lord": k_coords["sub_sub_lord"],
        "retrograde": True
    }

    significators = calculate_4step_significators(planets, cusps)

    return {
        "status": 200,
        "calculation_type": "KP Natal",
        "birth_details": {
            "dob": dt.strftime("%d/%m/%Y"),
            "tob": dt.strftime("%H:%M"),
            "city": req.city,
            "lat": req.lat,
            "lon": req.lon,
            "tz": req.tz
        },
        "planets": planets,
        "houses": cusps,
        "four_step_significators": significators
    }

@app.post("/kp/horary")
def calculate_horary(req: HoraryRequest):
    if not (1 <= req.seed <= 249):
        raise HTTPException(status_code=400, detail="Horary Seed Number must be between 1 and 249.")

    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(ist)

    raw_date = req.query_date
    if not raw_date or str(raw_date).strip().lower() in ["string", "null", "none", ""]:
        raw_date = now_ist.strftime("%d/%m/%Y")

    raw_time = req.query_time
    if not raw_time or str(raw_time).strip().lower() in ["string", "null", "none", ""]:
        raw_time = now_ist.strftime("%H:%M")

    try:
        dt = date_parser.parse(f"{raw_date} {raw_time}", dayfirst=True)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date/time format: '{raw_date} {raw_time}'. Use DD/MM/YYYY and HH:mm."
        )

    utc_hours = dt.hour + (dt.minute / 60.0) + (dt.second / 3600.0) - req.tz
    jd_ut = swe.julday(dt.year, dt.month, dt.day, utc_hours)
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0.0, 0.0)
    ayanamsa = swe.get_ayanamsa_ut(jd_ut)

    # Ascendant locked directly to 249 Table
    seed_entry = KP_249_TABLE[req.seed - 1]
    asc_sidereal = seed_entry["start_lon"]
    asc_tropical = (asc_sidereal + ayanamsa) % 360.0

    # Derive RAMC for Seed Ascendant at Location
    eps_res, _ = swe.calc_ut(jd_ut, swe.ECL_NUT, 0)
    eps = eps_res[0]

    rad = math.radians
    deg = math.degrees
    sin_d = math.sin(rad(eps)) * math.sin(rad(asc_tropical))
    decl = math.asin(sin_d)
    ra = deg(math.atan2(math.cos(rad(eps)) * math.sin(rad(asc_tropical)), math.cos(rad(asc_tropical)))) % 360.0
    sin_ad = math.tan(decl) * math.tan(rad(req.lat))
    sin_ad = max(-1.0, min(1.0, sin_ad))
    ad = deg(math.asin(sin_ad))
    armc = (ra - ad - 90.0) % 360.0

    # Placidus Houses from ARMC
    cusps_trop, _ = swe.houses_armc(armc, req.lat, eps, b'P')
    cusps = {}
    for i in range(1, 13):
        if i == 1:
            # Enforce 100% fidelity with the authentic KP 249 Seed Table
            cusps[1] = {
                "house": 1,
                "longitude": round(asc_sidereal, 4),
                "sign": seed_entry["sign"],
                "degree": to_dms(asc_sidereal % 30.0),
                "sign_lord": seed_entry["sign_lord"],
                "star_lord": seed_entry["star_lord"],
                "sub_lord": seed_entry["sub_lord"]
            }
        else:
            deg_trop = get_cusp_degree(cusps_trop, i)
            sid_c = (deg_trop - ayanamsa) % 360.0
            coords = get_kp_coordinates(sid_c)
            cusps[i] = {
                "house": i,
                "longitude": round(sid_c, 4),
                "sign": coords["sign"],
                "degree": coords["degree_in_sign"],
                "sign_lord": coords["sign_lord"],
                "star_lord": coords["star_lord"],
                "sub_lord": coords["sub_lord"]
            }

    # Planetary Coordinates at the Specified Query Moment
    PLANET_MAP = [
        ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS),
        ("Mercury", swe.MERCURY), ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
        ("Saturn", swe.SATURN), ("Rahu", swe.MEAN_NODE)
    ]
    planets = {}
    for name, pid in PLANET_MAP:
        res, _ = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED)
        lon = res[0]
        coords = get_kp_coordinates(lon)
        planets[name] = {
            "longitude": round(lon, 4),
            "sign": coords["sign"],
            "degree": coords["degree_in_sign"],
            "sign_lord": coords["sign_lord"],
            "star_lord": coords["star_lord"],
            "sub_lord": coords["sub_lord"],
            "sub_sub_lord": coords["sub_sub_lord"],
            "retrograde": res[3] < 0
        }

    ketu_lon = (planets["Rahu"]["longitude"] + 180.0) % 360.0
    k_coords = get_kp_coordinates(ketu_lon)
    planets["Ketu"] = {
        "longitude": round(ketu_lon, 4),
        "sign": k_coords["sign"],
        "degree": k_coords["degree_in_sign"],
        "sign_lord": k_coords["sign_lord"],
        "star_lord": k_coords["star_lord"],
        "sub_lord": k_coords["sub_lord"],
        "sub_sub_lord": k_coords["sub_sub_lord"],
        "retrograde": True
    }

    significators = calculate_4step_significators(planets, cusps)

    return {
        "status": 200,
        "calculation_type": "KP Horary (1-249)",
        "seed_number": req.seed,
        "query_details": {
            "date": dt.strftime("%d/%m/%Y"),
            "time": dt.strftime("%H:%M"),
            "city": req.city,
            "lat": req.lat,
            "lon": req.lon,
            "tz": req.tz
        },
        "planets": planets,
        "houses": cusps,
        "four_step_significators": significators
    }
