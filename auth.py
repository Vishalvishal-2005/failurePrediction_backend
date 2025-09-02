# auth.py - Updated with Super Admin functionality
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from models import TokenData
from pymongo import MongoClient
import os
from config import MONGODB_URI, MONGODB_DB_NAME, SECRET_KEY, ALGORITHM

# Password hashing - handle bcrypt version issue
try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except:
    # Fallback if bcrypt has issues
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]
users_collection = db["users"]
manufacturers_collection = db["manufacturers"]
SUPER_ADMIN_USERNAME = "admin"  # Default super admin username

# Initialize super admin if not exists
def init_super_admin():
    """Initialize the super admin user if it does not already exist."""
    super_admin = users_collection.find_one({"username": SUPER_ADMIN_USERNAME})
    if not super_admin:
        hashed_password = get_password_hash("admin123")  # Default password
        users_collection.insert_one({
            "username": SUPER_ADMIN_USERNAME,
            "email": "admin@hospital-device-risk.com",
            "hashed_password": hashed_password,
            "is_active": True,
            "role": "super_admin",
            "created_at": datetime.now().isoformat()
        })
        print("Super admin user created")

# User model (MongoDB document)
class UserDB:
    def __init__(self, username: str, email: str, hashed_password: str, 
                 is_active: bool = True, role: str = "user", **kwargs):
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.is_active = is_active
        self.role = role
    
    def to_dict(self):
        """Convert the object to a dictionary representation."""
        return {
            "username": self.username,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "is_active": self.is_active,
            "role": self.role
        }

# Database dependency
def get_db():
    """Yield the database connection."""
    try:
        yield db
    finally:
        pass

def verify_password(plain_password, hashed_password):
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Generate a hashed password using pwd_context."""
    return pwd_context.hash(password)

def get_user(username: str):
    """Retrieve a user by username."""
    user_data = users_collection.find_one({"username": username})
    if user_data:
        user_data_without_id = {k: v for k, v in user_data.items() if k != '_id'}
        return UserDB(**user_data_without_id)
    return None

def get_manufacturer(username: str):
    """Retrieve manufacturer information by username."""
    manufacturer_data = manufacturers_collection.find_one({"username": username})
    if manufacturer_data:
        return {
            "username": manufacturer_data["username"],
            "email": manufacturer_data["email"],
            "company_name": manufacturer_data["company_name"],
            "is_active": manufacturer_data.get("is_active", True),
            "role": "manufacturer"
        }
    return None

def authenticate_user(username: str, password: str):
    """def authenticate_user(username: str, password: str):
    Authenticate a user based on username and password.  This function retrieves a
    user by their username and checks the provided password against the stored
    hashed password. If the user is not found,  it checks if the username belongs
    to a manufacturer and verifies the  password accordingly. The function returns
    a UserDB object for valid  users or manufacturers, and False for invalid
    credentials.
    
    Args:
        username (str): The username of the user or manufacturer.
        password (str): The password provided for authentication."""
    user = get_user(username)
    if not user:
        # Check if it's a manufacturer
        manufacturer = get_manufacturer(username)
        if manufacturer and verify_password(password, manufacturer.get("hashed_password", "")):
            return UserDB(
                username=manufacturer["username"],
                email=manufacturer["email"],
                hashed_password=manufacturer["hashed_password"],
                is_active=manufacturer["is_active"],
                role="manufacturer"
            )
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JSON Web Token (JWT) access token with an expiration time."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# In auth.py, update the get_current_user function around line 147

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """async def get_current_user(token: str = Depends(oauth2_scheme)):
    Retrieve the current user based on the provided token.  This function decodes
    the JWT token to extract the username and role.  It first attempts to retrieve
    a user from the regular users collection.  If no user is found, it checks the
    manufacturers collection. If a manufacturer  is found, it constructs a UserDB
    object with the relevant details. The function  raises an HTTPException if the
    credentials are invalid or if the user is inactive.
    
    Args:
        token (str): The JWT token used for authentication."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "user")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
        
    # Check both regular users and manufacturers collections
    user = get_user(username=token_data.username)
    if user is None:
        manufacturer = get_manufacturer(username=token_data.username)
        if manufacturer:
            # FIX: Check if hashed_password exists before accessing it
            hashed_password = manufacturer.get("hashed_password", "")
            user = UserDB(
                username=manufacturer["username"],
                email=manufacturer["email"],
                hashed_password=hashed_password,
                is_active=manufacturer.get("is_active", True),
                role=manufacturer.get("role", "manufacturer")
            )
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    user.role = role
    return user
def get_super_admin_user(current_user: UserDB = Depends(get_current_user)):
    """Ensure the user is a super admin."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can access this endpoint"
        )
    return current_user

def create_manufacturer_user(username: str, email: str, password: str, company_name: str):
    # Check if user already exists
    """Create a manufacturer user with separate storage."""
    existing_user = manufacturers_collection.find_one({"username": username})
    if existing_user:
        return False, "Username already exists"
    
    existing_email = manufacturers_collection.find_one({"email": email})
    if existing_email:
        return False, "Email already registered"
    
    # Create manufacturer user
    hashed_password = get_password_hash(password)
    manufacturer_data = {
        "username": username,
        "email": email,
        "hashed_password": hashed_password,
        "company_name": company_name,
        "is_active": True,
        "role": "manufacturer",
        "created_at": datetime.now().isoformat()
    }
    
    result = manufacturers_collection.insert_one(manufacturer_data)
    return True, str(result.inserted_id)

def authenticate_manufacturer(username: str, password: str):
    """Authenticate a manufacturer user."""
    manufacturer_data = manufacturers_collection.find_one({"username": username})
    if not manufacturer_data:
        return False
    
    if not verify_password(password, manufacturer_data["hashed_password"]):
        return False
    
    # Create UserDB object for compatibility
    return UserDB(
        username=manufacturer_data["username"],
        email=manufacturer_data["email"],
        hashed_password=manufacturer_data["hashed_password"],
        is_active=manufacturer_data.get("is_active", True),
        role=manufacturer_data.get("role", "manufacturer")
    )

# Initialize super admin on import
init_super_admin()