import os
import pandas as pd
from supabase import create_client, Client


def get_supabase() -> Client:

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url:
        raise ValueError("SUPABASE_URL missing")

    if not key:
        raise ValueError("SUPABASE_KEY missing")

    return create_client(url, key)


def _fetch_table(table_name: str):

    try:

        supabase = get_supabase()

        response = (
            supabase
            .table(table_name)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        data = response.data if hasattr(response, "data") else []

        if not data:
            return pd.DataFrame()

        return pd.DataFrame(data)

    except Exception:
        return pd.DataFrame()


def get_smartport_batches():
    return _fetch_table("smartport_predictions")


def get_stockout_batches():
    return _fetch_table("stockout_predictions")


def get_nasa_batches():
    return _fetch_table("nasa_predictions")