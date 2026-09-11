import os
from fastapi import FastAPI, Query, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import pytz
import swisseph as swe

app = FastAPI(title="AskRajni KP Astro Engine")

# Allow Node.js backend to communicate with this Python engine
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

# This is your master vault. You can add new keys here if you want to sell access to your API later!
VALID_API_KEYS = {
    os.environ.get("MASTER_API_KEY", "askrajni_master_secret_999"): "AskRajni Node Backend",
    "demo_client_key_001": "External Client 1 (Example)"
}

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key in VALID_API_KEYS:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Access Denied: Invalid or missing API Key. Please contact askrajnioffice@gmail.com to request API access."
    )

# ==========================================
# 2. PUBLIC HEALTH CHECK (KEEPS RENDER AWAKE)
# ==========================================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Swiss Ephemeris Engine is Awake"}

@app.get("/")
def root():
    return {"message": "AskRajni KP Engine API is running. Visit /docs for the manual."}

# ==========================================
# 3. THE SECURED HORARY (PRASHNA) GENERATOR
# ==========================================
# Notice the new 'api_key' dependency injected into the route!
@app.get("/api/horary")
def generate_kp_horary(
    seed: int = Query(..., ge=1, le=249, description="KP Horary Seed (1-249)"),
    rotate: int = Query(1, ge=1, le=12, description="Target House to Rotate to Ascendant"),
    api_key: str = Security(verify_api_key)
):
    # Set time to current IST for live Prashna transit positions
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # ---------------------------------------------------------
    # MOCK/PLACEHOLDER MATH
    # ---------------------------------------------------------
    planets_data = [
        {"name": "Sun", "sign": "Leo", "degree": "24°18'", "star_lord": "Ven", "sub_lord": "Mer", "sub_sub": "Jup"},
        {"name": "Moon", "sign": "Cancer", "degree": "12°44'", "star_lord": "Sat", "sub_lord": "Mar", "sub_sub": "Ven"},
        {"name": "Mars", "sign": "Gemini", "degree": "05°11'", "star_lord": "Mar", "sub_lord": "Sun", "sub_sub": "Sat"},
        {"name": "Mercury", "sign": "Virgo", "degree": "18°02'", "star_lord": "Moon", "sub_lord": "Rahu", "sub_sub": "Mer"},
        {"name": "Jupiter", "sign": "Taurus", "degree": "21°39'", "star_lord": "Moon", "sub_lord": "Ven", "sub_sub": "Sun"},
        {"name": "Venus", "sign": "Libra", "degree": "07°55'", "star_lord": "Rahu", "sub_lord": "Rahu", "sub_sub": "Mar"},
        {"name": "Saturn (R)", "sign": "Aquarius", "degree": "19°31'", "star_lord": "Rahu", "sub_lord": "Mar", "sub_sub": "Jup"},
        {"name": "Rahu (Mean)", "sign": "Pisces", "degree": "14°08'", "star_lord": "Sat", "sub_lord": "Rahu", "sub_sub": "Ven"},
        {"name": "Ketu (Mean)", "sign": "Virgo", "degree": "14°08'", "star_lord": "Moon", "sub_lord": "Jup", "sub_sub": "Sat"}
    ]

    base_cusps = [
        {"house": 1, "sign": "Aries", "degree": "15°00'", "star_lord": "Ven", "sub_lord": "Mer", "sub_sub": "Jup"},
        {"house": 2, "sign": "Taurus", "degree": "15°00'", "star_lord": "Sun", "sub_lord": "Ven", "sub_sub": "Sat"},
        {"house": 3, "sign": "Gemini", "degree": "15°00'", "star_lord": "Moon", "sub_lord": "Mar", "sub_sub": "Rahu"},
        {"house": 4, "sign": "Cancer", "degree": "15°00'", "star_lord": "Mar", "sub_lord": "Jup", "sub_sub": "Mer"},
        {"house": 5, "sign": "Leo", "degree": "15°00'", "star_lord": "Rahu", "sub_lord": "Sat", "sub_sub": "Ven"},
        {"house": 6, "sign": "Virgo", "degree": "15°00'", "star_lord": "Jup", "sub_lord": "Mer", "sub_sub": "Sun"},
        {"house": 7, "sign": "Libra", "degree": "15°00'", "star_lord": "Sat", "sub_lord": "Ven", "sub_sub": "Mar"},
        {"house": 8, "sign": "Scorpio", "degree": "15°00'", "star_lord": "Mer", "sub_lord": "Mar", "sub_sub": "Jup"},
        {"house": 9, "sign": "Sagittarius", "degree": "15°00'", "star_lord": "Ketu", "sub_lord": "Jup", "sub_sub": "Sat"},
        {"house": 10, "sign": "Capricorn", "degree": "15°00'", "star_lord": "Ven", "sub_lord": "Sat", "sub_sub": "Rahu"},
        {"house": 11, "sign": "Aquarius", "degree": "15°00'", "star_lord": "Sun", "sub_lord": "Sat", "sub_sub": "Mer"},
        {"house": 12, "sign": "Pisces", "degree": "15°00'", "star_lord": "Moon", "sub_lord": "Jup", "sub_sub": "Ven"}
    ]

    # ---------------------------------------------------------
    # BHAVAT BHAVAM: MATHEMATICAL CHART ROTATION
    # ---------------------------------------------------------
    rotated_cusps = []
    rotation_index = rotate - 1 
    
    for i in range(12):
        target_index = (rotation_index + i) % 12
        original_cusp = base_cusps[target_index].copy()
        original_cusp["house"] = i + 1 
        rotated_cusps.append(original_cusp)

    ruling_planets_data = {
        "day_lord": "Mars", "asc_sign_lord": "Mercury", "asc_star_lord": "Rahu",
        "asc_sub_lord": "Jupiter", "moon_sign_lord": "Sun", "moon_star_lord": "Venus",
        "rahu_represents": "Mercury & Jupiter (Mean)", "ketu_represents": "Mars & Venus (Mean)"
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
