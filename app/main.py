# Creates FastAPI app
app = FastAPI(title="AI Corporate Suite", version="1.0.0")

# Home page endpoint
@app.get("/")
def root():
    return {"status": "online", "message": "AI Corporate Suite API", "docs": "/docs"}

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "healthy"}

# Upload endpoint - receives CSV, predicts, returns results
@app.post("/smartport/upload")
async def upload_smartport(file: UploadFile = File(...)):
    try:
        from core.smartport_predictor import SmartPortPredictor
        predictor = SmartPortPredictor()
        result = await predictor.predict_from_file(file)  # Calls Block 5 code
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Runs the server on port 8000
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)