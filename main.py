from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
import threading
import time

# ==========================================
# AI CORPORATE SUITE - MAIN API ENTRY POINT
# ==========================================
# Build: 2.0.3 - Back to Root for Stability

app = FastAPI(
    title="AI Corporate Suite",
    version="2.0.0",
    description="Enterprise Industrial AI API",
)

# Global engines initialized as None
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
    global stockout_engine, smartport_engine, nasa_engine

    # --- 1. TELEGRAM BOT BACKGROUND SERVICE ---
    def run_bot():
        time.sleep(5) # Wait for network
        try:
            # Simple direct import since it's now in root
            import telegram_bot
            logger.info("🤖 Bot module imported successfully from root.")
            
            # Clear webhooks and start
            telegram_bot.bot.remove_webhook()
            logger.info("🤖 Webhook cleared. Starting polling...")
            telegram_bot.bot.infinity_polling(skip_pending=True, timeout=60)
        except Exception as e:
            logger.error(f"❌ CRITICAL BOT ERROR: {str(e)}", exc_info=True)

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Telegram Bot thread spawned.")

    # --- 2. LOAD ML ENGINES ---
    try:
        from core.stockout_predictor import StockoutPredictor
        stockout_engine = StockoutPredictor()
        logger.info("✅ Stockout Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ Stockout Load Failed: {e}")

    try:
        from core.smartport_predictor import SmartPortPredictor
        smartport_engine = SmartPortPredictor()
        logger.info("✅ SmartPort Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ SmartPort Load Failed: {e}")

    try:
        from core.nasa_predictor import NASAPredictor
        nasa_engine = NASAPredictor()
        logger.info("✅ NASA RUL Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ NASA Load Failed: {e}")

# ==========================================
# API ENDPOINTS (UNCHANGED)
# ==========================================
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"status": "Online", "active_engines": {"stockout": stockout_engine is not None, "smartport": smartport_engine is not None, "nasa": nasa_engine is not None}}

@app.post("/stockout/upload")
async def upload_stockout(file: UploadFile = File(...)):
    if not stockout_engine: raise HTTPException(status_code=500)
    return await stockout_engine.predict_from_file(file)

@app.post("/smartport/upload")
async def upload_smartport(file: UploadFile = File(...)):
    if not smartport_engine: raise HTTPException(status_code=500)
    return await smartport_engine.predict_from_file(file)

@app.post("/nasa/upload")
async def upload_nasa(file: UploadFile = File(...)):
    if not nasa_engine: raise HTTPException(status_code=500)
    return await nasa_engine.predict_from_file(file)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)