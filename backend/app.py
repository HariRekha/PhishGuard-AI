import os
import time
import hmac
from importlib import import_module
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from features import extract_features, features_schema
from config import (
    MODEL_FILE,
    ADMIN_TOKEN,
    FRONTEND_ORIGINS,
    MAX_URL_LENGTH,
    DEFAULT_DATA_PATH,
    AUTH_SECRET,
    AUTH_TOKEN_TTL_SECONDS,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)
import joblib
from db import (
    insert_prediction,
    get_recent,
    get_recent_for_user,
    get_recent_for_user_id,
    clear_logs,
    delete_logs_for_user,
    delete_logs_for_user_id,
    set_user_can_delete_own,
    get_user_can_delete_own,
    verify_user_password,
    record_user_login,
    list_users,
    create_user,
    set_user_role,
    set_user_password,
    get_user_by_id,
    get_user_by_email,
)
from pathlib import Path
from sklearn.feature_extraction import DictVectorizer  # added


def _get_client_ip(req) -> str:
    """Best-effort client IP.

    Note: In Docker / reverse proxies, configure the proxy to pass X-Forwarded-For.
    """
    xff = (req.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        # First IP in the chain is the original client
        return xff.split(",")[0].strip()
    xri = (req.headers.get("X-Real-IP") or "").strip()
    if xri:
        return xri
    return (req.remote_addr or "").strip()

def _device_from_user_agent(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if not ua:
        return "unknown"

    # OS / device
    if "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_name = "iOS"
    elif "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    # Browser (very lightweight heuristics)
    if "edg/" in ua or "edge" in ua:
        browser = "Edge"
    elif "chrome" in ua and "safari" in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    else:
        browser = "Browser"

    return f"{os_name} • {browser}"

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": FRONTEND_ORIGINS,
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-ADMIN-TOKEN", "Authorization"],
    }
})

_AUTH = URLSafeTimedSerializer(AUTH_SECRET, salt="phishing-auth")


def _make_token(user_id: int, email: str, role: str, username: str | None = None) -> str:
    return _AUTH.dumps({"uid": int(user_id), "e": email, "u": username or email, "r": role})


def _get_bearer_token(req) -> str:
    auth = (req.headers.get("Authorization") or "").strip()
    if not auth:
        return ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _require_auth(required_role: str | None = None) -> dict:
    """Return auth context or abort(401/403)."""
    token = _get_bearer_token(request)
    if not token:
        abort(401)
    try:
        payload = _AUTH.loads(token, max_age=AUTH_TOKEN_TTL_SECONDS)
    except SignatureExpired:
        return abort(401)
    except BadSignature:
        return abort(401)

    user_id = payload.get("uid")
    email = str(payload.get("e") or "")
    username = str(payload.get("u") or email or "")
    role = str(payload.get("r") or "")
    if user_id is None or role not in ("admin", "user"):
        return abort(401)
    if required_role and role != required_role:
        return abort(403)
    return {"user_id": int(user_id), "email": email, "username": username, "role": role}


def _is_admin_request() -> bool:
    # Backward compat: allow existing admin token header (dev/demo)
    header_token = request.headers.get("X-ADMIN-TOKEN", "")
    if ADMIN_TOKEN and header_token and hmac.compare_digest(header_token, ADMIN_TOKEN):
        return True

    # New: bearer token with admin role
    try:
        ctx = _require_auth(required_role="admin")
        return bool(ctx)
    except Exception:
        return False

MODEL = None
MODEL_META = {"model_version": "none"}
_AUTO_TRAIN_ATTEMPTED = False

def _load_train_model():
    try:
        return import_module("train").train_model
    except MemoryError as exc:
        app.logger.error("Importing train module failed: %s", exc)
        raise

def _is_valid_pipeline(model) -> bool:
    """Model must be a sklearn Pipeline with a DictVectorizer named 'vectorizer'."""
    try:
        ns = getattr(model, "named_steps", None)
        return bool(ns and isinstance(ns.get("vectorizer"), DictVectorizer))
    except Exception:
        return False

def _try_auto_train():
    """Attempt a one-time auto-train using DEFAULT_DATA_PATH, then reload the model."""
    global _AUTO_TRAIN_ATTEMPTED
    if _AUTO_TRAIN_ATTEMPTED:
        return
    if not DEFAULT_DATA_PATH.exists():
        return
    _AUTO_TRAIN_ATTEMPTED = True
    try:
        train_model = _load_train_model()
        app.logger.info("Attempting auto-train due to missing/incompatible model...")
        train_model(str(DEFAULT_DATA_PATH), raise_errors=False)
    except MemoryError:
        app.logger.warning("Auto-train skipped due to low memory")
    except Exception as exc:
        app.logger.warning("Auto-train failed: %s", exc)

def load_model():
    global MODEL, MODEL_META, _AUTO_TRAIN_ATTEMPTED
    p = Path(MODEL_FILE)
    if not p.exists():
        _try_auto_train()
        if not p.exists():
            MODEL = None
            MODEL_META = {"model_version": "none"}
            return
    obj = joblib.load(p)
    MODEL = obj.get("pipeline") if isinstance(obj, dict) else obj
    MODEL_META = obj.get("meta", {"model_version": p.stat().st_mtime})
    # Log model version and accuracy when loaded
    app.logger.info(
        "Model loaded. version=%s accuracy=%s",
        str(MODEL_META.get("model_version")),
        str(MODEL_META.get("accuracy"))
    )
    if not _is_valid_pipeline(MODEL):
        app.logger.warning(
            "Loaded model is not a Pipeline[DictVectorizer -> Estimator]. "
            "Predictions may fail. Retrain via POST /train to generate a compatible model."
        )
        # Try to recover automatically once
        _try_auto_train()
        # Reload if a new model was produced
        if p.exists():
            try:
                obj = joblib.load(p)
                MODEL = obj.get("pipeline") if isinstance(obj, dict) else obj
                MODEL_META = obj.get("meta", {"model_version": p.stat().st_mtime})
            except Exception as exc:
                app.logger.warning("Reload after auto-train failed: %s", exc)

load_model()

@app.route("/health", methods=["GET"])
def health():
    has_register_route = False
    try:
        has_register_route = any(r.rule == "/auth/register" for r in app.url_map.iter_rules())
    except Exception:
        has_register_route = False
    return jsonify({
        "status": "ok",
        "model_loaded": MODEL is not None,
        "model_version": MODEL_META.get("model_version"),
        "model_compatible": bool(_is_valid_pipeline(MODEL)) if MODEL is not None else False,
        "model_accuracy": MODEL_META.get("accuracy"),  # added
        "has_register_route": bool(has_register_route),
    })

@app.route("/features/schema", methods=["GET"])
def schema():
    return jsonify(features_schema())


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    login = str(data.get("email") or data.get("username") or "")
    password = str(data.get("password") or "")
    if not login or not password:
        return jsonify({"error": "missing email/password"}), 400

    # Prefer DB-backed users; fall back to env admin credentials if DB is unreachable.
    role = None
    can_delete_own = False
    user_id = None
    email = ""
    username = ""
    try:
        user = verify_user_password(login, password)
        if not user:
            return jsonify({"error": "invalid credentials"}), 401
        role = user.get("role") or "user"
        can_delete_own = bool(user.get("can_delete_own_logs"))
        user_id = int(user.get("id"))
        email = str(user.get("email") or "")
        username = str(user.get("username") or "")
        try:
            record_user_login(
                user_id,
                _get_client_ip(request),
                _device_from_user_agent(request.headers.get("User-Agent", "")),
            )
        except Exception:
            pass
    except Exception:
        if hmac.compare_digest(login, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD):
            role = "admin"
            can_delete_own = True
            user_id = -1
            email = f"{ADMIN_USERNAME}@local"
            username = ADMIN_USERNAME
        else:
            return jsonify({"error": "invalid credentials"}), 401

    token = _make_token(user_id=user_id, email=email or login, role=role, username=username or login)
    if role == "admin":
        can_delete_own = True
    return jsonify({
        "token": token,
        "role": role,
        "user_id": user_id,
        "email": email or login,
        "username": username or login,
        "expires_in": AUTH_TOKEN_TTL_SECONDS,
        "can_delete_own_logs": bool(can_delete_own),
    })


@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    if not email or "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    if not password or len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    try:
        existing = get_user_by_email(email)
        if existing:
            return jsonify({"error": "email already registered"}), 409
        create_user(email, password, role="user", username=email)
        return jsonify({"status": "ok"}), 201
    except Exception as exc:
        app.logger.error("Register failed: %s", exc)
        return jsonify({"error": "failed to register"}), 400


@app.route("/auth/me", methods=["GET"])
def auth_me():
    ctx = _require_auth(required_role=None)
    if ctx.get("role") == "admin":
        ctx["can_delete_own_logs"] = True
    else:
        ctx["can_delete_own_logs"] = bool(get_user_can_delete_own(ctx.get("user_id")))
    return jsonify(ctx)


@app.route("/client-info", methods=["GET"])
def client_info():
    ua = request.headers.get("User-Agent", "")
    return jsonify({
        "ip": _get_client_ip(request),
        "device": _device_from_user_agent(ua),
        "user_agent": ua,
    })

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    if not data or "url" not in data:
        return jsonify({"error": "missing 'url' in payload"}), 400
    url = str(data.get("url"))[:MAX_URL_LENGTH]
    # Always derive client info server-side; do not trust client-provided device/ip
    ua = request.headers.get("User-Agent", "")
    device = _device_from_user_agent(ua)
    ip = _get_client_ip(request)
    metadata = data.get("metadata", {}) or {}
    metadata.setdefault("user_agent", ua)
    metadata.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    if len(url) > MAX_URL_LENGTH:
        return jsonify({"error": "url too long"}), 400
    features = extract_features(url)
    # If user is logged in, attach ownership to the log entry; otherwise keep anonymous
    owner_username = "anonymous"
    owner_user_id = None
    try:
        token = _get_bearer_token(request)
        if token:
            ctx = _require_auth(required_role=None)
            owner_username = ctx.get("email") or ctx.get("username") or "anonymous"
            owner_user_id = ctx.get("user_id")
    except Exception:
        owner_username = "anonymous"
        owner_user_id = None
    if MODEL is None:
        try:
            log_id = insert_prediction(
                url,
                features,
                prediction=-1,
                probability=-1.0,
                device=device,
                ip=ip,
                metadata=metadata,
                model_version=str(MODEL_META.get("model_version")),
                owner_username=owner_username,
                owner_user_id=owner_user_id,
            )
        except Exception as exc:
            app.logger.warning("Failed to log prediction (model missing): %s", exc)
            log_id = None
        return jsonify({
            "prediction": "model_not_loaded",
            "probability": None,
            "features": features,
            "device": device,
            "ip": ip,
            "model_version": MODEL_META.get("model_version"),
            "model_accuracy": MODEL_META.get("accuracy"),  # added
            "log_id": log_id,
            "message": "No trained model available. Train model via POST /train."
        }), 200
    # New: validate model compatibility before calling predict
    if not _is_valid_pipeline(MODEL):
        return jsonify({
            "error": "incompatible model file: expected a sklearn Pipeline with a DictVectorizer step named 'vectorizer'. Retrain the backend via POST /train.",
            "error_type": "ModelIncompatibleError",
            "model_type": str(type(MODEL)),
            "model_version": MODEL_META.get("model_version"),
            "remedy": "Trigger retraining from the UI or call POST /train; ensure new model overwrites the old file."
        }), 500
    try:
        pred = MODEL.predict([features])[0]
        proba = float(MODEL.predict_proba([features])[0][1]) if hasattr(MODEL, "predict_proba") else None
    except Exception as e:
        import traceback
        return jsonify({
            "error": f"model prediction failed: {str(e)}",
            "error_type": e.__class__.__name__,
            "traceback": traceback.format_exc(),
        }), 500
    label = "phishing" if int(pred) == 1 else "legitimate"
    try:
        log_id = insert_prediction(
            url,
            features,
            prediction=int(pred),
            probability=proba or 0.0,
            device=device,
            ip=ip,
            metadata=metadata,
            model_version=str(MODEL_META.get("model_version")),
            owner_username=owner_username,
            owner_user_id=owner_user_id,
        )
    except Exception as exc:
        app.logger.warning("Failed to log prediction: %s", exc)
        log_id = None
    return jsonify({
        "prediction": label,
        "probability": proba,
        "features": features,
        "device": device,
        "ip": ip,
        "model_version": MODEL_META.get("model_version"),
        "model_accuracy": MODEL_META.get("accuracy"),  # added
        "log_id": log_id
    })

@app.route("/train", methods=["POST"])
def train_endpoint():
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    data_path = data.get("data_path")
    grid = data.get("grid", False)
    label_column = data.get("label_column", "label")
    try:
        train_model = _load_train_model()
    except MemoryError:
        return jsonify({"error": "insufficient memory to import training pipeline"}), 500
    try:
        # Call training with structured-error mode
        result = train_model(data_path, perform_gridsearch=grid, label_column=label_column, raise_errors=False)
        # If training returned an error payload, propagate it clearly
        if isinstance(result, dict) and "error" in result:
            status = 400 if result.get("error_type") in ("FileNotFoundError", "ValueError") else 500
            return jsonify({
                "error": result.get("error"),
                "error_type": result.get("error_type"),
                "traceback": result.get("traceback"),
            }), status
        load_model()
        return jsonify({"status": "trained", "meta": result.get("meta", {}), "test_predictions_csv": result.get("test_predictions")})
    except Exception as e:
        return jsonify({"error": f"training failed: {str(e)}"}), 500

@app.route("/logs", methods=["GET", "DELETE"])
def logs():
    if request.method == "DELETE":
        # Admin only: clear all logs
        if not _is_admin_request():
            return jsonify({"error": "unauthorized"}), 401
        try:
            user_id_filter = (request.args.get("user_id") or "").strip()
            username_filter = (request.args.get("username") or "").strip()
            if user_id_filter:
                deleted = delete_logs_for_user_id(int(user_id_filter))
                return jsonify({"status": "cleared", "deleted": deleted, "scope": "user_id", "user_id": int(user_id_filter)})
            if username_filter:
                deleted = delete_logs_for_user(username_filter)
                return jsonify({"status": "cleared", "deleted": deleted, "scope": "user", "username": username_filter})
            deleted = clear_logs()
            return jsonify({"status": "cleared", "deleted": deleted, "scope": "all"})
        except Exception as exc:
            app.logger.error("Clearing logs failed: %s", exc)
            return jsonify({"error": "database_unavailable"}), 503

    # GET requires any authenticated user
    ctx = _require_auth(required_role=None)
    limit = int(request.args.get("limit", 50))
    try:
        user_id_filter = (request.args.get("user_id") or "").strip()
        username_filter = (request.args.get("username") or "").strip()
        if ctx.get("role") == "admin":
            if user_id_filter:
                return jsonify(get_recent_for_user_id(int(user_id_filter), limit=limit))
            if username_filter:
                return jsonify(get_recent_for_user(username_filter, limit=limit))
            return jsonify(get_recent(limit=limit))
        if ctx.get("user_id") is not None:
            return jsonify(get_recent_for_user_id(int(ctx.get("user_id")), limit=limit))
        return jsonify(get_recent_for_user(ctx.get("email") or ctx.get("username"), limit=limit))
    except Exception as exc:
        app.logger.error("Fetching logs failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503


@app.route("/logs/mine", methods=["DELETE"])
def delete_my_logs():
    ctx = _require_auth(required_role=None)
    user_id = ctx.get("user_id")
    username = ctx.get("email") or ctx.get("username")
    role = ctx.get("role")
    if role != "admin" and not get_user_can_delete_own(user_id):
        return jsonify({"error": "forbidden", "message": "Admin has not granted delete permission for your account."}), 403
    try:
        deleted = delete_logs_for_user_id(int(user_id)) if user_id is not None else delete_logs_for_user(username)
        return jsonify({"status": "cleared", "deleted": deleted, "scope": "mine"})
    except Exception as exc:
        app.logger.error("Clearing user logs failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503


@app.route("/admin/users/<username>/permissions", methods=["POST"])
def admin_set_user_permissions(username: str):
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    can_delete = bool(data.get("can_delete_own_logs", False))
    set_user_can_delete_own(username, can_delete)
    return jsonify({"status": "ok", "username": username, "can_delete_own_logs": can_delete})


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    if request.method == "GET":
        try:
            return jsonify({"users": list_users()})
        except Exception as exc:
            app.logger.error("Listing users failed: %s", exc)
            return jsonify({"error": "database_unavailable"}), 503

    data = request.get_json(silent=True) or {}
    email = (str(data.get("email") or "").strip())
    username = (str(data.get("username") or "").strip())
    password = str(data.get("password") or "")
    role = (str(data.get("role") or "user").strip() or "user")
    if role not in ("user", "admin"):
        return jsonify({"error": "invalid role"}), 400
    if not (email or username) or not password:
        return jsonify({"error": "missing email/password"}), 400
    try:
        email_to_use = (email or username).strip()
        create_user(email_to_use, password, role=role, username=username or None)
        return jsonify({"status": "ok", "email": email_to_use, "role": role})
    except Exception as exc:
        app.logger.error("Create user failed: %s", exc)
        return jsonify({"error": "failed to create user"}), 400


@app.route("/admin/users/<username>/role", methods=["POST"])
def admin_change_role(username: str):
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    role = (str(data.get("role") or "").strip())
    if role not in ("user", "admin"):
        return jsonify({"error": "invalid role"}), 400
    try:
        set_user_role(username, role)
        return jsonify({"status": "ok", "username": username, "role": role})
    except Exception as exc:
        app.logger.error("Set role failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503


@app.route("/admin/users/by-id/<int:user_id>/role", methods=["POST"])
def admin_change_role_by_id(user_id: int):
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    role = (str(data.get("role") or "").strip())
    if role not in ("user", "admin"):
        return jsonify({"error": "invalid role"}), 400
    try:
        set_user_role(int(user_id), role)
        u = get_user_by_id(int(user_id))
        return jsonify({"status": "ok", "user_id": int(user_id), "email": (u or {}).get("email"), "role": role})
    except Exception as exc:
        app.logger.error("Set role failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503


@app.route("/admin/users/<username>/password", methods=["POST"])
def admin_change_password(username: str):
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    password = str(data.get("password") or "")
    if not password:
        return jsonify({"error": "missing password"}), 400
    try:
        set_user_password(username, password)
        return jsonify({"status": "ok", "username": username})
    except Exception as exc:
        app.logger.error("Set password failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503


@app.route("/admin/users/by-id/<int:user_id>/logs", methods=["GET", "DELETE"])
def admin_user_logs_by_id(user_id: int):
    if not _is_admin_request():
        return jsonify({"error": "unauthorized"}), 401
    limit = int(request.args.get("limit", 50))
    try:
        if request.method == "DELETE":
            deleted = delete_logs_for_user_id(int(user_id))
            return jsonify({"status": "cleared", "deleted": deleted, "scope": "user_id", "user_id": int(user_id)})
        return jsonify(get_recent_for_user_id(int(user_id), limit=limit))
    except Exception as exc:
        app.logger.error("Admin user logs failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8081, type=int)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=True, use_reloader=False)
