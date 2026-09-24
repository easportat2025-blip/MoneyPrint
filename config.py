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
    v = (os.environ.get(key, default) or "").strip()
    return v if v else default


GEMINI_KEYS = [k for k in (env("GEMINI_KEY_A"), env("GEMINI_KEY_B")) if k]
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_MODEL_FALLBACK = env("GEMINI_MODEL_FALLBACK", "gemini-3.5-flash")

_DEFAULT_CHAIN = [
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def model_chain() -> list:
    raw = env("GEMINI_MODELS", "")
    chain = [m.strip() for m in raw.split(",") if m.strip()]
    if not chain:
        chain = list(_DEFAULT_CHAIN)
    for m in (GEMINI_MODEL, GEMINI_MODEL_FALLBACK):
        if m and m not in chain:
            chain.append(m)
    seen = []
    for m in chain:
        if m not in seen:
            seen.append(m)
    return seen

CHANNEL = env("CHANNEL", "1")
CHANNEL_1_NAME = env("CHANNEL_1_NAME", "ReZain")
CHANNEL_2_NAME = env("CHANNEL_2_NAME", "Channel2")

YOUTUBE_CLIENT_ID = env("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = env("YOUTUBE_CLIENT_SECRET")
if CHANNEL == "2":
    YOUTUBE_REFRESH_TOKEN = env("YOUTUBE_REFRESH_TOKEN_2")
    NICHE_ACTIVE = env("NICHE_2", "")
    VOICE_ACTIVE = env("VOICE_2", "")
    CHANNEL_NAME = CHANNEL_2_NAME
else:
    YOUTUBE_REFRESH_TOKEN = env("YOUTUBE_REFRESH_TOKEN")
    NICHE_ACTIVE = env("NICHE", "")
    VOICE_ACTIVE = env("VOICE", "")
    CHANNEL_NAME = CHANNEL_1_NAME

if not NICHE_ACTIVE:
    NICHE_ACTIVE = "space science documentary facts"
if not VOICE_ACTIVE:
    VOICE_ACTIVE = "en-US-GuyNeural" if CHANNEL == "2" else "en-US-ChristopherNeural"

PEXELS_API_KEY = env("PEXELS_API_KEY")
PIXABAY_API_KEY = env("PIXABAY_API_KEY")

SCHEDULE = env("SCHEDULE", "short")
NICHE = NICHE_ACTIVE
VOICE = VOICE_ACTIVE
SHORTS_PER_DAY = int(env("SHORTS_PER_DAY", "3"))
LONG_EVERY_DAYS = int(env("LONG_EVERY_DAYS", "5"))
MAX_DAILY_UPLOADS = int(env("MAX_DAILY_UPLOADS", "6"))
MEDIA_MODE = env("MEDIA_MODE", "mixed")
RETRY_MAX = int(env("RETRY_MAX", "2"))
RETRY_BASE_SEC = int(env("RETRY_BASE_SEC", "30"))

SHORT_FPS = 30
SHORT_W, SHORT_H = 1080, 1920
SHORT_MAX_SEC = 55
SHORT_SCENE_SEC = 3

LONG_FPS = 24
LONG_W, LONG_H = 1920, 1080
LONG_MIN_SEC = 300
LONG_SCENE_SEC = 6


def kill_requested() -> bool:
    return KILL_FILE.exists()
