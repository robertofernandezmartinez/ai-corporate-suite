import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Initialize logging to see what's happening in Railway logs
logger = logging.getLogger(__name__)

load_dotenv()
_supabase_client = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        # Railway will provide these via Environment Variables
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            # Instead of crashing the whole API, we log the error 
            # and return None to allow the API to at least start
            logger.error("❌ CRITICAL: SUPABASE_URL or SUPABASE_KEY missing in environment variables.")
            return None
            
        try:
            _supabase_client = create_client(url, key)
            logger.info("✅ Supabase client initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            return None
            
    return _supabase_client