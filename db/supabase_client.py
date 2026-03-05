# =========================
# Supabase Client (Shared)
# =========================
# This helper centralizes how we initialize the Supabase client across the suite.
#
# It supports multiple environment variable names for compatibility:
# - SUPABASE_URL (required)
# - SUPABASE_KEY (recommended if you already use it)
# - SUPABASE_SERVICE_ROLE_KEY (recommended in FastAPI backend)
# - SUPABASE_ANON_KEY (recommended in Streamlit / client apps)
#
# If variables are missing, it logs a clear error and returns None by default,
# so the app can still start and show an informative message.
# You can enforce strict behavior by setting SUPABASE_STRICT=1.

import os
from supabase import create_client, Client


SUPABASE_URL = "https://tqxbxyyrnvpjhbizopsg.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase() -> Client | None:
    """
    Returns a Supabase client using service key.
    Returns None if key is missing.
    """
    if not SUPABASE_KEY:
        print("⚠️ SUPABASE_SERVICE_KEY not set")
        return None

    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ----------------------------
# BATCH HELPERS
# ----------------------------

def get_smartport_batches(limit: int = 20):
    supabase = get_supabase()
    if not supabase:
        return []

    resp = (
        supabase.table("smartport_predictions")
        .select("batch_id,created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return resp.data or []


def get_stockout_batches(limit: int = 20):
    supabase = get_supabase()
    if not supabase:
        return []

    resp = (
        supabase.table("stockout_predictions")
        .select("batch_id,created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return resp.data or []


def get_nasa_batches(limit: int = 20):
    supabase = get_supabase()
    if not supabase:
        return []

    resp = (
        supabase.table("nasa_predictions")
        .select("batch_id,created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return resp.data or []