from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
import threading
import sys

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
    Initialize all ML engines and Telegram Bot on API startup.
    If one fails, the API still boots, but that component will remain offline.
    """
    global stockout_engine, smartport_engine, nasa_engine

    # --- 1. Load Telegram Bot (Background Service) ---
    try:
        # Ensure current directory is in sys.path to avoid ModuleNotFoundError
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)

        # Dynamic import of the bot module
        import telegram_bot
        bot = telegram_bot.bot
        
        def run_bot():
            logger.info("🤖 Telegram Bot: Starting polling...")
            # skip_pending=True prevents the bot from answering old messages on startup
            bot.infinity_polling(skip_pending=True, timeout=20)

        # Start the bot in a separate thread (daemon=True to exit with main app)
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("✅ Telegram Bot: BACKGROUND SERVICE ONLINE")
    except Exception as e:
        logger.error(f"⚠️ Telegram Bot Load Failed: {e}")

    # --- 2. Load Stockout Engine ---
    try:
        from core.stockout_predictor import StockoutPredictor
        stockout_engine = StockoutPredictor()
        print("✅ Stockout Engine: ONLINE")
    except Exception as e:
        print(f"⚠️ Stockout Load Failed: {e}")

    # --- 3. Load SmartPort Engine ---
    try:
        from core.smartport_predictor import SmartPortPredictor
        smartport_engine = SmartPortPredictor()
        print("✅ SmartPort Engine: ONLINE")
    except Exception as e:
        print(f"⚠️ SmartPort Load Failed: {e}")

    # --- 4. Load NASA RUL Engine ---
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
    if not smartport_engine:
        raise HTTPException(status_code=500, detail="SmartPort engine not initialized")

    try:
        print(f"📥 Processing SmartPort: {file.filename}")
        result = await smartport_engine.predict_from_file(file)
        # Debug Supabase connectivity
        print(f"SMARTPORT: supabase client present? {bool(getattr(smartport_engine, 'supabase', None))}")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"SmartPort Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT: NASA RUL (Engine Health) ---
@app.post("/nasa/upload", tags=["Predictive Maintenance"])
async def upload_nasa(file: UploadFile = File(...)):
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
    # Local development execution
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)