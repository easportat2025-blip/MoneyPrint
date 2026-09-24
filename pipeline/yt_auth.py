import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import requests as _rq
except ImportError:
    _rq = None

CACHE_TTL = 3600


def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key, default)
    v = (v or "").strip()
    return v if v else default


def _cache_path(slot: str) -> Path:
    return ROOT / f"account_cache_{slot}.json"


def _read_cache(slot: str) -> dict | None:
    p = _cache_path(slot)
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - d.get("at", 0) < CACHE_TTL:
                return d
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_cache(slot: str, data: dict) -> None:
    data["at"] = time.time()
    try:
        _cache_path(slot).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def check_slot(slot: str, force: bool = False) -> dict:
    cid = _env("YOUTUBE_CLIENT_ID")
    csec = _env("YOUTUBE_CLIENT_SECRET")
    rt = _env("YOUTUBE_REFRESH_TOKEN" if slot == "1" else "YOUTUBE_REFRESH_TOKEN_2")
    email = _env(f"ACCOUNT_{slot}_EMAIL")
    name = _env(f"CHANNEL_{slot}_NAME", f"Channel{slot}")
    out = {
        "slot": slot,
        "name": name,
        "email": email or "-",
        "configured": bool(cid and rt),
        "token_ok": False,
        "readonly_ok": False,
        "channel_id": "",
        "channel_title": "",
        "subs": "-",
        "videos": "-",
        "error": "",
    }
    if not out["configured"]:
        out["error"] = "thieu refresh token"
        return out
    if not force:
        cached = _read_cache(slot)
        if cached and cached.get("ok"):
            cached["slot"] = slot
            return cached
    if _rq is None:
        out["error"] = "thieu requests"
        return out
    try:
        t = _rq.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": csec,
                "refresh_token": rt,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        if t.status_code != 200:
            out["error"] = f"refresh fail {t.status_code}"
            return out
        out["token_ok"] = True
        token = t.json()["access_token"]
        r = _rq.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"mine": "true", "part": "snippet,statistics"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r.status_code == 403:
            out["error"] = "thieu scope readonly (chay lai wizard)"
            _write_cache(slot, {**out, "ok": False})
            return out
        if r.status_code != 200:
            out["error"] = f"channels {r.status_code}"
            return out
        items = r.json().get("items", [])
        if not items:
            out["error"] = "mail nay chua co kenh YouTube"
            return out
        ch = items[0]
        st = ch.get("statistics", {})
        out.update(
            {
                "readonly_ok": True,
                "channel_id": ch.get("id", ""),
                "channel_title": ch.get("snippet", {}).get("title", ""),
                "subs": st.get("subscriberCount", "0"),
                "videos": st.get("videoCount", "0"),
            }
        )
        _write_cache(slot, {**out, "ok": True})
    except Exception as e:
        out["error"] = str(e)[:150]
    return out


def check_all(force: bool = False) -> list:
    return [check_slot("1", force), check_slot("2", force)]
