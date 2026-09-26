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
CHANNEL_3_NAME = env("CHANNEL_3_NAME", "Channel3")

CHANNEL_NAMES = {
    "1": CHANNEL_1_NAME,
    "2": CHANNEL_2_NAME,
    "3": CHANNEL_3_NAME,
}

DEFAULT_NICHE = {
    "1": "space science documentary facts",
    "2": "human history documentaries - ancient empires, famous wars, kings queens and historical figures, mysteries of lost civilizations",
    "3": "doi song tieng Viet giai thich bang hoat hinh - co the, giac ngu, an uong, tien, thoi quen, thoi tiet, meo dung dien thoai va may tinh, nhung dieu binh thuong ngay ma it nguoi biet",
}

DEFAULT_VOICE = {
    "1": "en-US-ChristopherNeural",
    "2": "en-US-GuyNeural",
    "3": "vi-VN-NamMinhNeural",
}

YOUTUBE_CLIENT_ID = env("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = env("YOUTUBE_CLIENT_SECRET")


def slot_token(slot: str) -> str:
    mapped = env("YOUTUBE_REFRESH_TOKEN")
    if slot == "1":
        return mapped
    return env(f"YOUTUBE_REFRESH_TOKEN_{slot}") or mapped


YOUTUBE_REFRESH_TOKEN = slot_token(CHANNEL)
CHANNEL_NAME = CHANNEL_NAMES.get(CHANNEL, CHANNEL_1_NAME)
NICHE_ACTIVE = (
    env("NICHE") if CHANNEL == "1" else env(f"NICHE_{CHANNEL}", "")
) or DEFAULT_NICHE.get(CHANNEL, DEFAULT_NICHE["1"])
VOICE_ACTIVE = (
    (env("VOICE") if CHANNEL == "1" else env(f"VOICE_{CHANNEL}", ""))
    or DEFAULT_VOICE.get(CHANNEL, DEFAULT_VOICE["1"])
)

LANG = "vi" if "viet" in NICHE_ACTIVE.lower() else "en"
LANG_NAME = {"vi": "Vietnamese", "en": "English"}[LANG]

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
