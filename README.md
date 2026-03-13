# AI Corporate Suite

AI Corporate Suite is an operational AI platform integrating multiple machine learning applications into a unified production system with dashboards, APIs, automation, and messaging interfaces.

**Live Suite**  
https://ui-production-a2ba.up.railway.app

**Production API**  
https://api-production-dd2a.up.railway.app

![System Architecture](images/system_architecture.png)

---

# Overview

AI Corporate Suite is an operational AI platform that integrates multiple machine learning applications into a single production-style environment.

The platform currently includes three applied AI modules that also exist as standalone projects separately:

- **SmartPort** — Maritime operational risk prediction
    - standalone project: https://github.com/robertofernandezmartinez/smartport-ai-risk-early-warning )
- **Stockout** — Retail inventory stockout prediction
    - standalone project: https://github.com/robertofernandezmartinez/retail-stockout-risk-scoring )
- **NASA RUL** — Predictive maintenance and Remaining Useful Life estimation (s)
    - standalone project: https://github.com/robertofernandezmartinez/cmapss-rul-prediction )

The system allows users to:

- upload raw datasets through a web interface
- trigger machine learning inference through a dedicated API
- persist predictions in a cloud database
- analyze historical runs through dashboards
- communicate with the system directly through Telegram bot
- run automated demo data loading
- automatically clean old predictions

This repository demonstrates how machine learning models can be integrated into an operational AI platform rather than remaining as isolated notebooks.

---

# Live Architecture

The platform is deployed as two independent services on **Railway**:

- **UI Service** — Streamlit dashboards
- **API Service** — FastAPI inference engine

Predictions are persisted in **Supabase (PostgreSQL)**.

---

# Why the UI/API separation matters

The project uses a separated architecture so that:

- the **UI** focuses on dashboards and uploads
- the **API** handles machine learning inference
- both services can scale independently

This architecture reflects a realistic deployment pattern for production machine learning systems.

---

## Telegram Bot Integration

The platform includes a Telegram bot that provides an alternative interface to interact with the AI Corporate Suite outside the Streamlit UI.

The bot allows users to communicate with the system directly through Telegram, enabling simple command-based interactions with the available AI modules.

Main purposes of the bot:

- provide a conversational interface for the platform
- allow quick interaction with the AI modules
- demonstrate how the platform can be extended beyond a traditional web dashboard

Bot script location:

```
bot/telegram_bot.py
```

The bot can be used to trigger operations, retrieve information about the system, or integrate the platform with messaging workflows.

Although the primary interface of the platform is the Streamlit dashboard, the Telegram bot demonstrates how the system can be expanded into multi-channel interfaces for operational environments.

--

# AI Modules

## SmartPort — Maritime Risk Monitoring

SmartPort predicts operational and financial risk related to maritime activity.

Typical use cases include:

- vessel monitoring
- route and weather risk assessment
- maritime operational exposure analysis
- financial impact estimation

Outputs:

- risk score
- risk level
- financial impact

Demo dataset:

```
data/raw/tracking_db_demo.csv
```

Database table:

```
smartport_predictions
```

---

## Stockout — Retail Inventory Risk

Stockout predicts the probability that a product will experience a stockout event.

Typical inputs include:

- store ID
- product ID
- category
- region
- inventory level
- units sold
- price
- discount
- weather
- promotions
- competitor pricing
- seasonality

Outputs:

- risk score
- risk level
- estimated financial impact

The dashboard also includes an **interactive simulation sidebar** allowing users to explore pricing, demand, and inventory scenarios.

Demo dataset:

```
data/raw/retail_store_inventory_PRO.csv
```

Database table:

```
stockout_predictions
```

---

## NASA RUL — Predictive Maintenance

NASA RUL predicts Remaining Useful Life for turbofan engines using the NASA CMAPSS dataset.

The deployed predictor supports the raw telemetry format used in the original NASA dataset.

Outputs:

- predicted remaining useful life
- degradation trends by cycle

Demo dataset:

```
data/raw/train_FD001.txt
```

Database table:

```
nasa_predictions
```

---

# Upload Center

The Upload Center is the entry point for manual model inference.

Supported uploads:

- SmartPort → CSV
- Stockout → CSV
- NASA → TXT / CSV

Upload flow:

```
Upload file
  ↓
FastAPI endpoint
  ↓
Model inference
  ↓
Supabase persistence
  ↓
Dashboard batch
```

Each upload generates a unique **batch_id**.

This ensures:

- uploads never overwrite previous predictions
- automated demo data and manual uploads can coexist
- dashboards can display historical runs.

---

# Dashboards

Each AI module has its own Streamlit dashboard:

```
pages/smartport_streamlit.py
pages/stockout_streamlit.py
pages/nasa_streamlit.py
```

Dashboards include:

- batch selectors
- summary metrics
- charts
- historical batch views
- batch deletion controls
- interpretation panels

---

# Automated Demo Loading

The project includes a script that can automatically populate dashboards with demonstration predictions.

Script:

```
scripts/auto_reload_demo_data.py
```

Purpose:

- populate dashboards automatically
- simplify demos
- simulate a continuously active platform

---

# Automatic Cleanup

The project includes a cleanup utility to prevent the database from growing indefinitely.

Script:

```
scripts/cleanup_old_batches.py
```

Purpose:

- remove old prediction batches
- keep demo environments clean
- prevent uncontrolled table growth

Manual cleanup actions are also available in the UI.

---

# Telegram Bot

The repository includes a Telegram bot:

```
bot/telegram_bot.py
```

The bot allows external interaction with the system without opening the Streamlit interface.

---

# Batch Logic

The suite is designed around **batch-based inference**.

Every inference run generates a unique `batch_id`.

This makes it possible to:

- preserve historical runs
- separate manual uploads from automated demo runs
- inspect the latest run without mixing previous predictions
- delete one run without affecting others.

---

# Data Persistence

All predictions are stored in **Supabase PostgreSQL**.

Tables:

```
smartport_predictions
stockout_predictions
nasa_predictions
```

Common fields:

```
prediction_id
batch_id
created_at
timestamp
```

Module-specific outputs include:

SmartPort:

```
risk_score
risk_level
financial_impact
```

Stockout:

```
risk_score
risk_level
financial_impact
```

NASA:

```
predicted_rul
unit_id
time_in_cycles
```

---

# Machine Learning Integration

Serialized pipelines are stored in:

```
models/
```

Model files:

```
smartport_model.pkl
stockout_model.pkl
nasa_model.pkl
```

Each predictor:

- loads the trained pipeline
- converts uploaded raw data into the expected schema
- runs inference
- formats outputs
- persists predictions in Supabase.

Significant engineering work involved ensuring compatibility between:

- raw uploaded datasets
- training pipelines
- production predictors.

---

# Project Structure

```
ai-corporate-suite/
│
├── bot/                    # Telegram bot
├── core/                   # ML predictors
├── data/
│   └── raw/                # Demo datasets
├── db/                     # Supabase client
├── models/                 # Trained pipelines
├── pages/                  # Streamlit dashboards
├── scripts/                # Automation utilities
│
├── main.py                 # FastAPI entrypoint
├── suite_streamlit.py      # Main UI page
├── ui_theme.py             # Shared UI theme
├── requirements.txt
└── README.md
```

---

# Important Files

API:

```
main.py
```

Endpoints:

```
GET /
POST /smartport/upload
POST /stockout/upload
POST /nasa/upload
```

UI:

```
suite_streamlit.py
pages/00_upload_center.py
pages/smartport_streamlit.py
pages/stockout_streamlit.py
pages/nasa_streamlit.py
```

Predictors:

```
core/smartport_predictor.py
core/stockout_predictor.py
core/nasa_predictor.py
```

Database client:

```
db/supabase_client.py
```

---

# Running the Project Locally

Clone the repository:

```
git clone https://github.com/YOUR_USERNAME/ai-corporate-suite.git
cd ai-corporate-suite
```

Create a virtual environment:

```
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Configure environment variables:

```
export API_BASE_URL=http://127.0.0.1:8000
export SUPABASE_URL=your_supabase_url
export SUPABASE_KEY=your_supabase_key
```

If you want the local UI to use the deployed API:

```
export API_BASE_URL=https://api-production-dd2a.up.railway.app
```

Run the API:

```
uvicorn main:app --reload
```

Run the UI:

```
streamlit run suite_streamlit.py
```

---

# Deployment

The platform is deployed on Railway.

UI startup command:

```
streamlit run suite_streamlit.py --server.port $PORT --server.address 0.0.0.0
```

API startup command:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Environment variables required.

UI service:

```
API_BASE_URL
SUPABASE_URL
SUPABASE_KEY
```

API service:

```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

---

# Author

Roberto Fernández
https://www.linkedin.com/in/robertofernandezmartinez/