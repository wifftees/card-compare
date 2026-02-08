"""Supabase client initialization"""
import logging
from typing import Optional
from supabase import create_client, Client
from bot.config import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client"""
    
    _instance: Optional[Client] = None
    _admin_instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance (anon key)"""
        if cls._instance is None:
            logger.info("Initializing Supabase client...")
            cls._instance = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            logger.info("✅ Supabase client initialized")
        return cls._instance
    
    @classmethod
    def get_admin_client(cls) -> Client:
        """
        Get or create Supabase admin client instance (service role key).
        This client bypasses Row Level Security (RLS) policies.
        Use for server-side operations that need full database access.
        """
        if cls._admin_instance is None:
            if not settings.supabase_service_key:
                logger.warning(
                    "⚠️ SUPABASE_SERVICE_KEY not configured! "
                    "Using anon key instead. This may cause RLS errors."
                )
                # Fallback to regular client if service key not configured
                return cls.get_client()
            
            logger.info("Initializing Supabase admin client (service role)...")
            cls._admin_instance = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
            logger.info("✅ Supabase admin client initialized")
        return cls._admin_instance
    
    @classmethod
    def close(cls):
        """Close Supabase clients"""
        if cls._instance is not None:
            cls._instance = None
            logger.info("✅ Supabase client closed")
        if cls._admin_instance is not None:
            cls._admin_instance = None
            logger.info("✅ Supabase admin client closed")


# Convenience functions
def get_supabase() -> Client:
    """Get Supabase client instance (anon key)"""
    return SupabaseClient.get_client()


def get_supabase_admin() -> Client:
    """
    Get Supabase admin client instance (service role key).
    This client bypasses Row Level Security (RLS) policies.
    Use for server-side operations like creating events, admin operations, etc.
    """
    return SupabaseClient.get_admin_client()
