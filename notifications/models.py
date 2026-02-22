"""Pydantic models for the notification campaigns system"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel


class NotificationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class NotificationCampaign(BaseModel):
    id: str
    name: str
    message_template: str
    enabled: bool
    repeat_last_step: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationStep(BaseModel):
    id: int
    campaign_id: str
    step_order: int
    delay_seconds: int

    class Config:
        from_attributes = True


class UserNotification(BaseModel):
    id: int
    user_id: int
    campaign_id: str
    status: NotificationStatus
    current_step: int
    trigger_event_at: datetime
    last_sent_at: Optional[datetime] = None
    next_send_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignTarget(BaseModel):
    """Returned by resolvers: who qualifies and when their trigger happened."""
    user_id: int
    trigger_at: datetime
