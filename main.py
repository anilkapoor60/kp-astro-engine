import math
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import swisseph as swe

app = FastAPI(
    title="KP Stellar Astrology Engine",
    description="High-precision KP calculations using Swiss Ephemeris",
    version="1.0.0",
)

# Set KP New Ayanamsha (Krishnamurti)
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
    deg = int(degrees)
    rem = (degrees - deg) * 60.0
    minute = int(rem)
    sec = int(round((rem - minute) * 60.0))
    if sec == 60:
        sec = 0
        minute += 1
    if minute == 60:
        minute = 0
        deg += 1
    return f"{deg:02d}° {minute:02d}' {sec:02d}\""

def get_kp_coordinates(lon: float) -> Dict:
    """Calculates Sign, Sign Lord, Star, Star Lord, and Sub-Lord for any longitude."""
    lon = lon % 360.0
    sign_idx = int(lon // 30.0)
    sign_name, sign_lord = ZODIAC_SIGNS[sign_idx]
    deg_in_sign = lon - (sign_idx * 30.0)

    nak_idx = int(lon // (360.0 / 27.0))
    nak_name, star_lord = NAKSHATRAS[nak_idx]
    nak_start = nak_idx * (360.0 / 27.0)
    deg_in_nak_mins = (lon - nak_start) * 60.0

    # Calculate Sub-Lord
    start_lord_idx = DASHA_LORDS.index(star_lord)
    accum_mins = 0.0
    sub_lord = star_lord
    sub_sub_lord = star_lord

    for i in range(9):
        curr_lord = DASHA_LORDS[(start_lord_idx + i) % 9]
        span_mins = (DASHA_YEARS[(start_lord_idx + i) % 9] / TOTAL_YEARS) * NAKSHATRA_SPAN
        if accum_mins <= deg_in_nak_mins < (accum_mins + span_mins):
            sub_lord = curr_lord
            # Sub-Sub Lord
            deg_in_sub_mins = deg_in_nak_mins - accum_mins
            sub_start_idx = DASHA_LORDS.index(sub_lord)
            accum_ss_mins = 0.0
            for j in range(9):
                curr_ss_lord = DASHA_LORDS[(sub_start_idx + j) % 9]
                span_ss_mins = (DASHA_YEARS[(sub_start_idx + j) % 9] / TOTAL_YEARS) * span_mins
                if accum_ss_mins <= deg_in_sub_mins < (accum_ss_mins + span_ss_mins):
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
    """Generates the authoritative 249 Sub table of Prof. K.S. Krishnamurti."""
    table = []
    curr_lon = 0.0
    for nak_idx, (nak_name, star_lord) in enumerate(NAKSHATRAS):
        start_lord_idx = DASHA_LORDS.index(star_lord)
        for i in range(9):
            sub_lord = DASHA_LORDS[(start_lord_idx + i) % 9]
            sub_span_deg = ((DASHA_YEARS[(start_lord_idx + i) % 9] / TOTAL_YEARS) * NAKSHATRA_SPAN) / 60.0
            end_lon = curr_lon + sub_span_deg

            # Check if sub crosses a 30-degree sign boundary
            curr_sign_idx = int(curr_lon // 30.0)
            end_sign_idx = int(end_lon // 30.0)

            if curr_sign_idx != end_sign_idx and end_lon < 360.0:
                split_boundary = end_sign_idx * 30.0
                # Part 1
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": curr_lon,
                    "end_lon": split_boundary,
                    "sign": ZODIAC_SIGNS[curr_sign_idx][0],
                    "sign_lord": ZODIAC_SIGNS[curr_sign_idx][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
                # Part 2
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": split_boundary,
                    "end_lon": end_lon,
                    "sign": ZODIAC_SIGNS[end_sign_idx][0],
                    "sign_lord": ZODIAC_SIGNS[end_sign_idx][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
            else:
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": curr_lon,
                    "end_lon": end_lon,
                    "sign": ZODIAC_SIGNS[curr_sign_idx][0],
                    "sign_lord": ZODIAC_SIGNS[curr_sign_idx][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
            curr_lon = end_lon
    return table

KP_249_TABLE = build_kp_249_table()

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class NatalRequest(BaseModel):
    dob: str          # DD/MM/YYYY
    tob: str          # HH:mm
    lat: float
    lon: float
    tz: float = 5.5

class HoraryRequest(BaseModel):
    seed: int         # 1 to 249
    query_date: Optional[str] = None  # DD/MM/YYYY (defaults to now)
    query_time: Optional[str] = None  # HH:mm (defaults to now)
    lat: float = 30.9010
    lon: float = 75.8573
    tz: float = 5.5

# ==========================================
# 4-STEP SIGNIFICATORS ENGINE
# ==========================================
def calculate_4step_significators(planets: Dict, cusps: List[Dict]) -> Dict:
    """
    Evaluates 4-Step Significators:
    Level 1: Planet in the Star of an Occupant of House X
    Level 2: Planet occupying House X
    Level 3: Planet in the Star of the Lord of House X
    Level 4: Lord of House X
    """
    # 1. Determine House Occupants
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
            else:  # Spans across 360/0 boundary
                if p_lon >= c_start or p_lon < c_end:
                    house_occupants[i].append(p_name)
                    break

    # 2. House Lords
    house_lords = {i: cusps[i]["sign_lord"] for i in range(1, 13)}

    # 3. Calculate Significators per Planet
    significators = {}
    for p_name, p_data in planets.items():
        star_lord = p_data["star_lord"]
        
        # Level 1: Houses whose occupants have this planet's star lord
        l1 = [h for h, occs in house_occupants.items() if star_lord in occs]
        # Level 2: Houses occupied by this planet
        l2 = [h for h, occs in house_occupants.items() if p_name in occs]
        # Level 3: Houses whose lord is this planet's star lord
        l3 = [h for h, lord in house_lords.items() if lord == star_lord]
        # Level 4: Houses owned by this planet
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
# ENDPOINT 1: NATAL KP CALCULATION
# ==========================================
@app.post("/kp/natal")
def calculate_natal(req: NatalRequest):
    try:
        dt = datetime.strptime(f"{req.dob} {req.tob}", "%d/%m/%Y %H:%M")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Date/Time format. Use DD/MM/YYYY and HH:mm")

    utc_hours = dt.hour + (dt.minute / 60.0) - req.tz
    jd_ut = swe.julday(dt.year, dt.month, dt.day, utc_hours)
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0.0, 0.0)

    # 1. 12 House Cusps
    cusp_data, ascmc = swe.houses_ex(jd_ut, req.lat, req.lon, b'P', swe.FLG_SIDEREAL)
    cusps = {}
    for i in range(1, 13):
        coords = get_kp_coordinates(cusp_data[i])
        cusps[i] = {
            "house": i,
            "longitude": round(cusp_data[i], 4),
            "sign": coords["sign"],
            "degree": coords["degree_in_sign"],
            "sign_lord": coords["sign_lord"],
            "star_lord": coords["star_lord"],
            "sub_lord": coords["sub_lord"]
        }

    # 2. 9 Grahas
    PLANET_MAP = [
        ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS),
        ("Mercury", swe.MERCURY), ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
        ("Saturn", swe.SATURN), ("Rahu", swe.MEAN_NODE)
    ]
    planets = {}
    for name, pid in PLANET_MAP:
        res, flg = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED)
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

    # Ketu is opposite Rahu
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

    # 3. Pre-calculated 4-Step Significators
    significators = calculate_4step_significators(planets, cusps)

    return {
        "status": 200,
        "calculation_type": "KP Natal",
        "birth_details": {"dob": req.dob, "tob": req.tob, "lat": req.lat, "lon": req.lon},
        "planets": planets,
        "houses": cusps,
        "four_step_significators": significators
    }

# ==========================================
# ENDPOINT 2: KP HORARY (1-249 PRASHNA)
# ==========================================
@app.post("/kp/horary")
def calculate_horary(req: HoraryRequest):
    if not (1 <= req.seed <= 249):
        raise HTTPException(status_code=400, detail="Horary Seed Number must be between 1 and 249.")

    now = datetime.now()
    q_date = req.query_date or now.strftime("%d/%m/%Y")
    q_time = req.query_time or now.strftime("%H:%M")
    dt = datetime.strptime(f"{q_date} {q_time}", "%d/%m/%Y %H:%M")

    utc_hours = dt.hour + (dt.minute / 60.0) - req.tz
    jd_ut = swe.julday(dt.year, dt.month, dt.day, utc_hours)
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI, 0.0, 0.0)
    ayanamsa = swe.get_ayanamsa_ut(jd_ut)

    # 1. Lookup Ascendant from Seed
    seed_entry = KP_249_TABLE[req.seed - 1]
    asc_sidereal = seed_entry["start_lon"]
    asc_tropical = (asc_sidereal + ayanamsa) % 360.0

    # 2. Derive RAMC for Seed Ascendant at Query Location
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

    # 3. Calculate Placidus Houses from ARMC
    cusps_trop, _ = swe.houses_armc(armc, req.lat, eps, b'P')
    cusps = {}
    for i in range(1, 13):
        sid_c = (cusps_trop[i] - ayanamsa) % 360.0
        if i == 1:
            sid_c = asc_sidereal  # Exactly locked to the seed degree
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

    # 4. Calculate Transit Planets at Query Moment
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

    # 5. Significators
    significators = calculate_4step_significators(planets, cusps)

    return {
        "status": 200,
        "calculation_type": "KP Horary (1-249)",
        "seed_number": req.seed,
        "query_details": {"date": q_date, "time": q_time, "lat": req.lat, "lon": req.lon},
        "planets": planets,
        "houses": cusps,
        "four_step_significators": significators
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Swiss Ephemeris KP Engine"}
