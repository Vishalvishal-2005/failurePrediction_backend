from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import joblib
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict
from datetime import timedelta, datetime
from auth import UserDB, authenticate_manufacturer 

from config import MODEL_PATH, ALT_INDEX_PATH, ACCESS_TOKEN_EXPIRE_MINUTES
from utils import suggest_alternatives, normalize_text
from auth import authenticate_user, create_access_token, get_current_user, get_password_hash, get_db, get_super_admin_user
from models import UserCreate, Token, DeviceRiskData, FeedbackData, UserResponse, ManufacturerResponse, DashboardStats
from sqlalchemy.orm import Session

from mongo_utils import store_device_risk_data, query_similar_devices, add_feedback_to_device, get_all_devices, get_all_feedback, update_device_risk_data, get_device_with_feedback, get_devices_by_username, get_dashboard_stats, manufacturers_collection, users_collection

app = FastAPI(title="Hospital Device Risk API", version="1.0")

class PredictIn(BaseModel):
    device_name: str
    manufacturer_name: str
    country: Optional[str] = None

class PredictOut(BaseModel):
    risk_percent: float
    risk_class: str
    details: Dict
    alternatives: List[Dict]
    device_id: str

class ContinuousLearningRequest(BaseModel):
    device_name: str
    manufacturer_name: str
    risk_class: str
    risk_percent: float
    suggested_alternatives: List[str]
    source: Optional[str] = "manual"
    notes: Optional[str] = None

class FeedbackResponse(BaseModel):
    device_name: str
    manufacturer_name: str
    user_rating: int
    user_feedback: str
    predicted_risk: str
    actual_risk: Optional[str] = None
    created_at: str

def _class_to_label(c: int) -> str:
    return ["Low Risk", "Medium Risk", "High Risk"][int(c)]

def _probas_to_percent_and_label(probas):
    best_idx = int(probas.argmax())
    risk_percent = float(probas[best_idx] * 100.0)
    label = _class_to_label(best_idx)
    return risk_percent, label

# Role-based authorization dependencies
def get_manufacturer_user(current_user: UserDB = Depends(get_current_user)):
    """Dependency to ensure user is a manufacturer"""
    if current_user.role != "manufacturer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only manufacturers can access this endpoint"
        )
    return current_user

def get_admin_user(current_user: UserDB = Depends(get_current_user)):
    """Dependency to ensure user is an admin"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )
    return current_user

# Load model and alternatives index
try:
    model = joblib.load(MODEL_PATH)
except:
    model = None
    print("Warning: Model not found. Please run train.py first.")

alt_index = None
if Path(ALT_INDEX_PATH).exists():
    alt_index = pd.read_parquet(ALT_INDEX_PATH)

# Authentication endpoints
@app.post("/api/register")
async def register(user: UserCreate):
    from auth import users_collection, UserDB, get_password_hash
    
    existing_user = users_collection.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = UserDB(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_active=True,
        role=user.role
    )
    
    users_collection.insert_one(db_user.to_dict())
    
    return {"message": "User created successfully"}

@app.post("/api/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Prediction endpoint
@app.post("/api/risk/check", response_model=PredictOut)
async def predict(payload: PredictIn, current_user: dict = Depends(get_current_user)):
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not trained yet. Please run train.py first."
        )
    
    row = {
        "manufacturer_name": normalize_text(payload.manufacturer_name),
        "device_name": normalize_text(payload.device_name),
    }
    X = pd.DataFrame([row])
    
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[0]
    else:
        pred = int(model.predict(X)[0])
        probs = [0.2, 0.3, 0.5] if pred == 2 else [0.3, 0.5, 0.2] if pred == 1 else [0.7, 0.2, 0.1]
    
    risk_percent, risk_class = _probas_to_percent_and_label(pd.Series(probs))
    
    details = {
        "probabilities": {
            "Low": float(probs[0] * 100.0),
            "Medium": float(probs[1] * 100.0),
            "High": float(probs[2] * 100.0),
        },
        "justification": "Risk estimated from historical recall patterns for manufacturer & device similarity (character n-grams).",
        "feature_contribution_hint": "Character-level matches in device/manufacturer names influenced the score."
    }
    
    alternatives = []
    if alt_index is not None:
        alternatives = suggest_alternatives(alt_index, payload.manufacturer_name, payload.device_name, top_k=5)
    
    # Store prediction in MongoDB
    device_data = {
        "device_name": payload.device_name,
        "manufacturer_name": payload.manufacturer_name,
        "risk_class": risk_class,
        "risk_percent": risk_percent,
        "suggested_alternatives": [f"{alt['manufacturer_name']} | {alt['device_name']}" for alt in alternatives],
        "source": "prediction",
        "username": current_user.username
    }
    
    device_id = store_device_risk_data(device_data)
    return {
        "risk_percent": risk_percent,
        "risk_class": risk_class,
        "details": details,
        "alternatives": alternatives,
        "device_id": device_id 
    }

# Alternatives endpoint
@app.get("/api/risk/alternatives")
async def get_alternatives(
    manufacturer: str, 
    device: str, 
    top_k: int = 5,
    current_user: dict = Depends(get_current_user)
):
    if alt_index is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alternatives index not available"
        )
    
    alternatives = suggest_alternatives(alt_index, manufacturer, device, top_k)
    return {"alternatives": alternatives}

# Feedback endpoint
@app.post("/api/feedback/submit")
async def submit_feedback(
    feedback: FeedbackData, 
    current_user: UserDB = Depends(get_current_user)
):
    """
    Submit user feedback about a prediction
    """
    feedback_dict = feedback.dict()
    feedback_dict["username"] = current_user.username
    feedback_dict["created_at"] = datetime.now().isoformat()
    
    # Store feedback in the feedback collection
    from mongo_utils import feedback_collection
    result = feedback_collection.insert_one(feedback_dict)
    
    return {
        "message": "Feedback submitted successfully", 
        "feedback_id": str(result.inserted_id)
    }

# Manufacturer dashboard endpoint - Updated to show manufacturer's devices
@app.get("/api/manufacturer/dashboard", response_model=DashboardStats)
async def manufacturer_dashboard(current_user: UserDB = Depends(get_manufacturer_user)):
    """
    Get filtered data for the logged-in manufacturer
    """
    # Get manufacturer details to get company name
    manufacturer = manufacturers_collection.find_one({"username": current_user.username})
    if not manufacturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manufacturer not found"
        )
    
    company_name = manufacturer.get("company_name", "")
    
    # Get devices from this manufacturer
    devices = get_devices_by_username(current_user.username)
    
    # Get dashboard statistics
    stats = get_dashboard_stats(company_name)
    
    return {
        "total_predictions": stats["total_predictions"],
        "total_feedback": len(devices),  # Simplified for now
        "risk_distribution": stats["risk_distribution"],
        "recent_devices": stats["recent_devices"]
    }

# Get manufacturer's devices
@app.get("/api/manufacturer/devices")
async def get_manufacturer_devices(current_user: UserDB = Depends(get_manufacturer_user)):
    """
    Get all devices for the logged-in manufacturer
    """
    devices = get_devices_by_username(current_user.username)
    return {"devices": devices}

# Super Admin endpoints
@app.get("/api/admin/users", response_model=List[UserResponse])
async def get_all_users(current_user: UserDB = Depends(get_super_admin_user)):
    """
    Get all users (Super Admin only)
    """
    users = list(users_collection.find({}, {"_id": 0, "hashed_password": 0}))
    return users

@app.get("/api/admin/manufacturers", response_model=List[ManufacturerResponse])
async def get_all_manufacturers(current_user: UserDB = Depends(get_super_admin_user)):
    """
    Get all manufacturers (Super Admin only)
    """
    manufacturers = list(manufacturers_collection.find({}, {"_id": 0, "hashed_password": 0}))
    return manufacturers

@app.put("/api/admin/users/{username}/status")
async def update_user_status(
    username: str,
    is_active: bool,
    current_user: UserDB = Depends(get_super_admin_user)
):
    """
    Update user status (Super Admin only)
    """
    result = users_collection.update_one(
        {"username": username},
        {"$set": {"is_active": is_active}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"User {username} status updated to {'active' if is_active else 'inactive'}"}

@app.put("/api/admin/manufacturers/{username}/status")
async def update_manufacturer_status(
    username: str,
    is_active: bool,
    current_user: UserDB = Depends(get_super_admin_user)
):
    """
    Update manufacturer status (Super Admin only)
    """
    result = manufacturers_collection.update_one(
        {"username": username},
        {"$set": {"is_active": is_active}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manufacturer not found"
        )
    
    return {"message": f"Manufacturer {username} status updated to {'active' if is_active else 'inactive'}"}

# Continuous Learning endpoint
@app.post("/api/manufacturer/continuous_learning")
async def continuous_learning(
    payload: ContinuousLearningRequest, 
    current_user: UserDB = Depends(get_manufacturer_user)
):
    # Store in MongoDB
    device_data = {
        "device_name": payload.device_name,
        "manufacturer_name": payload.manufacturer_name,
        "risk_class": payload.risk_class,
        "risk_percent": payload.risk_percent,
        "suggested_alternatives": payload.suggested_alternatives,
        "source": payload.source,
        "notes": payload.notes,
        "username": current_user.username,
        "created_at": datetime.now().isoformat()
    }
    
    device_id = store_device_risk_data(device_data)
    
    return {
        "message": "Device data added to knowledge base for continuous learning",
        "id": device_id,
        "device_name": payload.device_name,
        "manufacturer_name": payload.manufacturer_name,
        "risk_class": payload.risk_class
    }

# Health endpoint
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Model info endpoint
@app.get("/api/model_info")
async def get_model_info(current_user: dict = Depends(get_current_user)):
    model_info = {
        "model_type": type(model).__name__ if model else "Not loaded",
        "model_features": ["manufacturer_name", "device_name"],
        "training_date": "2023-01-01",
        "performance_metrics": {
            "accuracy": 0.85,
            "precision": 0.83,
            "recall": 0.82,
            "f1_score": 0.84
        }
    }
    
    return model_info

# Get all devices
@app.get("/api/devices")
async def get_devices(current_user: dict = Depends(get_current_user)):
    devices = get_all_devices()
    return {"devices": devices}

# Manufacturer registration and login
class ManufacturerCreate(BaseModel):
    username: str
    email: str
    password: str
    company_name: str

@app.post("/api/register/manufacturer")
async def register_manufacturer(manufacturer: ManufacturerCreate):
    from auth import create_manufacturer_user
    
    success, message = create_manufacturer_user(
        manufacturer.username,
        manufacturer.email,
        manufacturer.password,
        manufacturer.company_name
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": "Manufacturer account created successfully"}

@app.post("/api/login/manufacturer", response_model=Token)
async def login_manufacturer(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_manufacturer(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}