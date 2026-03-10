import os
from supabase import create_client, Client

SUPABASE_URL = "https://tqxbxyyrnvpjhbizopsg.supabase.co"


def get_supabase() -> Client | None:
    """
    Return a Supabase client for the Streamlit UI.

    Priority:
    1) SUPABASE_ANON_KEY
    2) SUPABASE_KEY
    3) SUPABASE_SERVICE_ROLE_KEY
    4) SUPABASE_SERVICE_KEY
    """
    key = (
        os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
    )

    if not key:
        print("⚠️ No Supabase key found in environment")
        return None

    try:
        return create_client(SUPABASE_URL, key)
    except Exception as e:
        print(f"❌ Failed to initialize Supabase client: {e}")
        return None