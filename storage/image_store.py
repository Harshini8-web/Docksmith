import os
import json

DOCKSMITH_HOME = os.path.expanduser("~/.docksmith")
IMAGES_DIR = os.path.join(DOCKSMITH_HOME, "images")


def init_image_store():
    os.makedirs(IMAGES_DIR, exist_ok=True)


def save_image(name, tag, layers, config):
    init_image_store()

    image_data = {
        "name": name,
        "tag": tag,
        "layers": layers,
        "config": config
    }

    path = os.path.join(IMAGES_DIR, name + "_" + tag + ".json")

    with open(path, "w") as f:
        json.dump(image_data, f, indent=4)

    print("Image saved:", path)


def load_image(name, tag):
    path = os.path.join(IMAGES_DIR, name + "_" + tag + ".json")

    if not os.path.exists(path):
        raise Exception("Image not found")

    with open(path) as f:
        return json.load(f)


def list_images():
    init_image_store()

    images = []

    for file in os.listdir(IMAGES_DIR):
        if file.endswith(".json"):
            with open(os.path.join(IMAGES_DIR, file)) as f:
                images.append(json.load(f))

    return images


def remove_image(name, tag):
    path = os.path.join(IMAGES_DIR, name + "_" + tag + ".json")

    if os.path.exists(path):
        os.remove(path)
        print("Image removed")