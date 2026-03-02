import os
import sys
from datetime import datetime, timedelta, timezone
from db.supabase_client import get_supabase


def main():
    retention_days = int(os.getenv("RETENTION_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    supabase = get_supabase()
    if not supabase:
        print("Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY.")
        sys.exit(1)

    tables = ["smartport_predictions", "nasa_predictions", "stockout_predictions"]

    for t in tables:
        try:
            # Delete rows older than cutoff
            resp = supabase.table(t).delete().lt("created_at", cutoff_iso).execute()
            deleted = len(resp.data) if resp.data else 0
            print(f"[OK] {t}: deleted ~{deleted} rows older than {cutoff_iso}")
        except Exception as e:
            print(f"[WARN] {t}: cleanup failed: {e}")

    print("Cleanup completed.")


if __name__ == "__main__":
    main()