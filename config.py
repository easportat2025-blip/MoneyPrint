import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"
STATE_FILE = ROOT / "state.json"
KILL_FILE = ROOT / "KILL"
STATE_BRANCH = "logs"

for d in (CACHE_DIR, OUTPUT_DIR):
    d.mkdir(exist_ok=True)


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


GEMINI_KEYS = [k for k in (env("GEMINI_KEY_A"), env("GEMINI_KEY_B")) if k]
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_MODEL_FALLBACK = env("GEMINI_MODEL_FALLBACK", "gemini-3.5-flash")

YOUTUBE_CLIENT_ID = env("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = env("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = env("YOUTUBE_REFRESH_TOKEN")

PEXELS_API_KEY = env("PEXELS_API_KEY")
PIXABAY_API_KEY = env("PIXABAY_API_KEY")

SCHEDULE = env("SCHEDULE", "short")
NICHE = env("NICHE", "space science documentary facts")
VOICE = env("VOICE", "en-US-ChristopherNeural")
SHORTS_PER_DAY = int(env("SHORTS_PER_DAY", "3"))
LONG_EVERY_DAYS = int(env("LONG_EVERY_DAYS", "5"))
MAX_DAILY_UPLOADS = int(env("MAX_DAILY_UPLOADS", "6"))

SHORT_FPS = 30
SHORT_W, SHORT_H = 1080, 1920
SHORT_MAX_SEC = 55
SHORT_SCENE_SEC = 4

LONG_FPS = 24
LONG_W, LONG_H = 1920, 1080
LONG_MIN_SEC = 300
LONG_SCENE_SEC = 6


def kill_requested() -> bool:
    return KILL_FILE.exists()
