import csv
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import DEFAULT_DATA_PATH

LABEL_ALIASES = ["label", "target", "class", "status", "result", "phishing"]
URL_ALIASES = ["url", "URL", "Url", "link", "Link"]

def normalize_label(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        s_low = s.lower()
        if s_low in ("1", "phishing", "malicious", "yes", "true"):
            return 1
        if s_low in ("0", "legitimate", "benign", "no", "false"):
            return 0
        try:
            iv = int(float(s_low))
            return 1 if iv == 1 else 0
        except Exception:
            return None
    if isinstance(v, (int, float)):
        try:
            iv = int(float(v))
            return 1 if iv == 1 else 0
        except Exception:
            return None
    return None

def load_dataset(path: Optional[str] = None, label_column: str = "label") -> List[Dict[str, Any]]:
    p = Path(path) if path else Path(DEFAULT_DATA_PATH)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found at {p}. See README for how to download a public dataset.")
    with p.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("Dataset must contain headers.")
        field_map = {name.lower(): name for name in reader.fieldnames}
        url_key = next((field_map.get(alias.lower()) for alias in URL_ALIASES if alias.lower() in field_map), None)
        if not url_key:
            raise ValueError(f"Dataset must contain a URL column (one of: {', '.join(URL_ALIASES)}).")
        candidate_labels = [label_column] + [c for c in LABEL_ALIASES if c != label_column]
        label_key = next((field_map.get(alias.lower()) for alias in candidate_labels if alias.lower() in field_map), None)
        if not label_key:
            raise ValueError("Dataset must contain a label column. Tried: " + ", ".join(candidate_labels))
        records: List[Dict[str, Any]] = []
        for row in reader:
            raw_url = (row.get(url_key) or "").strip()
            if not raw_url:
                continue
            norm_label = normalize_label(row.get(label_key))
            if norm_label is None:
                continue
            records.append({"url": raw_url, "label": norm_label})
    if not records:
        raise ValueError("Dataset did not yield any usable rows (missing URL/label).")
    return records
