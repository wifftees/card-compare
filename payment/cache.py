"""In-memory cache for payment invoice URLs with TTL"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from database.models import ProductOption

logger = logging.getLogger(__name__)


@dataclass
class CachedInvoice:
    """Cached invoice data"""
    external_invoice_id: str
    confirmation_url: str
    created_at: datetime
    ttl_seconds: int = 3600  # 1 hour TTL
    
    def is_expired(self) -> bool:
        """Check if cached invoice has expired"""
        expiration_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() >= expiration_time


class InvoiceCache:
    """
    In-memory cache for invoice URLs to avoid creating duplicate invoices
    when user repeatedly opens payment screen.
    
    Cache key: (user_id, option)
    TTL: 1 hour (balance between reusability and freshness)
    
    Reference: CardSubscriptionPaymentProcessor.kt caching logic
    """
    
    def __init__(self):
        """Initialize empty cache"""
        self._cache: Dict[Tuple[int, ProductOption], CachedInvoice] = {}
    
    def get(self, user_id: int, option: ProductOption) -> Optional[CachedInvoice]:
        """
        Get cached invoice if exists and not expired
        
        Args:
            user_id: Telegram user ID
            option: Product option (SINGLE or PACKET)
            
        Returns:
            CachedInvoice if found and valid, None otherwise
        """
        cache_key = (user_id, option)
        cached = self._cache.get(cache_key)
        
        if cached is None:
            logger.debug(f"Cache MISS: user_id={user_id}, option={option.value}")
            return None
        
        if cached.is_expired():
            logger.info(
                f"Cache EXPIRED: user_id={user_id}, option={option.value}, "
                f"created_at={cached.created_at}"
            )
            # Remove expired entry
            del self._cache[cache_key]
            return None
        
        logger.info(
            f"Cache HIT: user_id={user_id}, option={option.value}, "
            f"external_invoice_id={cached.external_invoice_id}"
        )
        return cached
    
    def set(
        self,
        user_id: int,
        option: ProductOption,
        external_invoice_id: str,
        confirmation_url: str,
        ttl_seconds: int = 3600
    ) -> None:
        """
        Cache invoice data
        
        Args:
            user_id: Telegram user ID
            option: Product option (SINGLE or PACKET)
            external_invoice_id: YooKassa order_id (UUID)
            confirmation_url: Payment link from YooKassa
            ttl_seconds: Time to live in seconds (default: 3600 = 1 hour)
        """
        cache_key = (user_id, option)
        cached_invoice = CachedInvoice(
            external_invoice_id=external_invoice_id,
            confirmation_url=confirmation_url,
            created_at=datetime.utcnow(),
            ttl_seconds=ttl_seconds
        )
        
        self._cache[cache_key] = cached_invoice
        
        logger.info(
            f"Cache SET: user_id={user_id}, option={option.value}, "
            f"external_invoice_id={external_invoice_id}, ttl={ttl_seconds}s"
        )
    
    def invalidate(self, user_id: int, option: ProductOption) -> None:
        """
        Manually invalidate cached invoice
        
        Args:
            user_id: Telegram user ID
            option: Product option (SINGLE or PACKET)
        """
        cache_key = (user_id, option)
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.info(f"Cache INVALIDATED: user_id={user_id}, option={option.value}")
    
    def clear(self) -> None:
        """Clear all cached invoices"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache CLEARED: removed {count} entries")
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache
        
        Returns:
            Number of expired entries removed
        """
        expired_keys = [
            key for key, cached in self._cache.items()
            if cached.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cache CLEANUP: removed {len(expired_keys)} expired entries")
        
        return len(expired_keys)


# Global cache instance (singleton)
invoice_cache = InvoiceCache()
