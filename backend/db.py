import os
import json
import time
import threading
from config import LOG_FULL_URLS
from werkzeug.security import generate_password_hash, check_password_hash

from config import ADMIN_USERNAME, ADMIN_PASSWORD, USER_USERNAME, USER_PASSWORD

try:
    import bcrypt
except ImportError as exc:
    raise RuntimeError("bcrypt package is required for secure password hashing") from exc


def _hash_password(password: str) -> str:
    pw = (password or "").encode("utf-8")
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def _is_bcrypt_hash(password_hash: str) -> bool:
    ph = (password_hash or "").strip()
    return ph.startswith("$2a$") or ph.startswith("$2b$") or ph.startswith("$2y$")


def _verify_password(password_hash: str, password: str) -> bool:
    ph = (password_hash or "").strip()
    if not ph:
        return False
    if _is_bcrypt_hash(ph):
        try:
            return bcrypt.checkpw((password or "").encode("utf-8"), ph.encode("utf-8"))
        except Exception:
            return False
    # Legacy support (werkzeug hashes): allow verify then upgrade on success
    try:
        return check_password_hash(ph, password)
    except Exception:
        return False

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
PERMISSIONS_TABLE = os.getenv("DB_PERMISSIONS_TABLE", "user_permissions")
USERS_TABLE = os.getenv("DB_USERS_TABLE", "users")

RETRY_ATTEMPTS = int(os.getenv("DB_CONNECT_RETRIES", "5"))
RETRY_DELAY_SECONDS = float(os.getenv("DB_CONNECT_RETRY_DELAY", "1.5"))

_schema_ready = False
_schema_lock = threading.Lock()


def _connect(with_database: bool = True):
    cfg = {
        "host": MYSQL_CONFIG["host"],
        "port": MYSQL_CONFIG["port"],
        "user": MYSQL_CONFIG["user"],
        "password": MYSQL_CONFIG["password"],
        "autocommit": False,
    }
    if with_database:
        cfg["database"] = MYSQL_CONFIG["database"]
    return mysql_connector.connect(**cfg)


def _ensure_database_exists():
    """Create database if it does not exist.

    This prevents the common 'Unknown database' / 'no table' startup errors.
    """
    conn = _connect(with_database=False)
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

def get_connection():
    last_exc = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            try:
                return _connect(with_database=True)
            except mysql_connector.Error as exc:
                # 1049 = ER_BAD_DB_ERROR (unknown database)
                if getattr(exc, "errno", None) == 1049:
                    _ensure_database_exists()
                    return _connect(with_database=True)
                raise
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
                    owner_user_id INT,
                    owner_username VARCHAR(128),
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

            # Migrate predictions: add owner_user_id if needed
            cur.execute(
                """
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='owner_user_id'
                """,
                (MYSQL_CONFIG["database"], PREDICTIONS_TABLE),
            )
            has_owner_user_id = int(cur.fetchone()[0]) > 0
            if not has_owner_user_id:
                cur.execute(f"ALTER TABLE {PREDICTIONS_TABLE} ADD COLUMN owner_user_id INT")

            # Migrate existing tables to include owner_username if needed
            cur.execute(
                """
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='owner_username'
                """,
                (MYSQL_CONFIG["database"], PREDICTIONS_TABLE),
            )
            has_owner = int(cur.fetchone()[0]) > 0
            if not has_owner:
                cur.execute(f"ALTER TABLE {PREDICTIONS_TABLE} ADD COLUMN owner_username VARCHAR(128)")

            # Helpful indexes
            try:
                cur.execute(f"CREATE INDEX idx_owner_ts ON {PREDICTIONS_TABLE} (owner_username, timestamp)")
            except mysql_connector.Error:
                # index may already exist
                pass

            try:
                cur.execute(f"CREATE INDEX idx_owner_user_ts ON {PREDICTIONS_TABLE} (owner_user_id, timestamp)")
            except mysql_connector.Error:
                pass

            # Permissions table
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {PERMISSIONS_TABLE} (
                    username VARCHAR(128) PRIMARY KEY,
                    can_delete_own_logs TINYINT DEFAULT 0,
                    updated_at BIGINT
                ) ENGINE=InnoDB
                """
            )

            # Users table (proper auth)
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    username VARCHAR(128) UNIQUE,
                    password_hash VARCHAR(255),
                    role VARCHAR(16) DEFAULT 'user',
                    can_delete_own_logs TINYINT DEFAULT 0,
                    last_login_ip VARCHAR(64),
                    last_login_device VARCHAR(255),
                    created_at BIGINT,
                    last_login_at BIGINT
                ) ENGINE=InnoDB
                """
            )

            # Migrate users table columns for older installs
            def _ensure_user_col(col_name: str, ddl: str):
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
                    """,
                    (MYSQL_CONFIG["database"], USERS_TABLE, col_name),
                )
                if int(cur.fetchone()[0]) == 0:
                    cur.execute(f"ALTER TABLE {USERS_TABLE} ADD COLUMN {ddl}")

            _ensure_user_col("email", "email VARCHAR(255) UNIQUE")
            _ensure_user_col("last_login_ip", "last_login_ip VARCHAR(64)")
            _ensure_user_col("last_login_device", "last_login_device VARCHAR(255)")

            # Back-compat: if old columns exist, keep them but prefer new names
            # (Some prior versions used last_ip/last_device)

            # Backfill email for existing rows (keep login stable)
            try:
                cur.execute(
                    f"UPDATE {USERS_TABLE} SET email=LOWER(CONCAT(username,'@local')) WHERE (email IS NULL OR email='') AND username IS NOT NULL AND username<>''"
                )
            except Exception:
                pass

            def _has_user_col(col_name: str) -> bool:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
                    """,
                    (MYSQL_CONFIG["database"], USERS_TABLE, col_name),
                )
                return int(cur.fetchone()[0]) > 0

            # Copy legacy last_ip/last_device if present
            try:
                if _has_user_col("last_ip"):
                    cur.execute(
                        f"UPDATE {USERS_TABLE} SET last_login_ip=last_ip WHERE (last_login_ip IS NULL OR last_login_ip='') AND last_ip IS NOT NULL AND last_ip<>''"
                    )
                if _has_user_col("last_device"):
                    cur.execute(
                        f"UPDATE {USERS_TABLE} SET last_login_device=last_device WHERE (last_login_device IS NULL OR last_login_device='') AND last_device IS NOT NULL AND last_device<>''"
                    )
            except Exception:
                pass

            # Bootstrap: create initial admin/user if users table is empty
            cur.execute(f"SELECT COUNT(*) FROM {USERS_TABLE}")
            user_count = int(cur.fetchone()[0] or 0)
            if user_count == 0:
                now = int(time.time())
                def _default_email(u: str) -> str:
                    u = (u or "").strip()
                    return u if "@" in u else f"{u}@local"

                cur.execute(
                    f"INSERT INTO {USERS_TABLE} (email, username, password_hash, role, can_delete_own_logs, created_at, last_login_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (_default_email(ADMIN_USERNAME), ADMIN_USERNAME, _hash_password(ADMIN_PASSWORD), "admin", 1, now, now),
                )
                cur.execute(
                    f"INSERT INTO {USERS_TABLE} (email, username, password_hash, role, can_delete_own_logs, created_at, last_login_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (_default_email(USER_USERNAME), USER_USERNAME, _hash_password(USER_PASSWORD), "user", 0, now, now),
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

def insert_prediction(url, features: dict, prediction: int, probability: float, device: str, ip: str, metadata: dict, model_version: str, owner_username: str = "anonymous", owner_user_id: int | None = None):
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
            (owner_user_id, owner_username, url, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            int(owner_user_id) if owner_user_id is not None else None,
            owner_username,
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
        SELECT id, owner_user_id, owner_username, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp
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
                "owner_user_id": int(row[1]) if row[1] is not None else None,
                "owner_username": row[2] or "anonymous",
                "url": row[3],
                "features": json.loads(row[4] or "{}"),
                "prediction": int(row[5]) if row[5] is not None else -1,
                "probability": float(row[6]) if row[6] is not None else 0.0,
                "device": row[7],
                "ip": row[8],
                "metadata": json.loads(row[9] or "{}"),
                "model_version": row[10],
                "timestamp": int(row[11]) if row[11] is not None else 0,
            }
        )
    return results


def clear_logs() -> int:
    """Delete all rows from the predictions table.

    Returns the number of deleted rows when available (may be -1 depending on driver).
    """
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"DELETE FROM {PREDICTIONS_TABLE}")
        deleted = cur.rowcount
        conn.commit()
        return int(deleted) if deleted is not None else -1
    finally:
        cur.close()
        conn.close()


def delete_logs_for_user(username: str) -> int:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"DELETE FROM {PREDICTIONS_TABLE} WHERE owner_username=%s", (username,))
        deleted = cur.rowcount
        conn.commit()
        return int(deleted) if deleted is not None else -1
    finally:
        cur.close()
        conn.close()


def _resolve_user(identifier):
    s = str(identifier or "").strip()
    if not s:
        return None
    if isinstance(identifier, int) or s.isdigit():
        return get_user_by_id(int(s))
    if "@" in s:
        return get_user_by_email(s.lower())
    return get_user(s)


def set_user_can_delete_own(user_id_or_login, can_delete: bool) -> None:
    init_db()
    user = _resolve_user(user_id_or_login)
    if not user:
        raise ValueError("user not found")
    username = user.get("username") or user.get("email")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Mirror into users table (source of truth)
        cur.execute(
            f"UPDATE {USERS_TABLE} SET can_delete_own_logs=%s WHERE id=%s",
            (1 if can_delete else 0, int(user.get("id"))),
        )
        cur.execute(
            f"""
            INSERT INTO {PERMISSIONS_TABLE} (username, can_delete_own_logs, updated_at)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE can_delete_own_logs=VALUES(can_delete_own_logs), updated_at=VALUES(updated_at)
            """,
            (username, 1 if can_delete else 0, int(time.time())),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_user_can_delete_own(user_id_or_login) -> bool:
    init_db()
    user = _resolve_user(user_id_or_login)
    if user and "can_delete_own_logs" in user:
        return bool(user.get("can_delete_own_logs"))
    username = None
    if user:
        username = user.get("username") or user.get("email")
    else:
        username = str(user_id_or_login or "").strip()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT can_delete_own_logs FROM {PERMISSIONS_TABLE} WHERE username=%s",
            (username,),
        )
        row = cur.fetchone()
        return bool(int(row[0])) if row else False
    finally:
        cur.close()
        conn.close()


def get_user_by_id(user_id: int):
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT id, email, username, password_hash, role, can_delete_own_logs, last_login_ip, last_login_device, created_at, last_login_at FROM {USERS_TABLE} WHERE id=%s",
            (int(user_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "email": row[1],
            "username": row[2],
            "password_hash": row[3],
            "role": row[4] or "user",
            "can_delete_own_logs": bool(int(row[5] or 0)),
            "last_login_ip": row[6],
            "last_login_device": row[7],
            "created_at": int(row[8] or 0),
            "last_login_at": int(row[9] or 0),
        }
    finally:
        cur.close()
        conn.close()


def get_user(username: str):
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT id, email, username, password_hash, role, can_delete_own_logs, last_login_ip, last_login_device, created_at, last_login_at FROM {USERS_TABLE} WHERE username=%s",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "email": row[1],
            "username": row[2],
            "password_hash": row[3],
            "role": row[4] or "user",
            "can_delete_own_logs": bool(int(row[5] or 0)),
            "last_login_ip": row[6],
            "last_login_device": row[7],
            "created_at": int(row[8] or 0),
            "last_login_at": int(row[9] or 0),
        }
    finally:
        cur.close()
        conn.close()


def get_user_by_email(email: str):
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT id, email, username, password_hash, role, can_delete_own_logs, last_login_ip, last_login_device, created_at, last_login_at FROM {USERS_TABLE} WHERE email=%s",
            ((email or "").strip().lower(),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "email": row[1],
            "username": row[2],
            "password_hash": row[3],
            "role": row[4] or "user",
            "can_delete_own_logs": bool(int(row[5] or 0)),
            "last_login_ip": row[6],
            "last_login_device": row[7],
            "created_at": int(row[8] or 0),
            "last_login_at": int(row[9] or 0),
        }
    finally:
        cur.close()
        conn.close()


def verify_user_password(login: str, password: str) -> dict | None:
    login = (login or "").strip()
    user = get_user_by_email(login.lower()) if "@" in login else get_user(login)
    if not user:
        return None
    if not user.get("password_hash"):
        return None
    if _verify_password(user["password_hash"], password):
        # If legacy hash, upgrade in-place to bcrypt
        if not _is_bcrypt_hash(user["password_hash"]):
            try:
                set_user_password(user.get("id"), password)
                user = get_user_by_id(int(user.get("id"))) or user
            except Exception:
                pass
        return user
    return None


def create_user(email: str, password: str, role: str = "user", username: str | None = None) -> None:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        now = int(time.time())
        email_norm = (email or "").strip().lower()
        username_val = (username or "").strip() or email_norm
        cur.execute(
            f"INSERT INTO {USERS_TABLE} (email, username, password_hash, role, can_delete_own_logs, created_at, last_login_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (email_norm, username_val, _hash_password(password), role, 0, now, now),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def list_users():
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT id, email, username, role, can_delete_own_logs, last_login_ip, last_login_device, created_at, last_login_at FROM {USERS_TABLE} ORDER BY email ASC"
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "id": int(r[0]),
                "email": r[1],
                "username": r[2],
                "role": r[3] or "user",
                "can_delete_own_logs": bool(int(r[4] or 0)),
                "last_login_ip": r[5],
                "last_login_device": r[6],
                "created_at": int(r[7] or 0),
                "last_login_at": int(r[8] or 0),
            })
        return out
    finally:
        cur.close()
        conn.close()


def set_user_role(user_id_or_username, role: str) -> None:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        if isinstance(user_id_or_username, int) or str(user_id_or_username).isdigit():
            cur.execute(f"UPDATE {USERS_TABLE} SET role=%s WHERE id=%s", (role, int(user_id_or_username)))
        else:
            cur.execute(f"UPDATE {USERS_TABLE} SET role=%s WHERE username=%s", (role, str(user_id_or_username)))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def set_user_password(user_id_or_username, password: str) -> None:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        new_hash = _hash_password(password)
        if isinstance(user_id_or_username, int) or str(user_id_or_username).isdigit():
            cur.execute(
                f"UPDATE {USERS_TABLE} SET password_hash=%s WHERE id=%s",
                (new_hash, int(user_id_or_username)),
            )
        else:
            cur.execute(
                f"UPDATE {USERS_TABLE} SET password_hash=%s WHERE username=%s",
                (new_hash, str(user_id_or_username)),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def record_user_login(user_id_or_username, ip: str, device: str) -> None:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    try:
        if isinstance(user_id_or_username, int) or str(user_id_or_username).isdigit():
            cur.execute(
                f"UPDATE {USERS_TABLE} SET last_login_ip=%s, last_login_device=%s, last_login_at=%s WHERE id=%s",
                (ip, device, int(time.time()), int(user_id_or_username)),
            )
        else:
            cur.execute(
                f"UPDATE {USERS_TABLE} SET last_login_ip=%s, last_login_device=%s, last_login_at=%s WHERE username=%s",
                (ip, device, int(time.time()), str(user_id_or_username)),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_recent_for_user(username: str, limit: int = 50):
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, owner_user_id, owner_username, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp
        FROM {PREDICTIONS_TABLE}
        WHERE owner_username=%s
        ORDER BY id DESC
        LIMIT %s
        """,
        (username, int(limit)),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    results = []
    for row in rows:
        results.append(
            {
                "id": int(row[0]),
                "owner_user_id": int(row[1]) if row[1] is not None else None,
                "owner_username": row[2] or "anonymous",
                "url": row[3],
                "features": json.loads(row[4] or "{}"),
                "prediction": int(row[5]) if row[5] is not None else -1,
                "probability": float(row[6]) if row[6] is not None else 0.0,
                "device": row[7],
                "ip": row[8],
                "metadata": json.loads(row[9] or "{}"),
                "model_version": row[10],
                "timestamp": int(row[11]) if row[11] is not None else 0,
            }
        )
    return results


def get_recent_for_user_id(user_id: int, limit: int = 50):
    init_db()
    user = get_user_by_id(int(user_id))
    legacy_usernames = []
    if user:
        if user.get("email"):
            legacy_usernames.append(str(user.get("email")))
        if user.get("username") and str(user.get("username")) not in legacy_usernames:
            legacy_usernames.append(str(user.get("username")))
    conn = get_connection()
    cur = conn.cursor()
    if legacy_usernames:
        cur.execute(
            f"""
            SELECT id, owner_user_id, owner_username, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp
            FROM {PREDICTIONS_TABLE}
            WHERE owner_user_id=%s OR owner_username IN (%s, %s)
            ORDER BY id DESC
            LIMIT %s
            """,
            (int(user_id), legacy_usernames[0], legacy_usernames[-1], int(limit)),
        )
    else:
        cur.execute(
            f"""
            SELECT id, owner_user_id, owner_username, masked_url, features_json, prediction, probability, device, ip, metadata_json, model_version, timestamp
            FROM {PREDICTIONS_TABLE}
            WHERE owner_user_id=%s
            ORDER BY id DESC
            LIMIT %s
            """,
            (int(user_id), int(limit)),
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    results = []
    for row in rows:
        results.append(
            {
                "id": int(row[0]),
                "owner_user_id": int(row[1]) if row[1] is not None else None,
                "owner_username": row[2] or "anonymous",
                "url": row[3],
                "features": json.loads(row[4] or "{}"),
                "prediction": int(row[5]) if row[5] is not None else -1,
                "probability": float(row[6]) if row[6] is not None else 0.0,
                "device": row[7],
                "ip": row[8],
                "metadata": json.loads(row[9] or "{}"),
                "model_version": row[10],
                "timestamp": int(row[11]) if row[11] is not None else 0,
            }
        )
    return results


def delete_logs_for_user_id(user_id: int) -> int:
    init_db()
    user = get_user_by_id(int(user_id))
    legacy_usernames = []
    if user:
        if user.get("email"):
            legacy_usernames.append(str(user.get("email")))
        if user.get("username") and str(user.get("username")) not in legacy_usernames:
            legacy_usernames.append(str(user.get("username")))
    conn = get_connection()
    cur = conn.cursor()
    try:
        if legacy_usernames:
            cur.execute(
                f"DELETE FROM {PREDICTIONS_TABLE} WHERE owner_user_id=%s OR owner_username IN (%s, %s)",
                (int(user_id), legacy_usernames[0], legacy_usernames[-1]),
            )
        else:
            cur.execute(f"DELETE FROM {PREDICTIONS_TABLE} WHERE owner_user_id=%s", (int(user_id),))
        deleted = cur.rowcount
        conn.commit()
        return int(deleted) if deleted is not None else -1
    finally:
        cur.close()
        conn.close()