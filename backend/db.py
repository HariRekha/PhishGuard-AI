import os
import json
import time
import threading
from config import LOG_FULL_URLS

try:
    import mysql.connector as mysql_connector
except ImportError as exc:
    raise RuntimeError("mysql-connector-python package is required for the database layer") from exc

MYSQL_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "1234"),
    "database": os.getenv("DB_NAME", "url"),
}
PREDICTIONS_TABLE = os.getenv("DB_TABLE", "predictions")

RETRY_ATTEMPTS = int(os.getenv("DB_CONNECT_RETRIES", "5"))
RETRY_DELAY_SECONDS = float(os.getenv("DB_CONNECT_RETRY_DELAY", "1.5"))

_schema_ready = False
_schema_lock = threading.Lock()

def get_connection():
    last_exc = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return mysql_connector.connect(
                host=MYSQL_CONFIG["host"],
                port=MYSQL_CONFIG["port"],
                user=MYSQL_CONFIG["user"],
                password=MYSQL_CONFIG["password"],
                database=MYSQL_CONFIG["database"],
                autocommit=False,
            )
        except mysql_connector.Error as exc:
            last_exc = exc
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Database connection failed after {RETRY_ATTEMPTS} attempts") from last_exc

def init_db():
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {PREDICTIONS_TABLE} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    url TEXT,
                    masked_url TEXT,
                    features_json LONGTEXT,
                    prediction TINYINT,
                    probability DOUBLE,
                    device VARCHAR(255),
                    ip VARCHAR(64),
                    metadata_json LONGTEXT,
                    model_version VARCHAR(128),
                    timestamp BIGINT
                ) ENGINE=InnoDB
                """
            )
            conn.commit()
            _schema_ready = True
        finally:
            cur.close()
            conn.close()

def mask_url(url: str) -> str:
    if LOG_FULL_URLS:
        return url
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        scheme = parsed.scheme + "://" if parsed.scheme else ""
        host = parsed.netloc if parsed.netloc else parsed.path
        return f"{scheme}{host[:40]}... (masked)"
    except Exception:
        return url[:40] + "... (masked)" if len(url) > 50 else url

def insert_prediction(url, features: dict, prediction: int, probability: float, device: str, ip: str, metadata: dict, model_version: str):
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    timestamp = int(time.time())
    features_json = json.dumps(features)
    metadata_json = json.dumps(metadata or {})
    masked = mask_url(url)
    cur.execute(
        f"""
        INSERT INTO {PREDICTIONS_TABLE}
            (url, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            url if LOG_FULL_URLS else masked,
            masked,
            features_json,
            int(prediction),
            float(probability or 0.0),
            device,
            ip,
            metadata_json,
            model_version,
            timestamp,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    cur.close()
    conn.close()
    return row_id

def get_recent(limit=50):
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp
        FROM {PREDICTIONS_TABLE}
        ORDER BY id DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    results = []
    for row in rows:
        results.append(
            {
                "id": int(row[0]),
                "url": row[1],
                "features": json.loads(row[2] or "{}"),
                "prediction": int(row[3]) if row[3] is not None else -1,
                "probability": float(row[4]) if row[4] is not None else 0.0,
                "device": row[5],
                "ip": row[6],
                "metadata": json.loads(row[7] or "{}"),
                "model_version": row[8],
                "timestamp": int(row[9]) if row[9] is not None else 0,
            }
        )
    return results