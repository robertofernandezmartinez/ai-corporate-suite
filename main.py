from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
import threading
import sys
import time

# ==========================================
# AI CORPORATE SUITE - MAIN API ENTRY POINT
# ==========================================
# This service hosts 3 independent ML engines and a Telegram Bot thread.
# Architecture: FastAPI (Web/API) + Threading (Telegram Bot Polling)

app = FastAPI(
    title="AI Corporate Suite",
    version="2.0.0",
    description="Enterprise Industrial AI API",
)

# Global engines initialized as None (Lazy Load)
stockout_engine = None
smartport_engine = None
nasa_engine = None

# Logger Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("ai-corporate-suite-api")

@app.on_event("startup")
async def startup_event():
    """
    Service startup logic:
    1. Spawns Telegram Bot in a background thread.
    2. Initializes ML Engines for Stockout, SmartPort, and NASA RUL.
    """
    global stockout_engine, smartport_engine, nasa_engine

    # --- 1. TELEGRAM BOT BACKGROUND SERVICE ---
    def run_bot():
        # Delay to ensure Railway network stack is fully ready
        time.sleep(5)
        try:
            # Add current directory to sys.path to ensure module discovery
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.append(current_dir)

            import telegram_bot
            logger.info("🤖 Bot module imported successfully.")
            
            # CRITICAL: Remove existing webhooks to allow clean Polling
            telegram_bot.bot.remove_webhook()
            logger.info("🤖 Webhook cleared. Starting infinity polling...")
            
            # Start polling with long timeout for stability
            telegram_bot.bot.infinity_polling(
                skip_pending=True, 
                timeout=60, 
                long_polling_timeout=60
            )
        except Exception as e:
            logger.error(f"❌ CRITICAL BOT ERROR: {str(e)}", exc_info=True)

    # Spawn the bot thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Telegram Bot thread spawned.")

    # --- 2. STOCKOUT PREDICTOR ENGINE ---
    try:
        from core.stockout_predictor import StockoutPredictor
        stockout_engine = StockoutPredictor()
        logger.info("✅ Stockout Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ Stockout Load Failed: {e}")

    # --- 3. SMARTPORT PREDICTOR ENGINE ---
    try:
        from core.smartport_predictor import SmartPortPredictor
        smartport_engine = SmartPortPredictor()
        logger.info("✅ SmartPort Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ SmartPort Load Failed: {e}")

    # --- 4. NASA RUL PREDICTOR ENGINE ---
    try:
        from core.nasa_predictor import NASAPredictor
        nasa_engine = NASAPredictor()
        logger.info("✅ NASA RUL Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ NASA Load Failed: {e}")

# ==========================================
# MIDDLEWARE & CORS
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/")
def root():
    """System health check and engine status."""
    return {
        "status": "Online",
        "suite": "AI Corporate Suite",
        "version": "2.0.0",
        "active_engines": {
            "stockout": stockout_engine is not None,
            "smartport": smartport_engine is not None,
            "nasa": nasa_engine is not None,
        },
    }

@app.post("/stockout/upload", tags=["Inventory Management"])
async def upload_stockout(file: UploadFile = File(...)):
    if not stockout_engine:
        raise HTTPException(status_code=500, detail="Stockout engine offline")
    try:
        logger.info(f"📥 Processing Stockout: {file.filename}")
        result = await stockout_engine.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Stockout Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/smartport/upload", tags=["Maritime Logistics"])
async def upload_smartport(file: UploadFile = File(...)):
    if not smartport_engine:
        raise HTTPException(status_code=500, detail="SmartPort engine offline")
    try:
        logger.info(f"📥 Processing SmartPort: {file.filename}")
        result = await smartport_engine.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"SmartPort Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/nasa/upload", tags=["Predictive Maintenance"])
async def upload_nasa(file: UploadFile = File(...)):
    if not nasa_engine:
        raise HTTPException(status_code=500, detail="NASA engine offline")
    try:
        logger.info(f"📥 Processing NASA RUL: {file.filename}")
        result = await nasa_engine.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"NASA Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# LOCAL EXECUTION
# ==========================================
if __name__ == "__main__":
    # For local testing. Railway uses: uvicorn main:app --host 0.0.0.0 --port $PORT
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)