from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"  # Added role field

class User(UserBase):
    id: int
    is_active: bool
    role: str  # Added role field

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class FeedbackEntry(BaseModel):
    user_rating: int  # 1-5 scale
    user_feedback: str
    predicted_risk: str
    actual_risk: Optional[str] = None
    username: str
    created_at: datetime

class DeviceRiskData(BaseModel):
    device_name: str
    manufacturer_name: str
    risk_class: str
    risk_percent: float
    suggested_alternatives: List[str]
    feedback: List[FeedbackEntry] = []  # Add feedback field
    created_at: datetime = None

class FeedbackData(BaseModel):
    user_feedback: str  # Only this is required
    user_rating: Optional[int] = None
    device_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    predicted_risk: Optional[str] = None
    actual_risk: Optional[str] = None

# Add to models.py
class DatasetRecord(BaseModel):
    id: str
    original_data: Dict
    normalized_manufacturer: str
    normalized_device: str
    risk_class: Optional[int] = None
    risk_label: Optional[str] = None
    import_timestamp: str
    source: str

class DatasetStats(BaseModel):
    total_records: int
    risk_distribution: List[Dict]
    unique_manufacturers: int
    unique_devices: int

# Admin models
class UserResponse(BaseModel):
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None

class ManufacturerResponse(BaseModel):
    username: str
    email: str
    company_name: str
    is_active: bool
    created_at: Optional[str] = None

class DashboardStats(BaseModel):
    total_predictions: int
    total_feedback: int
    risk_distribution: Dict[str, int]
    recent_devices: List[Dict]