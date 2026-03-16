"""
interfaces.py — Stub interfaces for the other 3 members' modules.

WHY THIS FILE EXISTS:
    Your CLI code needs to call Member 2, 3, and 4's code.
    But they haven't written it yet!

    This file provides FAKE versions of their functions so your
    CLI code runs and can be tested right now.

    When a member finishes their module, they REPLACE the stub
    below with a real import from their module.

HOW TO SWAP IN REAL CODE:
    When Member 2 finishes build_engine/builder.py, change:
        # STUB
        def build_image(...): ...
    to:
        from build_engine.builder import build_image

    Same for Members 3 and 4.
"""


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER 2 — Build Engine  ✅  INTEGRATED
# ══════════════════════════════════════════════════════════════════════════════
from build_engine.builder import build_image   # noqa: F401  (re-exported for CLI)


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER 3 — Layer & Image Storage
# Replace with: from storage.image_store import list_images, delete_image
# ══════════════════════════════════════════════════════════════════════════════

def list_images():
    from storage.image_store import list_images as _list_images
    raw = _list_images()
    result = []
    for img in raw:
        digest = img.get("digest", "")
        result.append({
            "name":    img.get("name", ""),
            "tag":     img.get("tag", ""),
            "id":      digest.replace("sha256:", "")[:12],
            "created": img.get("created", "")
        })
    return result


def delete_image(image: str):
    from storage.image_store import remove_image
    if ":" in image:
        name, tag = image.split(":", 1)
    else:
        name, tag = image, "latest"
    remove_image(name, tag)


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER 4 — Container Runtime
# Replace with: from runtime.runner import run_container
# ══════════════════════════════════════════════════════════════════════════════

from runtime.runner import run_container
