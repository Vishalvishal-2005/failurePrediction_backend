# mongo_utils.py - Updated with manufacturer-specific queries
from bson import ObjectId
import certifi
from pymongo import MongoClient
from datetime import datetime
from typing import List, Dict, Optional
from config import MONGODB_URI, MONGODB_DB_NAME
import uuid

# Initialize connection variables
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]
devices_collection = db["devices"]
manufacturers_collection = db["manufacturers"]
users_collection = db["users"]
feedback_collection = db["feedback"]

def init_mongo_connection():
    """Initialize MongoDB connection"""
    global client, db, devices_collection, feedback_collection, manufacturers_collection, users_collection
    
    try:
        client = MongoClient(
            MONGODB_URI,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=30000,
            tls=True,
            tlsCAFile=certifi.where()
        )
        client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        db = client[MONGODB_DB_NAME]
        devices_collection = db["devices"]
        feedback_collection = db["feedback"]
        manufacturers_collection = db["manufacturers"]
        users_collection = db["users"]
        
        # Create indexes
        devices_collection.create_index([
            ("device_name", "text"),
            ("manufacturer_name", "text")
        ], name="device_manufacturer_text")
        
        devices_collection.create_index("manufacturer_name")
        devices_collection.create_index("username")
        
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False

# Initialize connection on import
init_mongo_connection()

def get_mongo_collections():
    """Get MongoDB collections with connection check"""
    if None in [client, db, devices_collection, feedback_collection]:
        if not init_mongo_connection():
            raise Exception("MongoDB connection not available")
    
    return devices_collection, feedback_collection

def store_device_risk_data(device_data: dict):
    """
    Store device risk data in MongoDB
    """
    device_data["created_at"] = datetime.now().isoformat()
    result = devices_collection.insert_one(device_data)
    return str(result.inserted_id)

def update_device_risk_data(device_id: str, update_data: dict):
    """
    Update device risk data
    """
    try:
        result = devices_collection.update_one(
            {"_id": ObjectId(device_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except:
        return False

def query_similar_devices(device_name: str, manufacturer_name: str, n_results: int = 5):
    """Query similar devices from MongoDB using text search"""
    devices_coll, _ = get_mongo_collections()
    
    # Search for similar devices
    results = devices_coll.find(
        {"$text": {"$search": f"{device_name} {manufacturer_name}"}},
        {"score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})]).limit(n_results)
    
    # Process results
    devices = []
    for result in results:
        device_info = {
            "id": result["_id"],
            "device_name": result["device_name"],
            "manufacturer_name": result["manufacturer_name"],
            "risk_class": result["risk_class"],
            "risk_percent": result["risk_percent"],
            "suggested_alternatives": result["suggested_alternatives"],
            "source": result.get("source", "unknown"),
            "username": result.get("username", "unknown"),
            "created_at": result.get("created_at", ""),
            "score": result.get("score", 0)
        }
        devices.append(device_info)
    
    return devices

def get_all_devices():
    """
    Get all devices from MongoDB
    """
    devices = list(devices_collection.find())
    # Convert ObjectId to string for JSON serialization
    for device in devices:
        device["_id"] = str(device["_id"])
        if "feedback" in device:
            for feedback in device["feedback"]:
                if "_id" in feedback:
                    feedback["_id"] = str(feedback["_id"])
    return devices

def get_devices_by_manufacturer(manufacturer_name: str):
    """
    Get devices by manufacturer name
    """
    devices = list(devices_collection.find({"manufacturer_name": manufacturer_name}))
    for device in devices:
        device["_id"] = str(device["_id"])
    return devices

def get_devices_by_username(username: str):
    """
    Get devices by username (for manufacturer dashboard)
    """
    # First get manufacturer details to get company name
    manufacturer = manufacturers_collection.find_one({"username": username})
    if manufacturer:
        company_name = manufacturer.get("company_name", "")
        # Get devices by manufacturer name
        devices = list(devices_collection.find({"manufacturer_name": company_name}))
        for device in devices:
            device["_id"] = str(device["_id"])
        return devices
    return []

def add_feedback_to_device(device_id: str, feedback_data: dict):
    """
    Add feedback to an existing device document
    """
    try:
        result = devices_collection.update_one(
            {"_id": ObjectId(device_id)},
            {"$push": {"feedback": feedback_data}}
        )
        return result.modified_count > 0
    except:
        return False

def get_device_with_feedback(device_id: str):
    """
    Get a device with its feedback
    """
    try:
        device = devices_collection.find_one({"_id": ObjectId(device_id)})
        return device
    except:
        return None

def get_all_feedback():
    """Get all feedback entries from MongoDB"""
    _, feedback_coll = get_mongo_collections()
    
    feedback_entries = []
    for feedback in feedback_coll.find():
        feedback_info = {
            "id": feedback["_id"],
            "device_name": feedback["device_name"],
            "manufacturer_name": feedback["manufacturer_name"],
            "user_rating": feedback["user_rating"],
            "user_feedback": feedback["user_feedback"],
            "predicted_risk": feedback["predicted_risk"],
            "actual_risk": feedback.get("actual_risk", ""),
            "username": feedback.get("username", "unknown"),
            "created_at": feedback.get("created_at", "")
        }
        feedback_entries.append(feedback_info)
    
    return feedback_entries

def get_dashboard_stats(manufacturer_name: str = None):
    """
    Get dashboard statistics
    """
    query = {}
    if manufacturer_name:
        query = {"manufacturer_name": manufacturer_name}
    
    total_predictions = devices_collection.count_documents(query)
    
    # Get risk distribution
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$risk_class", "count": {"$sum": 1}}}
    ]
    risk_distribution = list(devices_collection.aggregate(pipeline))
    
    # Convert to dictionary
    risk_dist_dict = {}
    for item in risk_distribution:
        risk_dist_dict[item["_id"]] = item["count"]
    
    # Get recent devices
    recent_devices = list(devices_collection.find(query).sort("created_at", -1).limit(5))
    for device in recent_devices:
        device["_id"] = str(device["_id"])
    
    return {
        "total_predictions": total_predictions,
        "risk_distribution": risk_dist_dict,
        "recent_devices": recent_devices
    }