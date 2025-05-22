import os
import json
import threading
import time
import requests
from datetime import datetime, timedelta

CACHE_PATH = "/tmp/cip10_registry.json"
CACHE_EXPIRATION_SECONDS = 3600  # 1 hour

_registry_labels = set()

def _load_registry():
    global _registry_labels
    url = "https://raw.githubusercontent.com/cardano-foundation/CIPs/master/CIP-0010/registry.json"
    try:
        print("[registry_loader] Fetching CIP-10 registry...")
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        with open(CACHE_PATH, "w") as f:
            json.dump(data, f)
        _registry_labels = {entry["transaction_metadatum_label"] for entry in data}
        print(f"[registry_loader] Loaded {len(_registry_labels)} labels.")
    except Exception as e:
        print(f"[registry_loader] Failed to load registry: {e}")

def _load_from_cache():
    global _registry_labels
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r") as f:
            try:
                data = json.load(f)
                _registry_labels = {entry["transaction_metadatum_label"] for entry in data}
                print(f"[registry_loader] Loaded {len(_registry_labels)} labels from cache.")
            except Exception as e:
                print(f"[registry_loader] Failed to load cache: {e}")

def get_registry_labels():
    return _registry_labels

def start_registry_loader():
    def loop():
        while True:
            _load_registry()
            time.sleep(CACHE_EXPIRATION_SECONDS)

    _load_from_cache()
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()