"""
Simple auth helpers using Supabase Auth.
Frontend will call these endpoints; Supabase handles JWT.
"""
from typing import Optional, Dict, Any
import os
from supabase import create_client, Client

_supabase: Optional[Client] = None

def get_supabase_client() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")  # service role or anon depending on use
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY required")
        _supabase = create_client(url, key)
    return _supabase
