"""Central config: values from .env and persona.json."""
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv optional
    pass

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
(DATA / "images").mkdir(parents=True, exist_ok=True)


def env(key, default=""):
    return os.getenv(key, default)


def flag(key, default="false"):
    return env(key, default).strip().lower() in ("1", "true", "yes", "on")


_s = json.loads((ROOT / "persona.json").read_text(encoding="utf-8"))
PERSONA = _s["persona"]
SCHEDULE = _s["schedule"]
QUALITY = _s["quality"]
HASHTAGS = _s["hashtags"]

TEXT_MODEL = env("TEXT_MODEL", "claude-sonnet-5-5")
QC_MODEL = env("QC_MODEL", "claude-haiku-5-5")
IMAGE_MODEL = env("IMAGE_MODEL", "gpt-image-1")
IMAGE_QUALITY = env("IMAGE_QUALITY", "medium")
