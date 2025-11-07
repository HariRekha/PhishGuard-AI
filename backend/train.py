import csv
import joblib
import time
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.decomposition import TruncatedSVD  # added
from sklearn.preprocessing import StandardScaler  # added
from features import extract_features
from data_loader import load_dataset
from config import MODEL_DIR, MODEL_FILE
import traceback  # added

# Ensure these are Path objects even if config provides strings
MODEL_DIR = Path(MODEL_DIR)
MODEL_FILE = Path(MODEL_FILE)

MODEL_DIR.mkdir(parents=True, exist_ok=True)


def build_pipeline():
    """Builds a memory-friendly pipeline: DictVectorizer (sparse) -> SVD -> Scaler -> RandomForest."""
    vectorizer = DictVectorizer(sparse=True)  # was: sparse=False
    svd = TruncatedSVD(n_components=256, random_state=42)
    scaler = StandardScaler(with_mean=False)
    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    return Pipeline([
        ("vectorizer", vectorizer),
        ("svd", svd),
        ("scaler", scaler),
        ("clf", clf)
    ])


def _capture_error(exc: Exception) -> dict:
    """Return a JSON-safe error payload for frontends."""
    return {
        "error": str(exc),
        "error_type": exc.__class__.__name__,
        "traceback": traceback.format_exc(),
    }


def train_model(
    data_path: str = None,
    save_path: Path = None,  # was: MODEL_FILE
    perform_gridsearch: bool = False,
    label_column: str = "label",
    raise_errors: bool = False,  # added: control re-raising
):
    """Train phishing URL detection model."""
    start = time.time()
    try:
        # Resolve save path
        save_path = Path(save_path) if save_path else MODEL_FILE

        # Load dataset
        dataset = load_dataset(data_path, label_column=label_column)
        print(f"[train] loaded dataset with {len(dataset)} rows")

        # Extract features and labels
        feature_rows = [extract_features(row["url"]) for row in dataset]
        labels = [int(row["label"]) for row in dataset]

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            feature_rows, labels, test_size=0.20, random_state=42, stratify=labels
        )

        # Build pipeline
        pipeline = build_pipeline()

        # Optional GridSearch
        if perform_gridsearch:
            param_grid = {
                "svd__n_components": [128, 256],
                "clf__n_estimators": [100, 200],
                "clf__max_depth": [None, 10, 20],
            }
            gs = GridSearchCV(pipeline, param_grid, cv=3, scoring="f1", n_jobs=-1, verbose=1)
            gs.fit(X_train, y_train)
            model = gs.best_estimator_
            print("[train] GridSearchCV best params:", gs.best_params_)
        else:
            pipeline.fit(X_train, y_train)
            model = pipeline

        # Evaluate model
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None

        accuracy = accuracy_score(y_test, y_pred)
        print(f"[train] Accuracy: {accuracy:.4f}")
        print("[train] Classification report:")
        print(classification_report(y_test, y_pred, digits=4))

        # Safeguard ROC AUC when only one class is present in y_test
        if y_proba is not None and len(set(y_test)) > 1:
            try:
                auc = roc_auc_score(y_test, y_proba)
                print(f"[train] ROC AUC: {auc:.4f}")
            except Exception as exc:
                print(f"[train] ROC AUC unavailable: {exc}")

        # Save model
        model_info = {
            "model_version": time.strftime("%Y%m%d-%H%M%S"),
            "trained_rows": len(X_train),
            "test_rows": len(X_test),
            "timestamp": time.time(),
            "accuracy": accuracy,
        }

        save_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": model, "meta": model_info}, save_path)
        print(f"[train] model saved to {save_path}")

        # Save predictions to CSV
        preds_csv = save_path.parent / "test_predictions.csv"
        fieldnames = sorted({key for row in X_test for key in row.keys()})

        with preds_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames + ["label", "pred", "prob"])
            writer.writeheader()
            probs = list(y_proba) if y_proba is not None else [None] * len(y_pred)
            for row_feat, label, pred, prob in zip(X_test, y_test, y_pred, probs):
                record = {name: row_feat.get(name, "") for name in fieldnames}
                record.update({
                    "label": int(label),
                    "pred": int(pred),
                    "prob": float(prob) if prob is not None else ""
                })
                writer.writerow(record)

        print(f"[train] test split predictions saved to {preds_csv}")
        print(f"[train] completed in {time.time() - start:.1f}s")
        return {"meta": model_info, "test_predictions": str(preds_csv)}
    except Exception as exc:
        err = _capture_error(exc)
        print(f"[train][ERROR] {err['error_type']}: {err['error']}")
        print(err["traceback"])
        if raise_errors:
            raise
        return err


# ---------------- MAIN ENTRY POINT ---------------- #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train phishing URL detection model")
    parser.add_argument("--data", help="Path to dataset CSV", default=None)
    parser.add_argument("--grid", action="store_true", help="Run GridSearchCV (slow)")
    parser.add_argument("--label-column", default="label", help="Name of the label column in the dataset")
    args = parser.parse_args()

    # Run model training
    result = train_model(
        data_path=args.data,
        perform_gridsearch=args.grid,
        label_column=args.label_column,
        raise_errors=False,  # return structured error instead of crashing
    )
    # Print a concise summary for CLI usage
    if "error" in result:
        print("[train] Exited with error (see details above).")
