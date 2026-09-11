from fastapi import FastAPI, Query
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
# 1. HEALTH CHECK (KEEPS RENDER AWAKE)
# ==========================================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Swiss Ephemeris Engine is Awake"}

@app.get("/")
def root():
    return {"message": "AskRajni KP Engine API is running. Visit /docs for the manual."}

# ==========================================
# 2. THE MASTER HORARY (PRASHNA) GENERATOR
# ==========================================
@app.get("/api/horary")
def generate_kp_horary(
    seed: int = Query(..., ge=1, le=249, description="KP Horary Seed (1-249)"),
    rotate: int = Query(1, ge=1, le=12, description="Target House to Rotate to Ascendant")
):
    # Set time to current IST for live Prashna transit positions
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # ---------------------------------------------------------
    # MOCK/PLACEHOLDER MATH (To ensure 100% uptime for Node.js)
    # ---------------------------------------------------------
    # Note: Full 1-249 KP Ayanamsa mathematical mapping goes here. 
    # For now, we generate a flawless JSON structure so the AI Drafter 
    # and PDF Generator on the Node.js side work perfectly.
    
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
    # If a user selects House 7 (Spouse), House 7 becomes House 1.
    rotated_cusps = []
    rotation_index = rotate - 1  # Arrays are 0-indexed
    
    for i in range(12):
        # Calculate the new index, wrapping around 12 using modulo
        target_index = (rotation_index + i) % 12
        original_cusp = base_cusps[target_index].copy()
        
        # Renumber the house logically (1 to 12)
        original_cusp["house"] = i + 1 
        rotated_cusps.append(original_cusp)

    ruling_planets_data = {
        "day_lord": "Mars", 
        "asc_sign_lord": "Mercury", 
        "asc_star_lord": "Rahu",
        "asc_sub_lord": "Jupiter", 
        "moon_sign_lord": "Sun", 
        "moon_star_lord": "Venus",
        "rahu_represents": "Mercury & Jupiter (Mean)", 
        "ketu_represents": "Mars & Venus (Mean)"
    }

    return {
        "seed_used": seed,
        "rotation_applied": rotate,
        "planets": planets_data,
        "cusps": rotated_cusps,
        "ruling_planets": ruling_planets_data
    }

# Entry point for local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
