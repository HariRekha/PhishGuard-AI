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
* POST `/predict`   (JSON body: { "url": "...", "device": "...", "ip": "...", "metadata": {...} })
* POST `/train`     (protected — pass header `X-ADMIN-TOKEN: <token>`)
* GET `/logs`       (recent logs)

Example predict:

```bash
curl -X POST http://localhost:8081/predict -H "Content-Type: application/json" \
  -d '{"url":"http://secure-bank.example/login","device":"Android","ip":"1.2.3.4"}'
```

## Tests

Run tests with pytest:

```bash
pytest -q
```

## Environment variables

* `X_ADMIN_TOKEN`: token to protect /train (default "changeme")
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
