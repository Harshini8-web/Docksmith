import os
import tarfile
import hashlib

DOCKSMITH_HOME = os.path.expanduser("~/.docksmith")
LAYERS_DIR = os.path.join(DOCKSMITH_HOME, "layers")


def init_layer_store():
    os.makedirs(LAYERS_DIR, exist_ok=True)


def hash_directory(directory):
    sha = hashlib.sha256()

    for root, dirs, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)

            with open(path, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sha.update(chunk)

    return sha.hexdigest()


def create_layer(directory):
    init_layer_store()

    digest = hash_directory(directory)

    layer_path = os.path.join(LAYERS_DIR, digest + ".tar")

    if os.path.exists(layer_path):
        print("Layer already exists")
        return digest

    with tarfile.open(layer_path, "w") as tar:
        tar.add(directory, arcname="")

    print("Layer created:", digest)

    return digest


def get_layer_path(digest):
    return os.path.join(LAYERS_DIR, digest + ".tar")