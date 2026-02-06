"""Pydantic models for database entities"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel


class ProductOption(str, Enum):
    """Product option types"""
    SINGLE = "SINGLE"
    PACKET = "PACKET"


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


class Price(BaseModel):
    """Price model"""
    option: ProductOption
    price: int
    
    class Config:
        from_attributes = True


class PaymentStatus(str, Enum):
    """Payment status types"""
    NEW = "NEW"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Payment(BaseModel):
    """Payment model"""
    id: int
    user_id: int
    reports_amount: int
    total_price: int
    option: ProductOption
    status: PaymentStatus
    telegram_payment_charge_id: Optional[str] = None
    provider_payment_charge_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreatePaymentDTO(BaseModel):
    """DTO for creating a new payment"""
    user_id: int
    reports_amount: int
    total_price: int
    option: ProductOption
