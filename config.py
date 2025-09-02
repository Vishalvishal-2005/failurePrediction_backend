from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
DATASET_PATH = BASE_DIR / "realistic_risk_data.csv"   # Put/keep your CSV here
MODEL_DIR = BASE_DIR / "artifacts"
MODEL_DIR.mkdir(exist_ok=True, parents=True)
MODEL_PATH = MODEL_DIR / "risk_model.joblib"
ALT_INDEX_PATH = MODEL_DIR / "alternatives.parquet"

# MongoDB

MONGODB_URI="mongodb+srv://727822tuad019_db_user:medplexity@medplexity.v9qbvpi.mongodb.net/?retryWrites=true&w=majority&appName=MedPlexity"
MONGODB_DB_NAME = "device_risk_db"
TEST_SIZE = 0.2
RANDOM_STATE = 42
CV_FOLDS = 5

# Security
SECRET_KEY = "b70f951f18d50f3f1b34efb3532d6fee331544d840d675dfc3ffbd3ebb86eeab"  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30