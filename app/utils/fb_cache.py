import json
import os

_CACHE_FILE = os.path.join(os.getenv("DATA_DIR", "/app/data"), "fb_image_cache.json")


def set_image(url: str) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump({"url": url or ""}, f)
    except Exception:
        pass


def get_image() -> str:
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f).get("url", "")
    except Exception:
        return ""
