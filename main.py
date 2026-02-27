import os
import logging
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

# Importaciones ajustadas a tu carpeta 'core'
from core.nasa_predictor import NASAPredictor
from core.smartport_predictor import SmartPortPredictor
from core.stockout_predictor import StockoutPredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AI_Corporate_Suite")

app = FastAPI(title="AI Corporate Suite API")

# Seguridad
API_KEY = os.getenv("SUITE_INTERNAL_KEY", "dev_key")

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return x_api_key

# Inicialización de motores
nasa_engine = NASAPredictor()
smartport_engine = SmartPortPredictor()
stockout_engine = StockoutPredictor()

@app.get("/")
async def health():
    return {"status": "Online", "suite": "AI Corporate Suite"}

@app.post("/predict/nasa", dependencies=[Depends(verify_api_key)])
async def predict_nasa(file: UploadFile = File(...)):
    return await nasa_engine.predict_from_file(file)

@app.post("/predict/smartport", dependencies=[Depends(verify_api_key)])
async def predict_smartport(file: UploadFile = File(...)):
    return await smartport_engine.predict_from_file(file)

@app.post("/predict/stockout", dependencies=[Depends(verify_api_key)])
async def predict_stockout(file: UploadFile = File(...)):
    return await stockout_engine.predict_from_file(file)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)