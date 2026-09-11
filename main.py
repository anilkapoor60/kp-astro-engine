import os
import math
from datetime import datetime
import pytz
from fastapi import FastAPI, Query, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import swisseph as swe

app = FastAPI(title="AskRajni KP Astro Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. SECURITY & API KEY MANAGEMENT
# ==========================================
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

# ==========================================
# 2. KP ASTROLOGY CONSTANTS & 249 GENERATOR
# ==========================================
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
            span = (years / 120.0) * (40.0 / 3.0) # 13.333333 degrees per nakshatra
            
            sign_idx = int(current_deg / 30.0)
            if sign_idx > 11: sign_idx = 11
            sign_end = (sign_idx + 1) * 30.0
            
            if current_deg + span > sign_end + 0.00001:
                part1 = sign_end - current_deg
                subs.append({"seed": seed_cnt, "start": current_deg, "end": sign_end, "star": star_lord, "sub": sub_lord})
                seed_cnt += 1
                current_deg = sign_end
                
                part2 = span - part1
                subs.append({"seed": seed_cnt, "start": current_deg, "end": current_deg + part2, "star": star_lord, "sub": sub_lord})
                seed_cnt += 1
                current_deg += part2
            else:
                subs.append({"seed": seed_cnt, "start": current_deg, "end": current_deg + span, "star": star_lord, "sub": sub_lord})
                seed_cnt += 1
                current_deg += span
    return subs

# Generate the massive 249 memory table on server startup
KP_TABLE = build_249_table()

def get_lords(deg):
    deg = deg % 360
    for s in KP_TABLE:
        if s["start"] <= deg <= s["end"] + 0.00001:
            return s["star"], s["sub"]
    return "Ketu", "Ketu"
    
def format_deg(deg):
    d = int(deg) % 30
    m = int((deg - int(deg)) * 60)
    return f"{d:02d}°{m:02d}'"

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Swiss Ephemeris 249-Engine Awake"}

# ==========================================
# 3. LIVE HORARY ENGINE (REAL SWISS EPHEMERIS)
# ==========================================
@app.get("/api/horary")
def generate_kp_horary(
    seed: int = Query(..., ge=1, le=249),
    rotate: int = Query(1, ge=1, le=12),
    api_key: str = Security(verify_api_key)
):
    now = datetime.utcnow()
    ist_now = datetime.now(pytz.timezone('Asia/Kolkata'))
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0 + now.second/3600.0)
    
    seed_data = KP_TABLE[seed - 1]
    seed_asc_deg = seed_data["start"] + 0.0001 
    
    # FIX: Renamed Rahu (Mean) to strictly "Rahu"
    SWE_PLANETS = [swe.SUN, swe.MOON, swe.MARS, swe.MERCURY, swe.JUPITER, swe.VENUS, swe.SATURN, swe.MEAN_NODE]
    PLANET_NAMES = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu"]
    
    planets_data = []
    moon_sign_lord = ""
    moon_star_lord = ""
    
    for i, p in enumerate(SWE_PLANETS):
        pos, _ = swe.calc_ut(jd, p)
        deg = pos[0]
        sign_idx = int(deg / 30.0)
        star, sub = get_lords(deg)
        
        if PLANET_NAMES[i] == "Moon":
            moon_sign_lord = SIGN_LORDS[sign_idx]
            moon_star_lord = star

        planets_data.append({
            "name": PLANET_NAMES[i],
            "sign": SIGNS[sign_idx],
            "degree": format_deg(deg),
            "star_lord": star,
            "sub_lord": sub,
            "sub_sub": "Ven" 
        })
        
    rahu_raw_deg = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
    ketu_raw_deg = (rahu_raw_deg + 180.0) % 360
    k_sign_idx = int(ketu_raw_deg / 30.0)
    k_star, k_sub = get_lords(ketu_raw_deg)
    
    # FIX: Renamed Ketu (Mean) to strictly "Ketu"
    planets_data.append({
        "name": "Ketu", "sign": SIGNS[k_sign_idx], "degree": format_deg(ketu_raw_deg),
        "star_lord": k_star, "sub_lord": k_sub, "sub_sub": "Mar"
    })

    live_cusps, _ = swe.houses(jd, 30.9010, 75.8573, b'P')
    live_asc = live_cusps[0]
    
    offset = seed_asc_deg - live_asc
    
    base_cusps = []
    for i in range(12):
        shifted_deg = (live_cusps[i] + offset) % 360
        sign_idx = int(shifted_deg / 30.0)
        c_star, c_sub = get_lords(shifted_deg)
        
        base_cusps.append({
            "house": i + 1,
            "sign": SIGNS[sign_idx],
            "degree": format_deg(shifted_deg),
            "star_lord": c_star,
            "sub_lord": c_sub,
            "sub_sub": "Jup"
        })

    rotated_cusps = []
    rotation_index = rotate - 1 
    for i in range(12):
        target_index = (rotation_index + i) % 12
        original_cusp = base_cusps[target_index].copy()
        original_cusp["house"] = i + 1 
        rotated_cusps.append(original_cusp)

    day_idx = ist_now.weekday()
    day_lord = DAY_PLANET_MAP[day_idx]
    
    ruling_planets_data = {
        "day_lord": day_lord,
        "asc_sign_lord": SIGN_LORDS[int(seed_asc_deg / 30.0)],
        "asc_star_lord": seed_data["star"],
        "asc_sub_lord": seed_data["sub"],
        "moon_sign_lord": moon_sign_lord,
        "moon_star_lord": moon_star_lord,
        "rahu_represents": SIGN_LORDS[int(rahu_raw_deg / 30.0)], 
        "ketu_represents": SIGN_LORDS[int(ketu_raw_deg / 30.0)]
    }

    return {
        "seed_used": seed,
        "rotation_applied": rotate,
        "planets": planets_data,
        "cusps": rotated_cusps,
        "ruling_planets": ruling_planets_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
