from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

app = FastAPI(
    title="AI Corporate Suite",
    version="2.0.0",
    description="Enterprise Industrial AI API"
)

# 1) Engines initialized as None (lazy initialization pattern)
stockout_engine = None
smartport_engine = None
nasa_engine = None


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


# CORS middleware (allowing all origins/methods/headers for simplicity in demo mode)
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
        "status": "online",
        "suite_version": "2.0.0",
        "active_engines": {
            "stockout": stockout_engine is not None,
            "smartport": smartport_engine is not None,
            "nasa": nasa_engine is not None
        }
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
        logging.error(f"Stockout Error: {e}")
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
        result = await smartport_engine.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        logging.error(f"SmartPort Error: {e}")
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
        logging.error(f"NASA Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Standard local port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)