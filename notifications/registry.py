"""Campaign resolver registry.

Register a resolver for each campaign_id. The resolver is an async callable
that returns a list of CampaignTarget — the users who currently qualify for
the campaign and the timestamp from which the notification schedule starts.
"""

import logging
from typing import Callable, Awaitable

from .models import CampaignTarget

logger = logging.getLogger(__name__)

ResolverFn = Callable[[], Awaitable[list[CampaignTarget]]]


class CampaignRegistry:
    def __init__(self):
        self._resolvers: dict[str, ResolverFn] = {}

    def resolver(self, campaign_id: str):
        """Decorator to register a resolver for *campaign_id*."""

        def decorator(fn: ResolverFn) -> ResolverFn:
            if campaign_id in self._resolvers:
                logger.warning(f"Overwriting resolver for campaign '{campaign_id}'")
            self._resolvers[campaign_id] = fn
            return fn

        return decorator

    def get(self, campaign_id: str) -> ResolverFn | None:
        return self._resolvers.get(campaign_id)

    @property
    def campaign_ids(self) -> list[str]:
        return list(self._resolvers.keys())


registry = CampaignRegistry()
