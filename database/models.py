"""Pydantic models for database entities"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class User(BaseModel):
    """User model"""
    id: int  # Telegram user_id
    username: Optional[str] = None
    created_at: datetime
    reports_balance: int = 0
    
    class Config:
        from_attributes = True


class CreateUserDTO(BaseModel):
    """DTO for creating a new user"""
    id: int  # Telegram user_id
    username: Optional[str] = None


class UpdateBalanceDTO(BaseModel):
    """DTO for updating user balance"""
    user_id: int
    amount: int  # Can be positive or negative


class FeatureFlag(BaseModel):
    """Feature flag model"""
    name: str
    enabled: bool
    
    class Config:
        from_attributes = True
