# Phishing URL Detector - Backend (Flask)

## Requirements
- Python 3.10+
- pip
- Recommended: create a virtualenv

## Install
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Train model (sample)

A small synthetic sample dataset is included at `sample_data/sample_phishing.csv`.

Train:

```bash
python train.py --data sample_data/sample_phishing.csv
```

This will create `model/model.joblib` and `model/test_predictions.csv`.

To run a slower grid search:

```bash
python train.py --data sample_data/sample_phishing.csv --grid
```

## Run Flask API (dev)

```bash
export X_ADMIN_TOKEN=changeme
export FRONTEND_ORIGINS=http://localhost:5173
python app.py --host 0.0.0.0 --port 8081
```

Endpoints:

* GET `/health`
* GET `/features/schema`
* GET `/client-info` (returns detected `ip` + `device` from the request)
* POST `/auth/login` (returns Bearer token + role)
* GET `/auth/me` (requires Bearer token)
* POST `/predict`   (JSON body: { "url": "...", "metadata": {...} })
* POST `/train`     (protected — pass header `X-ADMIN-TOKEN: <token>`)
* GET `/logs`       (recent logs, requires Bearer token)
* DELETE `/logs`    (admin only: clears all logs)

Example predict:

```bash
curl -X POST http://localhost:8081/predict -H "Content-Type: application/json" \
  -d '{"url":"http://secure-bank.example/login"}'

Note: the backend derives `device` (from User-Agent) and `ip` (from request headers / remote address) automatically.

Example client info:

```bash
curl http://localhost:8081/client-info
```
```

## Tests

Run tests with pytest:

```bash
pytest -q
```

## Environment variables

* `X_ADMIN_TOKEN`: token to protect /train (default "changeme")
* `AUTH_SECRET`: secret used to sign login tokens (default "dev-secret-change-me")
* `ADMIN_USERNAME` / `ADMIN_PASSWORD`: admin credentials (defaults: admin/admin123)
* `USER_USERNAME` / `USER_PASSWORD`: normal user credentials (defaults: user/user123)
* `FRONTEND_ORIGINS`: comma-separated allowed origins for CORS
* `LOG_FULL_URLS`: if true, logs full URLs; default false (masks)
* `MAX_URL_LENGTH`: max length accepted for submitted url

## Deployment notes

* Use a WSGI server like Gunicorn for production.
* Ensure ADMIN token is strong and not checked into source.
* Do NOT configure to log full URLs in public or multi-tenant deployments (privacy).
* Set FRONTEND_ORIGINS to your front-end origin(s).

## Extensibility

* Add new features in `features.py` (small independent functions).
* For domain age, integrate WHOIS or a curated dataset and update `domain_age_days`.
* Replace classifier with XGBoost by modifying `train.py`.

## Improving accuracy

Accuracy depends mostly on data quality/quantity and feature quality.

Practical steps that usually help:

1) Add more labeled data
- Put more rows into your CSV (phishing + legitimate). The included sample is tiny and will not generalize.
- Keep the label column consistent (default is `label` where 1=phishing, 0=legitimate).

2) Use the built-in grid search

```bash
python train.py --data sample_data/sample_phishing.csv --grid
```

This runs a small `GridSearchCV` over a few hyperparameters (slower, but often better).

3) Evaluate properly
- Look at the printed `classification_report` and ROC AUC (better than accuracy on imbalanced datasets).
- If your data is imbalanced (many more legitimate than phishing), consider tuning the model or using class weights.

4) Add stronger features
- Current approach is lexical-only (it does not visit URLs). Adding features like known brand tokens, punycode detection, TLD reputation lists, or URL length patterns can help.
