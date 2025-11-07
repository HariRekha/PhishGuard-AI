import json
import os
import tempfile
import pytest
from app import app, load_model
from config import MODEL_FILE

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    j = resp.get_json()
    assert "status" in j

def test_predict_no_model(client, monkeypatch):
    p = MODEL_FILE
    moved = False
    temp = None
    if os.path.exists(p):
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.close()
        os.rename(p, temp.name)
        moved = True
    load_model()
    resp = client.post("/predict", json={"url":"http://example.com/login"})
    assert resp.status_code == 200
    j = resp.get_json()
    assert j["prediction"] == "model_not_loaded"
    if moved:
        os.rename(temp.name, p)
        load_model()
