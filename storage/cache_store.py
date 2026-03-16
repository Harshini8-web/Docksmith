import os
import hashlib

DOCKSMITH_HOME = os.path.expanduser("~/.docksmith")
CACHE_DIR = os.path.join(DOCKSMITH_HOME, "cache")

os.makedirs(CACHE_DIR, exist_ok=True)


def compute_cache_key(instruction, previous_layer):
    data = instruction + (previous_layer or "")
    return hashlib.sha256(data.encode()).hexdigest()


def save_cache(key, layer_digest):
    path = os.path.join(CACHE_DIR, key)

    with open(path, "w") as f:
        f.write(layer_digest)


def load_cache(key):
    path = os.path.join(CACHE_DIR, key)

    if os.path.exists(path):
        with open(path) as f:
            return f.read()

    return None