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


def get_supabase() -> Client | None:
    """
    Return a Supabase client using any supported environment variable name.

    Supported names:
    - SUPABASE_SERVICE_ROLE_KEY
    - SUPABASE_SERVICE_KEY
    - SUPABASE_KEY
    - SUPABASE_ANON_KEY
    """
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )

    if not key:
        print("⚠️ No Supabase key found in environment")
        return None

    try:
        return create_client(SUPABASE_URL, key)
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
        return None