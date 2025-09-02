# # csv_to_mongodb.py - UPDATED with batch processing
# import pandas as pd
# import json
# from pymongo import MongoClient
# import certifi
# from config import MONGODB_URI, MONGODB_DB_NAME, DATASET_PATH
# from utils import ensure_device_manufacturer_cols, action_to_risk_class, normalize_text
# from datetime import datetime
# import uuid
# import time

# def convert_csv_to_json_and_import():
#     """Convert CSV dataset to JSON and import into MongoDB with batch processing"""
    
#     # Initialize MongoDB connection
#     try:
#         client = MongoClient(
#             MONGODB_URI,
#             tls=True,
#             tlsCAFile=certifi.where(),
#             connectTimeoutMS=60000,  # Increased timeout
#             socketTimeoutMS=60000,
#             serverSelectionTimeoutMS=60000
#         )
#         db = client[MONGODB_DB_NAME]
#         dataset_collection = db["dataset_records"]
#         print("✅ Connected to MongoDB")
#     except Exception as e:
#         print(f"❌ MongoDB connection failed: {e}")
#         return False

#     # Load and process CSV
#     try:
#         print(f"Loading dataset from: {DATASET_PATH}")
#         df = pd.read_csv(DATASET_PATH)
        
#         # Ensure we have the required columns
#         df = ensure_device_manufacturer_cols(df)
        
#         # Convert to JSON records in batches
#         batch_size = 100  # Process in smaller batches
#         total_records = len(df)
#         imported_count = 0
        
#         for i in range(0, total_records, batch_size):
#             batch_df = df.iloc[i:i + batch_size]
#             records = []
            
#             for _, row in batch_df.iterrows():
#                 # Create a unique ID for each record
#                 record_id = str(uuid.uuid4())
                
#                 # Convert row to dictionary
#                 record_data = row.to_dict()
                
#                 # Add metadata and normalized fields
#                 record = {
#                     "_id": record_id,
#                     "original_data": record_data,
#                     "normalized_manufacturer": normalize_text(record_data.get('manufacturer_name', '')),
#                     "normalized_device": normalize_text(record_data.get('device_name', '')),
#                     "import_timestamp": datetime.now().isoformat(),
#                     "source": "csv_import"
#                 }
                
#                 # Add risk classification if available
#                 if "Action_Level" in record_data:
#                     record["risk_class"] = action_to_risk_class(record_data["Action_Level"])
#                     record["risk_label"] = ["Low Risk", "Medium Risk", "High Risk"][record["risk_class"]]
                
#                 records.append(record)
            
#             # Insert batch into MongoDB
#             if records:
#                 try:
#                     result = dataset_collection.insert_many(records, ordered=False)
#                     imported_count += len(result.inserted_ids)
#                     print(f"✅ Imported batch {i//batch_size + 1}: {len(result.inserted_ids)} records")
                    
#                     # Small delay to avoid overwhelming the server
#                     time.sleep(0.1)
                    
#                 except Exception as batch_error:
#                     print(f"⚠️  Batch {i//batch_size + 1} had some errors: {batch_error}")
#                     # Try inserting records one by one for this batch
#                     for record in records:
#                         try:
#                             dataset_collection.insert_one(record)
#                             imported_count += 1
#                         except Exception as single_error:
#                             print(f"❌ Failed to insert single record: {single_error}")
        
#         # Create indexes after all data is imported
#         print("Creating indexes...")
#         dataset_collection.create_index("normalized_manufacturer")
#         dataset_collection.create_index("normalized_device")
#         dataset_collection.create_index([("normalized_manufacturer", "text"), ("normalized_device", "text")])
#         print("✅ Created indexes for better search performance")
        
#         print(f"✅ Successfully imported {imported_count} out of {total_records} records into MongoDB")
#         return True
            
#     except Exception as e:
#         print(f"❌ Error processing CSV: {e}")
#         import traceback
#         traceback.print_exc()
#         return False

# def get_dataset_stats():
#     """Get statistics about the imported dataset"""
#     try:
#         client = MongoClient(
#             MONGODB_URI,
#             tls=True,
#             tlsCAFile=certifi.where(),
#             connectTimeoutMS=30000,
#             socketTimeoutMS=30000
#         )
#         db = client[MONGODB_DB_NAME]
#         dataset_collection = db["dataset_records"]
        
#         # Get total count
#         total_count = dataset_collection.count_documents({})
        
#         # Get risk class distribution
#         risk_distribution = list(dataset_collection.aggregate([
#             {"$group": {"_id": "$risk_label", "count": {"$sum": 1}}}
#         ]))
        
#         # Get manufacturer count
#         manufacturer_count = len(dataset_collection.distinct("normalized_manufacturer"))
        
#         # Get device count
#         device_count = len(dataset_collection.distinct("normalized_device"))
        
#         return {
#             "total_records": total_count,
#             "risk_distribution": risk_distribution,
#             "unique_manufacturers": manufacturer_count,
#             "unique_devices": device_count
#         }
        
#     except Exception as e:
#         print(f"Error getting stats: {e}")
#         return None

# if __name__ == "__main__":
#     print("Starting CSV to MongoDB conversion...")
#     success = convert_csv_to_json_and_import()
    
#     if success:
#         print("\n📊 Dataset Statistics:")
#         stats = get_dataset_stats()
#         if stats:
#             print(f"Total Records: {stats['total_records']}")
#             print(f"Unique Manufacturers: {stats['unique_manufacturers']}")
#             print(f"Unique Devices: {stats['unique_devices']}")
#             print("Risk Distribution:")
#             for item in stats['risk_distribution']:
#                 if item['_id']:  # Skip None values
#                     print(f"  - {item['_id']}: {item['count']}")
#     else:
#         print("Conversion failed")



import pandas as pd
from pymongo import MongoClient
from config import MONGODB_URI, MONGODB_DB_NAME, DATASET_PATH  # reuse your config

def upload_csv_to_mongo():
    # 1. Read CSV
    df = pd.read_csv(DATASET_PATH)

    # 🔧 2. Replace NaN/NaT with None (MongoDB-compatible)
    df = df.where(pd.notnull(df), None)

    # 3. Connect to MongoDB
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]

    # 4. Choose collection (create if not exists)
    collection = db["dataset_records"]

    # 5. Convert DataFrame → dict and insert
    data = df.to_dict(orient="records")
    if data:
        collection.insert_many(data, ordered=False)
        print(f"✅ Uploaded {len(data)} records to MongoDB collection: {collection.name}")
    else:
        print("⚠️ No data found in CSV.")

    client.close()

if __name__ == "__main__":
    upload_csv_to_mongo()