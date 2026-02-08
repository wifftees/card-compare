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
    reports_amount: int
    
    class Config:
        from_attributes = True


class PaymentStatus(str, Enum):
    """Payment status types"""
    NEW = "NEW"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"  # Payment canceled or expired


class Payment(BaseModel):
    """Payment model"""
    id: int
    user_id: int
    total_price: int
    option: ProductOption
    status: PaymentStatus
    external_invoice_id: Optional[str] = None  # YooKassa order_id (UUID)
    confirmation_url: Optional[str] = None  # YooKassa payment link
    created_at: datetime
    updated_at: Optional[datetime] = None  # Updated when status changes
    
    class Config:
        from_attributes = True


class CreatePaymentDTO(BaseModel):
    """DTO for creating a new payment"""
    user_id: int
    total_price: int
    option: ProductOption


class ReportState(str, Enum):
    """Report state types"""
    NEW = "NEW"
    GENERATED = "GENERATED"


class Report(BaseModel):
    """Report model"""
    id: int
    user_id: int
    articles: str
    state: ReportState
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CreateReportDTO(BaseModel):
    """DTO for creating a new report"""
    user_id: int
    articles: str
