# test_connection.py
from pymongo import MongoClient
import certifi
from config import MONGODB_URI

def test_connection():
    try:
        # Method 1: With certifi
        client = MongoClient(
            MONGODB_URI,
            tls=True,
            tlsCAFile=certifi.where(),
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        print("Testing connection with certifi...")
        client.admin.command('ping')
        print("✅ Connection successful with certifi!")
        return True
        
    except Exception as e:
        print(f"❌ Connection with certifi failed: {e}")
        
        # Method 2: Without TLS (for development)
        try:
            print("Trying without TLS...")
            client = MongoClient(
                MONGODB_URI.replace("mongodb+srv://", "mongodb://").replace("?retryWrites", "&retryWrites"),
                tls=False,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000
            )
            client.admin.command('ping')
            print("✅ Connection successful without TLS!")
            return True
        except Exception as e2:
            print(f"❌ Connection without TLS also failed: {e2}")
            return False

if __name__ == "__main__":
    test_connection()