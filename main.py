from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="AI Corporate Suite", version="1.0.0")

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "AI Corporate Suite API",
        "endpoints": {
            "smartport": "/smartport/upload",
            "nasa": "/nasa/upload",
            "stockout": "/stockout/upload"
        },
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/smartport/upload")
async def upload_smartport(file: UploadFile = File(...)):
    """Upload SmartPort tracking data CSV"""
    try:
        from core.smartport_predictor import SmartPortPredictor
        predictor = SmartPortPredictor()
        result = await predictor.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/nasa/upload")
async def upload_nasa(file: UploadFile = File(...)):
    """Upload NASA engine test data TXT"""
    try:
        from core.nasa_predictor import NASAPredictor
        predictor = NASAPredictor()
        result = await predictor.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stockout/upload")
async def upload_stockout(file: UploadFile = File(...)):
    """Upload inventory data CSV"""
    try:
        from core.stockout_predictor import StockoutPredictor
        predictor = StockoutPredictor()
        result = await predictor.predict_from_file(file)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
