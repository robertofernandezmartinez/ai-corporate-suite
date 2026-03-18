from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
import threading
import time

# ==========================================
# API CONFIGURATION & DOCUMENTATION
# ==========================================
# Professional metadata for Swagger UI (/docs)
app = FastAPI(
    title="AI Corporate Suite",
    description="""
    ## Enterprise Industrial Intelligence Platform
    This API orchestrates three ML engines with real-time monitoring:
    * **Supply Chain**: Inventory stockout risk prediction.
    * **Maritime**: AIS-based port congestion & vessel delay analysis.
    * **Aerospace**: Predictive maintenance for NASA turbofan engines.
    """,
    version="2.1.0",
    contact={
        "name": "Industrial AI Operations",
        "email": "admin@your-suite-demo.com",
    },
)

# Global instances for ML engines (Loaded during startup)
stockout_engine = None
smartport_engine = None
nasa_engine = None

# Logger setup to track API performance and bot status
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("ai-corporate-suite-api")

# ==========================================
# STARTUP SERVICES (ML & TELEGRAM)
# ==========================================
@app.on_event("startup")
async def startup_event():
    """
    Service Orchestration on Startup:
    1. Background Thread for Telegram Bot (Non-blocking).
    2. Lazy Loading for Heavy ML Models.
    """
    global stockout_engine, smartport_engine, nasa_engine

    # --- 1. BACKGROUND TELEGRAM SERVICE ---
    def run_bot():
        # Delay to ensure cloud network stack is fully initialized
        time.sleep(5) 
        try:
            import telegram_bot
            logger.info("🤖 Bot module imported successfully from root.")
            
            # Clean up pending webhooks from previous runs
            telegram_bot.bot.remove_webhook()
            logger.info("🤖 Webhook cleared. Starting Infinity Polling...")
            
            # Start the bot loop
            telegram_bot.bot.infinity_polling(skip_pending=True, timeout=60)
        except Exception as e:
            logger.error(f"❌ CRITICAL BOT ERROR: {str(e)}", exc_info=True)

    # Spawning the bot in a separate thread to keep the API responsive
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Telegram Bot thread spawned.")

    # --- 2. ML ENGINES INITIALIZATION ---
    # Loading predictors from the core module
    try:
        from core.stockout_predictor import StockoutPredictor
        stockout_engine = StockoutPredictor()
        logger.info("✅ Stockout Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ Stockout Engine Load Failed: {e}")

    try:
        from core.smartport_predictor import SmartPortPredictor
        smartport_engine = SmartPortPredictor()
        logger.info("✅ SmartPort Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ SmartPort Engine Load Failed: {e}")

    try:
        from core.nasa_predictor import NASAPredictor
        nasa_engine = NASAPredictor()
        logger.info("✅ NASA RUL Engine: ONLINE")
    except Exception as e:
        logger.error(f"⚠️ NASA Engine Load Failed: {e}")

# ==========================================
# MIDDLEWARE
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

@app.get("/", tags=["System Health"])
def root():
    """Returns the operational status of all platform engines."""
    return {
        "status": "Online", 
        "active_engines": {
            "stockout": stockout_engine is not None, 
            "smartport": smartport_engine is not None, 
            "nasa": nasa_engine is not None
        }
    }

@app.post("/stockout/upload", tags=["Supply Chain & Inventory"])
async def upload_stockout(file: UploadFile = File(...)):
    """Infers stockout risk from inventory CSV and triggers alerts if critical."""
    if not stockout_engine: 
        raise HTTPException(status_code=500, detail="Stockout engine offline")
    try:
        result = await stockout_engine.predict_from_file(file)
        
        # Guardrail: Only process if engine successfully analyzed data
        if result.get("success"):
            # Check summary for critical flags to trigger Telegram Push
            criticals = result.get("summary", {}).get("critical_risks", 0)
            if criticals > 0:
                from telegram_bot import send_push_alert
                send_push_alert("Stockout Predictor", "CRITICAL", f"Detected {criticals} products with immediate depletion risk.")
        
        return result
    except Exception as e:
        logger.error(f"Stockout Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/smartport/upload", tags=["Maritime Logistics"])
async def upload_smartport(file: UploadFile = File(...)):
    """Analyzes AIS tracking data for logistical bottlenecks."""
    if not smartport_engine: 
        raise HTTPException(status_code=500, detail="SmartPort engine offline")
    try:
        result = await smartport_engine.predict_from_file(file)
        
        if result.get("success"):
            # Trigger alert based on vessel risk level
            if result.get("summary", {}).get("risk_level") == "CRITICAL":
                from telegram_bot import send_push_alert
                send_push_alert("SmartPort AI", "CRITICAL", "High probability of port congestion detected in current batch.")
            
        return result
    except Exception as e:
        logger.error(f"SmartPort Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/nasa/upload", tags=["Predictive Maintenance"])
async def upload_nasa(file: UploadFile = File(...)):
    """Estimates Remaining Useful Life (RUL) for aircraft engines."""
    if not nasa_engine: 
        raise HTTPException(status_code=500, detail="NASA RUL engine offline")
    try:
        result = await nasa_engine.predict_from_file(file)
        
        if result.get("success"):
            # Alert if maintenance is required within 30 cycles
            critical_engines = result.get("summary", {}).get("critical_engines", 0)
            if critical_engines > 0:
                from telegram_bot import send_push_alert
                send_push_alert("NASA RUL Engine", "CRITICAL", f"{critical_engines} units require immediate inspection (RUL < 30).")
            
        return result
    except Exception as e:
        logger.error(f"NASA Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # Standard Uvicorn runner
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)