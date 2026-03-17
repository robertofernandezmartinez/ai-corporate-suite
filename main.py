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
# Build: 2.0.2 - Fixed Path for bot/ folder
# Architecture: FastAPI + Background Telegram Thread

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
    1. Spawns Telegram Bot in a background thread looking into bot/ folder.
    2. Initializes ML Engines for Stockout, SmartPort, and NASA RUL.
    """
    global stockout_engine, smartport_engine, nasa_engine

    # --- 1. TELEGRAM BOT BACKGROUND SERVICE ---
    def run_bot():
        # Delay to ensure Railway network stack is fully ready
        time.sleep(5)
        try:
            # Ensure the root and the bot folder are in sys.path
            base_path = os.path.dirname(os.path.abspath(__file__))
            if base_path not in sys.path:
                sys.path.append(base_path)
            
            # Diagnostic: check if the bot directory exists
            bot_folder = os.path.join(base_path, "bot")
            if os.path.exists(bot_folder):
                logger.info(f"📂 Bot folder detected. Contents: {os.listdir(bot_folder)}")
            else:
                logger.error(f"❌ CRITICAL: Folder 'bot/' NOT FOUND in {base_path}")
                return

            # IMPORT FROM THE SUBFOLDER
            from bot.telegram_bot import bot as telegram_instance
            logger.info("🤖 Bot module imported successfully from bot/ folder.")
            
            # Clear webhooks to allow clean Polling
            telegram_instance.remove_webhook()
            logger.info("🤖 Webhook cleared. Starting infinity polling...")
            
            # Start polling
            telegram_instance.infinity_polling(
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)