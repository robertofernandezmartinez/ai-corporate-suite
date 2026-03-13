import os
import pandas as pd
from supabase import create_client, Client


def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

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


def delete_batch(table_name: str, batch_id: str):
    supabase = get_supabase()
    return supabase.table(table_name).delete().eq("batch_id", batch_id).execute()


def delete_all_rows(table_name: str):
    supabase = get_supabase()
    return supabase.table(table_name).delete().neq("prediction_id", "").execute()


def get_smartport_batches():
    return _fetch_table("smartport_predictions")


def get_stockout_batches():
    return _fetch_table("stockout_predictions")


def get_nasa_batches():
    return _fetch_table("nasa_predictions")