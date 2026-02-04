"""Supabase client initialization"""
import logging
from typing import Optional
from supabase import create_client, Client
from bot.config import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client"""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance"""
        if cls._instance is None:
            logger.info("Initializing Supabase client...")
            cls._instance = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            logger.info("✅ Supabase client initialized")
        return cls._instance
    
    @classmethod
    def close(cls):
        """Close Supabase client"""
        if cls._instance is not None:
            cls._instance = None
            logger.info("✅ Supabase client closed")


# Convenience function
def get_supabase() -> Client:
    """Get Supabase client instance"""
    return SupabaseClient.get_client()
