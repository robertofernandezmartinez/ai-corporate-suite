import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv()

_supabase_client: Client | None = None


def _resolve_supabase_key() -> str | None:
    """
    Resolve the Supabase key with backward-compatible naming.
    Priority:
      1) SUPABASE_KEY
      2) SUPABASE_SERVICE_ROLE_KEY
      3) SUPABASE_ANON_KEY
    """
    return (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )


def get_supabase() -> Client | None:
    """
    Returns a cached Supabase client or initializes it once.
    If credentials are missing, returns None (unless SUPABASE_STRICT=1).
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    url = os.getenv("SUPABASE_URL")
    key = _resolve_supabase_key()

    strict = os.getenv("SUPABASE_STRICT", "0") == "1"

    if not url or not key:
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not key:
            missing.append("SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY)")

        msg = f"❌ CRITICAL: Missing Supabase env vars: {', '.join(missing)}"
        logger.error(msg)

        if strict:
            raise RuntimeError(msg)

        return None

    try:
        _supabase_client = create_client(url, key)
        logger.info("✅ Supabase client initialized successfully.")
        return _supabase_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {e}")

        if strict:
            raise

        return None

def get_smartport_batches(limit: int = 20):
    """
    Fetch SmartPort prediction batches from Supabase.
    """

    try:
        response = (
            supabase
            .table("smartport_predictions")
            .select("batch_id, prediction, created_at")
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )

        rows = response.data

        if not rows:
            return []

        import pandas as pd
        df = pd.DataFrame(rows)

        batches = []

        for batch_id, group in df.groupby("batch_id"):

            batches.append({
                "batch_id": batch_id,
                "records": len(group),
                "created_at": group["created_at"].max()
            })

        batches = sorted(
            batches,
            key=lambda x: x["created_at"],
            reverse=True
        )

        return batches[:limit]

    except Exception as e:
        print(f"Supabase SmartPort fetch error: {e}")
        return []


def get_stockout_batches(limit: int = 20):
    """
    Fetch Stockout prediction batches from Supabase.
    """

    try:
        response = (
            supabase
            .table("stockout_predictions")
            .select("batch_id, prediction, created_at")
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )

        rows = response.data

        if not rows:
            return []

        import pandas as pd
        df = pd.DataFrame(rows)

        batches = []

        for batch_id, group in df.groupby("batch_id"):

            batches.append({
                "batch_id": batch_id,
                "records": len(group),
                "created_at": group["created_at"].max()
            })

        batches = sorted(
            batches,
            key=lambda x: x["created_at"],
            reverse=True
        )

        return batches[:limit]

    except Exception as e:
        print(f"Supabase Stockout fetch error: {e}")
        return []


def get_nasa_batches(limit: int = 20):
    """
    Fetch NASA RUL prediction batches from Supabase.
    """

    try:
        response = (
            supabase
            .table("nasa_predictions")
            .select("batch_id, prediction, created_at")
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )

        rows = response.data

        if not rows:
            return []

        import pandas as pd
        df = pd.DataFrame(rows)

        batches = []

        for batch_id, group in df.groupby("batch_id"):

            batches.append({
                "batch_id": batch_id,
                "records": len(group),
                "created_at": group["created_at"].max()
            })

        batches = sorted(
            batches,
            key=lambda x: x["created_at"],
            reverse=True
        )

        return batches[:limit]

    except Exception as e:
        print(f"Supabase NASA fetch error: {e}")
        return []