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