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
        status_code=status.HTTP_403_FORBIDDEN if hasattr(status, 'HTTP_403_FORBIDDEN') else 403, 
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
    s_str = f"{s:05.2f}" if s >= 10 else f"0{s:04.2f}"
    return f"{d:02d}°{m:02d}'{s_str}\""

def get_placidus_house(deg, cusps_data):
    deg = deg % 360
    sorted_cusps = sorted(cusps_data, key=lambda x: x["house"])
    for i in range(12):
        curr = sorted_cusps[i]
        nxt = sorted_cusps[(i + 1) % 12]
        start = curr["degree_raw"]
        end = nxt["degree_raw"]
        if start <= end:
            if start <= deg < end:
                return curr["house"]
        else:
            if deg >= start or deg < end:
                return curr["house"]
    return 1

def compute_kp_significators(planets_data, cusps_data):
    # Mapping exact Placidus house occupancy and lordship per KP rules
    planet_map = {p["name"]: p for p in planets_data}
    sig_matrix = {p["name"]: {"A": [], "B": [], "C": [], "D": []} for p in planets_data}
    
    house_lords = {}
    house_occupants = {i: [] for i in range(1, 13)}
    
    for cusp in cusps_data:
        h_num = cusp["house"]
        house_lords[h_num] = cusp.get("sign_lord", SIGN_LORDS[SIGNS.index(cusp["sign"])])

    for p in planets_data:
        h_occ = get_placidus_house(p["degree_raw"], cusps_data)
        p["occupies_house"] = h_occ
        if p["name"] not in house_occupants[h_occ]:
            house_occupants[h_occ].append(p["name"])

    # Helper to resolve node proxy actors (Rahu and Ketu act as agents for conjunctions, sign dispositor, star lord)
    def get_effective_planets_for_star(star_lord_name):
        actors = [star_lord_name]
        if star_lord_name in ["Rahu", "Ketu"]:
            node_p = planet_map.get(star_lord_name)
            if node_p:
                # Add sign dispositor
                dispositor = node_p["sign_lord"]
                if dispositor not in actors: actors.append(dispositor)
                # Add planets in star of node
                for pl in planets_data:
                    if pl["star_lord"] == star_lord_name and pl["name"] not in actors:
                        actors.append(pl["name"])
        return actors

    for h_num in range(1, 13):
        occ_list = house_occupants[h_num]
        
        # Level B: House Occupants
        for occ in occ_list:
            if h_num not in sig_matrix[occ]["B"]:
                sig_matrix[occ]["B"].append(h_num)
            # If occupant is node, add conjunct planets
            if occ in ["Rahu", "Ketu"]:
                for p in planets_data:
                    if p["occupies_house"] == h_num and p["name"] != occ:
                        if h_num not in sig_matrix[p["name"]]["B"]:
                            sig_matrix[p["name"]]["B"].append(h_num)

        # Level A: Planets in the star of occupant(s)
        for occ in occ_list:
            effective_occupants = get_effective_planets_for_star(occ)
            for p in planets_data:
                if p["star_lord"] in effective_occupants:
                    if h_num not in sig_matrix[p["name"]]["A"]:
                        sig_matrix[p["name"]]["A"].append(h_num)

        # Level D: House Cusp Lord (Sign Lord)
        h_lord = house_lords.get(h_num)
        if h_lord and h_lord in sig_matrix and h_lord not in ["Rahu", "Ketu"]:
            if h_num not in sig_matrix[h_lord]["D"]:
                sig_matrix[h_lord]["D"].append(h_num)

        # Level C: Planets in the star of House Lord
        if h_lord:
            effective_lords = get_effective_planets_for_star(h_lord)
            for p in planets_data:
                if p["star_lord"] in effective_lords:
                    if h_num not in sig_matrix[p["name"]]["C"]:
                        sig_matrix[p["name"]]["C"].append(h_num)

    for p_name in sig_matrix:
        for lvl in ["A", "B", "C", "D"]:
            sig_matrix[p_name][lvl] = sorted(list(set(sig_matrix[p_name][lvl])))

    return sig_matrix

def get_planet_signified_houses(planet_name, planets_data, cusps_data):
    occupied = []
    owned = []
    for cusp in cusps_data:
        h_num = cusp["house"]
        s_lord = cusp.get("sign_lord", SIGN_LORDS[SIGNS.index(cusp["sign"])])
        if s_lord == planet_name and h_num not in owned:
            owned.append(h_num)
            
    for p in planets_data:
        if p["name"] == planet_name:
            h_occ = get_placidus_house(p["degree_raw"], cusps_data)
            if h_occ not in occupied:
                occupied.append(h_occ)
                
    # Handle Rahu/Ketu proxy extension for Nadi
    if planet_name in ["Rahu", "Ketu"]:
        node_p = next((p for p in planets_data if p["name"] == planet_name), None)
        if node_p:
            disp = node_p["sign_lord"]
            for cusp in cusps_data:
                if cusp.get("sign_lord") == disp and cusp["house"] not in owned:
                    owned.append(cusp["house"])
            for p in planets_data:
                if p["star_lord"] == planet_name:
                    h_occ_sub = get_placidus_house(p["degree_raw"], cusps_data)
                    if h_occ_sub not in occupied:
                        occupied.append(h_occ_sub)

    return sorted(list(set(occupied + owned)))

def compute_nadi_significators(planets_data, cusps_data):
    nadi_matrix = {}
    for p in planets_data:
        p_name = p["name"]
        sign_lord = p["sign_lord"]
        
        # Exact house occupancy and ownership for the planet itself
        p_occupancy = [get_placidus_house(p["degree_raw"], cusps_data)]
        p_ownership = [c["house"] for c in cusps_data if c.get("sign_lord") == p_name]
        
        stl = p["star_lord"]
        sub = p["sub_lord"]
        
        stl_houses = get_planet_signified_houses(stl, planets_data, cusps_data)
        sub_houses = get_planet_signified_houses(sub, planets_data, cusps_data)
        
        nadi_matrix[p_name] = {
            "sign_lord": sign_lord,
            "occupancy": sorted(list(set(p_occupancy))),
            "ownership": sorted(list(set(p_ownership))),
            "star_lord": stl,
            "star_lord_houses": stl_houses,
            "sub_lord": sub,
            "sub_lord_houses": sub_houses
        }
    return nadi_matrix

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
        sign_lord = SIGN_LORDS[sign_idx]
        star, sub, sub_sub = get_lords(deg)
        
        d9_deg = (deg * 9.0) % 360.0
        d9_sign_idx = int(d9_deg / 30.0)
        
        if PLANET_NAMES[i] == "Moon":
            moon_sign_lord = sign_lord
            moon_star_lord = star

        planets_data.append({
            "name": PLANET_NAMES[i], "sign": SIGNS[sign_idx], "degree": format_deg(deg),
            "degree_raw": deg, "sign_lord": sign_lord, "star_lord": star, "sub_lord": sub, "sub_sub": sub_sub
        })
        d9_planets_data.append({"name": PLANET_NAMES[i], "sign": SIGNS[d9_sign_idx]})
        
    rahu_raw_deg = swe.calc_ut(jd, swe.MEAN_NODE, flags)[0][0]
    ketu_raw_deg = (rahu_raw_deg + 180.0) % 360
    k_sign_idx = int(ketu_raw_deg / 30.0)
    k_sign_lord = SIGN_LORDS[k_sign_idx]
    k_star, k_sub, k_sub_sub = get_lords(ketu_raw_deg)
    
    d9_k_deg = (ketu_raw_deg * 9.0) % 360.0
    d9_k_sign_idx = int(d9_k_deg / 30.0)
    
    planets_data.append({
        "name": "Ketu", "sign": SIGNS[k_sign_idx], "degree": format_deg(ketu_raw_deg),
        "degree_raw": ketu_raw_deg, "sign_lord": k_sign_lord, "star_lord": k_star, "sub_lord": k_sub, "sub_sub": k_sub_sub
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
    for i in range(12):
        cusp_deg = true_horary_cusps[i]
        sign_idx = int(cusp_deg / 30.0)
        c_star, c_sub, c_sub_sub = get_lords(cusp_deg)
        base_cusps.append({
            "house": i + 1, "sign": SIGNS[sign_idx], "degree": format_deg(cusp_deg),
            "degree_raw": cusp_deg, "sign_lord": SIGN_LORDS[sign_idx],
            "star_lord": c_star, "sub_lord": c_sub, "sub_sub": c_sub_sub
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
    moon_sub_lord = next((p["sub_lord"] for p in planets_data if p["name"] == "Moon"), "")
    asc_sub_lord = seed_data["sub"]
    
    ruling_planets_data = {
        "day_lord": day_lord,
        "asc_sign_lord": SIGN_LORDS[int(target_asc / 30.0)],
        "asc_star_lord": seed_data["star"],
        "asc_sub_lord": asc_sub_lord,
        "moon_sign_lord": moon_sign_lord,
        "moon_star_lord": moon_star_lord,
        "moon_sub_lord": moon_sub_lord,
        "rahu_represents": SIGN_LORDS[int(rahu_raw_deg / 30.0)], 
        "ketu_represents": SIGN_LORDS[int(ketu_raw_deg / 30.0)]
    }

    significators_matrix = compute_kp_significators(planets_data, rotated_cusps)
    nadi_matrix = compute_nadi_significators(planets_data, rotated_cusps)

    return {
        "seed_used": payload.seed,
        "rotation_applied": payload.rotate_to_house,
        "transit_asc_sign": transit_asc_sign,
        "d9_asc_sign": d9_asc_sign,
        "planets": planets_data,
        "d9_planets": d9_planets_data,
        "cusps": rotated_cusps,
        "houses": rotated_cusps, 
        "ruling_planets": ruling_planets_data,
        "significators": significators_matrix,
        "nadi_significators": nadi_matrix
    }

@app.get("/api/horary")
def generate_kp_horary_get(seed: int = Query(..., ge=1, le=249), rotate: int = Query(1, ge=1, le=12), api_key: str = Security(verify_api_key)):
    req = HoraryPayload(seed=seed, rotate_to_house=rotate)
    return generate_kp_horary_post(req, api_key)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
