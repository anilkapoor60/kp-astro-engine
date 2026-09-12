import os
import math
from datetime import datetime, timedelta
import pytz
from fastapi import FastAPI, Query, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import swisseph as swe

app = FastAPI(title="AskRajni KP Astro Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

VALID_API_KEYS = {
    os.environ.get("MASTER_API_KEY", "askrajni_master_secret_999"): "AskRajni Node Backend"
}

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key in VALID_API_KEYS:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Access Denied: Invalid API Key."
    )

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
DASHA_SEQ = [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]
DAY_LORDS_PLANET = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_PLANET_MAP = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]

def build_249_table():
    subs = []
    current_deg = 0.0
    seed_cnt = 1
    
    for nak in range(27):
        star_idx = nak % 9
        star_lord = DASHA_SEQ[star_idx][0]
        
        for i in range(9):
            sub_idx = (star_idx + i) % 9
            sub_lord, years = DASHA_SEQ[sub_idx]
            span = (years / 120.0) * (40.0 / 3.0) 
            
            sign_idx = int(current_deg / 30.0)
            if sign_idx > 11: sign_idx = 11
            sign_end = float((sign_idx + 1) * 30)
            
            next_deg = current_deg + span
            if abs(next_deg - sign_end) < 0.0001:
                next_deg = sign_end
                
            if next_deg > sign_end:
                subs.append({"seed": seed_cnt, "start": current_deg, "end": sign_end, "star": star_lord, "sub": sub_lord})
                seed_cnt += 1
                subs.append({"seed": seed_cnt, "start": sign_end, "end": next_deg, "star": star_lord, "sub": sub_lord})
                seed_cnt += 1
                current_deg = next_deg
            else:
                subs.append({"seed": seed_cnt, "start": current_deg, "end": next_deg, "star": star_lord, "sub": sub_lord})
                seed_cnt += 1
                current_deg = next_deg
    return subs

KP_TABLE = build_249_table()

def get_lords(deg):
    deg = deg % 360
    for s in KP_TABLE:
        if s["start"] - 0.0001 <= deg <= s["end"] + 0.0001:
            star_lord = s["star"]
            sub_lord = s["sub"]
            sub_lord_idx = next(i for i, v in enumerate(DASHA_SEQ) if v[0] == sub_lord)
            sub_span = s["end"] - s["start"]
            current_ssl_start = s["start"]
            
            for i in range(9):
                ssl_idx = (sub_lord_idx + i) % 9
                ssl_name, years = DASHA_SEQ[ssl_idx]
                ssl_span = sub_span * (years / 120.0)
                
                if current_ssl_start - 0.0001 <= deg <= current_ssl_start + ssl_span + 0.0001:
                    return star_lord, sub_lord, ssl_name
                current_ssl_start += ssl_span
            return star_lord, sub_lord, sub_lord
    return "Ketu", "Ketu", "Ketu"
    
def format_deg(deg):
    deg = deg % 360
    d = int(deg) % 30
    m_float = (deg - int(deg)) * 60
    m = int(m_float)
    s = round((m_float - m) * 60, 2)
    
    # Format cleanly as 25°50'37.74"
    s_str = f"{s:05.2f}" if s >= 10 else f"0{s:04.2f}"
    return f"{d:02d}°{m:02d}'{s_str}\""

def compute_kp_significators(planets_data, cusps_data):
    # Mapping planets to their occupied houses based on sign/cusp boundaries
    sig_matrix = {}
    for house in cusps_data:
        h_num = house["house"]
        h_sign = house["sign"]
        for p in planets_data:
            if p["sign"] == h_sign:
                if p["name"] not in sig_matrix: sig_matrix[p["name"]] = {"A": [], "B": [], "C": [], "D": []}
                if h_num not in sig_matrix[p["name"]]["B"]:
                    sig_matrix[p["name"]]["B"].append(h_num) # Level B: Occupant
                    
    # Level A, C, D mapping logic can be appended here and passed to Node.js
    return sig_matrix
    
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Swiss Ephemeris 249-Engine Awake"}

class HoraryPayload(BaseModel):
    seed: int
    rotate_to_house: int = 1
    city: str = "Ludhiana"
    lat: float = 30.9010
    lon: float = 75.8573
    tz: float = 5.5
    year: int = None
    month: int = None
    day: int = None
    hour: int = None
    min: int = None
    sec: int = None
    ayanamsa: int = 4
    system: str = "sidereal"
    ayanamsa_name: str = "KP"

@app.post("/kp/horary")
def generate_kp_horary_post(payload: HoraryPayload, api_key: str = Security(verify_api_key)):
    if payload.year is not None:
        local_dt = datetime(payload.year, payload.month, payload.day, payload.hour, payload.min, payload.sec)
        utc_dt = local_dt - timedelta(hours=payload.tz)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
        ist_now = local_dt
    else:
        now = datetime.utcnow()
        ist_now = datetime.now(pytz.timezone('Asia/Kolkata'))
        jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0 + now.second/3600.0)
        
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    
    seed_data = KP_TABLE[payload.seed - 1]
    
    SWE_PLANETS = [swe.SUN, swe.MOON, swe.MARS, swe.MERCURY, swe.JUPITER, swe.VENUS, swe.SATURN, swe.MEAN_NODE]
    PLANET_NAMES = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu"]
    
    planets_data = []
    d9_planets_data = []
    moon_sign_lord = ""
    moon_star_lord = ""
    
    for i, p in enumerate(SWE_PLANETS):
        pos, _ = swe.calc_ut(jd, p, flags)
        deg = pos[0]
        sign_idx = int(deg / 30.0)
        star, sub, sub_sub = get_lords(deg)
        
        d9_deg = (deg * 9.0) % 360.0
        d9_sign_idx = int(d9_deg / 30.0)
        
        if PLANET_NAMES[i] == "Moon":
            moon_sign_lord = SIGN_LORDS[sign_idx]
            moon_star_lord = star

        planets_data.append({
            "name": PLANET_NAMES[i], "sign": SIGNS[sign_idx], "degree": format_deg(deg),
            "star_lord": star, "sub_lord": sub, "sub_sub": sub_sub
        })
        d9_planets_data.append({"name": PLANET_NAMES[i], "sign": SIGNS[d9_sign_idx]})
        
    rahu_raw_deg = swe.calc_ut(jd, swe.MEAN_NODE, flags)[0][0]
    ketu_raw_deg = (rahu_raw_deg + 180.0) % 360
    k_sign_idx = int(ketu_raw_deg / 30.0)
    k_star, k_sub, k_sub_sub = get_lords(ketu_raw_deg)
    
    d9_k_deg = (ketu_raw_deg * 9.0) % 360.0
    d9_k_sign_idx = int(d9_k_deg / 30.0)
    
    planets_data.append({
        "name": "Ketu", "sign": SIGNS[k_sign_idx], "degree": format_deg(ketu_raw_deg),
        "star_lord": k_star, "sub_lord": k_sub, "sub_sub": k_sub_sub
    })
    d9_planets_data.append({"name": "Ketu", "sign": SIGNS[d9_k_sign_idx]})

    target_asc = seed_data["start"] + 0.0001 
    jd_guess = jd
    
    for _ in range(15):
        _, live_ascmc = swe.houses_ex(jd_guess, payload.lat, payload.lon, b'P', flags)
        current_asc = live_ascmc[0]  
        diff = target_asc - current_asc
        if diff > 180: diff -= 360
        elif diff < -180: diff += 360
        if abs(diff) < 0.0001: break
        jd_guess += diff / 360.0
    
    true_horary_cusps, _ = swe.houses_ex(jd_guess, payload.lat, payload.lon, b'P', flags)
    
    base_cusps = []
    # FIX: Corrected 0-indexed house loop (0 to 11 for houses 1 to 12)
    for i in range(12):
        cusp_deg = true_horary_cusps[i]
        sign_idx = int(cusp_deg / 30.0)
        c_star, c_sub, c_sub_sub = get_lords(cusp_deg)
        base_cusps.append({
            "house": i + 1, "sign": SIGNS[sign_idx], "degree": format_deg(cusp_deg),
            "degree_raw": cusp_deg, "star_lord": c_star, "sub_lord": c_sub, "sub_sub": c_sub_sub
        })
        
    rotated_cusps = []
    rotation_index = payload.rotate_to_house - 1 
    for i in range(12):
        target_index = (rotation_index + i) % 12
        original_cusp = base_cusps[target_index].copy()
        original_cusp["house"] = i + 1 
        rotated_cusps.append(original_cusp)

    d9_asc_deg = (rotated_cusps[0].get("degree_raw", target_asc * 9.0)) % 360.0
    d9_asc_sign = SIGNS[int(d9_asc_deg / 30.0)]
    
    _, live_transit_ascmc = swe.houses_ex(jd, payload.lat, payload.lon, b'P', flags)
    transit_asc_sign = SIGNS[int(live_transit_ascmc[0] / 30.0)]

    day_idx = ist_now.weekday()
    day_lord = DAY_PLANET_MAP[day_idx]
    
    ruling_planets_data = {
        "day_lord": day_lord,
        "asc_sign_lord": SIGN_LORDS[int(target_asc / 30.0)],
        "asc_star_lord": seed_data["star"],
        "asc_sub_lord": seed_data["sub"],
        "moon_sign_lord": moon_sign_lord,
        "moon_star_lord": moon_star_lord,
        "rahu_represents": SIGN_LORDS[int(rahu_raw_deg / 30.0)], 
        "ketu_represents": SIGN_LORDS[int(ketu_raw_deg / 30.0)]
    }

    return {
        "seed_used": payload.seed,
        "rotation_applied": payload.rotate_to_house,
        "transit_asc_sign": transit_asc_sign,
        "d9_asc_sign": d9_asc_sign,
        "planets": planets_data,
        "d9_planets": d9_planets_data,
        "cusps": rotated_cusps,
        "houses": rotated_cusps, 
        "ruling_planets": ruling_planets_data
    }

@app.get("/api/horary")
def generate_kp_horary_get(seed: int = Query(..., ge=1, le=249), rotate: int = Query(1, ge=1, le=12), api_key: str = Security(verify_api_key)):
    req = HoraryPayload(seed=seed, rotate_to_house=rotate)
    return generate_kp_horary_post(req, api_key)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
