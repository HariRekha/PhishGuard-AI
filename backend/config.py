import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model"
MODEL_FILE = MODEL_DIR / "model.joblib"
DB_FILE = BASE_DIR / "predictions.db"
ADMIN_TOKEN = os.getenv("X_ADMIN_TOKEN", "")

# Simple role-based auth (for demo/dev)
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "604800"))  # 7 days

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

USER_USERNAME = os.getenv("USER_USERNAME", "user")
USER_PASSWORD = os.getenv("USER_PASSWORD", "user123")
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if origin.strip()
]
# Add localhost/127.0.0.1 variants to reduce CORS mismatch risk
def _with_localhost_variants(origins):
    out = set(origins)
    try:
        from urllib.parse import urlparse
        for o in list(origins):
            u = urlparse(o)
            if u.scheme and u.netloc:
                if u.hostname == "localhost":
                    out.add(o.replace("localhost", "127.0.0.1"))
                if u.hostname == "127.0.0.1":
                    out.add(o.replace("127.0.0.1", "localhost"))
    except Exception:
        pass
    return list(out)

FRONTEND_ORIGINS = _with_localhost_variants(FRONTEND_ORIGINS)
LOG_FULL_URLS = os.getenv("LOG_FULL_URLS", "false").lower() in ("1", "true", "yes")
MAX_URL_LENGTH = int(os.getenv("MAX_URL_LENGTH", "2000"))
SUSPICIOUS_TOKENS = os.getenv("SUSPICIOUS_TOKENS", "login,secure,bank,verify,update,account").split(",")
DEFAULT_DATA_PATH = BASE_DIR / "sample_data" / "sample_phishing.csv"
