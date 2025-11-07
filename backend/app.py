import os
import time
from importlib import import_module
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from features import extract_features, features_schema
from config import MODEL_FILE, ADMIN_TOKEN, FRONTEND_ORIGINS, MAX_URL_LENGTH, DEFAULT_DATA_PATH
import joblib
from db import insert_prediction, get_recent
from pathlib import Path
from sklearn.feature_extraction import DictVectorizer  # added

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": FRONTEND_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-ADMIN-TOKEN"],
    }
})

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
    return jsonify({
        "status": "ok",
        "model_loaded": MODEL is not None,
        "model_version": MODEL_META.get("model_version"),
        "model_compatible": bool(_is_valid_pipeline(MODEL)) if MODEL is not None else False,
        "model_accuracy": MODEL_META.get("accuracy"),  # added
    })

@app.route("/features/schema", methods=["GET"])
def schema():
    return jsonify(features_schema())

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    if not data or "url" not in data:
        return jsonify({"error": "missing 'url' in payload"}), 400
    url = str(data.get("url"))[:MAX_URL_LENGTH]
    device = data.get("device", "")
    ip = data.get("ip", "")
    metadata = data.get("metadata", {})
    if len(url) > MAX_URL_LENGTH:
        return jsonify({"error": "url too long"}), 400
    features = extract_features(url)
    if MODEL is None:
        try:
            log_id = insert_prediction(url, features, prediction=-1, probability=-1.0, device=device, ip=ip, metadata=metadata, model_version=str(MODEL_META.get("model_version")))
        except Exception as exc:
            app.logger.warning("Failed to log prediction (model missing): %s", exc)
            log_id = None
        return jsonify({
            "prediction": "model_not_loaded",
            "probability": None,
            "features": features,
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
        log_id = insert_prediction(url, features, prediction=int(pred), probability=proba or 0.0, device=device, ip=ip, metadata=metadata, model_version=str(MODEL_META.get("model_version")))
    except Exception as exc:
        app.logger.warning("Failed to log prediction: %s", exc)
        log_id = None
    return jsonify({
        "prediction": label,
        "probability": proba,
        "features": features,
        "model_version": MODEL_META.get("model_version"),
        "model_accuracy": MODEL_META.get("accuracy"),  # added
        "log_id": log_id
    })

@app.route("/train", methods=["POST"])
def train_endpoint():
    header_token = request.headers.get("X-ADMIN-TOKEN", "")
    if header_token != ADMIN_TOKEN and request.remote_addr not in ("127.0.0.1", "localhost"):
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

@app.route("/logs", methods=["GET"])
def logs():
    limit = int(request.args.get("limit", 50))
    try:
        return jsonify(get_recent(limit=limit))
    except Exception as exc:
        app.logger.error("Fetching logs failed: %s", exc)
        return jsonify({"error": "database_unavailable"}), 503

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8081, type=int)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=True)
