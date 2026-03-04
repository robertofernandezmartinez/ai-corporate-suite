from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os

# =========================
# AI Corporate Suite (API)
# =========================
# This FastAPI service hosts 3 independent ML engines:
# - Stockout (Retail inventory risk)
# - SmartPort (Maritime risk)
# - NASA RUL (Predictive maintenance)
#
# The UI (Streamlit) should call this API via HTTP using API_BASE_URL.
# In Railway, the service is started with:
#   uvicorn main:app --host 0.0.0.0 --port $PORT
#
# Note: The __main__ block below is ONLY for local development. Railway ignores it.

app = FastAPI(
    title="AI Corporate Suite",
    version="2.0.0",
    description="Enterprise Industrial AI API",
)

# Engines initialized as None (lazy init)
stockout_engine = None
smartport_engine = None
nasa_engine = None

# Basic logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-corporate-suite-api")


@app.on_event("startup")
async def startup_event():
    """
    Initialize all ML engines on API startup.
    If one fails, the API still boots, but that engine will remain offline.
    """
    global stockout_engine, smartport_engine, nasa_engine

    # --- Load Stockout Engine ---
    try:
        from core.stockout_predictor import StockoutPredictor
        stockout_engine = StockoutPredictor()
        print("✅ Stockout Engine: ONLINE")
    except Exception as e:
        print(f"⚠️ Stockout Load Failed: {e}")

    # --- Load SmartPort Engine ---
    try:
        from core.smartport_predictor import SmartPortPredictor
        smartport_engine = SmartPortPredictor()
        print("✅ SmartPort Engine: ONLINE")
    except Exception as e:
        print(f"⚠️ SmartPort Load Failed: {e}")

    # --- Load NASA RUL Engine ---
    try:
        from core.nasa_predictor import NASAPredictor
        nasa_engine = NASAPredictor()
        print("✅ NASA RUL Engine: ONLINE")
    except Exception as e:
        print(f"⚠️ NASA Load Failed: {e}")


# CORS middleware (demo-friendly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """
    Basic status endpoint to confirm the API is online and which engines are loaded.
    """
    return {
        "status": "Online",
        "suite": "AI Corporate Suite",
        "suite_version": "2.0.0",
        "active_engines": {
            "stockout": stockout_engine is not None,
            "smartport": smartport_engine is not None,
            "nasa": nasa_engine is not None,
        },
    }


# --- ENDPOINT: STOCKOUT RISK ---
@app.post("/stockout/upload", tags=["Inventory Management"])
async def upload_stockout(file: UploadFile = File(...)):
    """
    Upload a CSV file and run stockout risk predictions.
    """
    if not stockout_engine:
        raise HTTPException(status_code=500, detail="Stockout engine not initialized")

    try:
        print(f"📥 Processing Stockout: {file.filename}")
        result = await stockout_engine.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Stockout Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT: SMARTPORT DELAYS / RISK ---
@app.post("/smartport/upload", tags=["Maritime Logistics"])
async def upload_smartport(file: UploadFile = File(...)):
    """
    Upload a CSV file and run SmartPort risk predictions.
    """
    if not smartport_engine:
        raise HTTPException(status_code=500, detail="SmartPort engine not initialized")

    try:
        print(f"📥 Processing SmartPort: {file.filename}")

        # Run inference
        result = await smartport_engine.predict_from_file(file)

        # DEBUG: confirm whether Supabase client exists inside the SmartPort engine.
        # If this prints False, the engine will not persist rows to Supabase.
        print(f"SMARTPORT: supabase client present? {bool(getattr(smartport_engine, 'supabase', None))}")

        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"SmartPort Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT: NASA RUL (Engine Health) ---
@app.post("/nasa/upload", tags=["Predictive Maintenance"])
async def upload_nasa(file: UploadFile = File(...)):
    """
    Upload a CSV file and run NASA Remaining Useful Life predictions.
    """
    if not nasa_engine:
        raise HTTPException(status_code=500, detail="NASA engine not initialized")

    try:
        print(f"📥 Processing NASA RUL: {file.filename}")
        result = await nasa_engine.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"NASA Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Local development only (Railway ignores this block).
    # Railway uses: uvicorn main:app --host 0.0.0.0 --port $PORT
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)