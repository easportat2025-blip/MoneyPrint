import json
import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[1]

try:
    import requests as _rq
except ImportError:
    _rq = None

CACHE_TTL = 3600
CACHE_VERSION = 2


def _fp(token: str) -> str:
    import hashlib

    return hashlib.sha256((token or "").encode()).hexdigest()[:16]


def _env(key: str, default: str = "") -> str:
    v = os.environ.get(key, default)
    v = (v or "").strip()
    return v if v else default


def _cache_path(slot: str) -> Path:
    return ROOT / f"account_cache_{slot}.json"


def _read_cache(slot: str, fp: str) -> dict | None:
    p = _cache_path(slot)
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - d.get("at", 0) < CACHE_TTL:
                if d.get("v") != CACHE_VERSION or d.get("fp") != fp:
                    return None
                return d
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_cache(slot: str, data: dict, fp: str = "") -> None:
    data["at"] = time.time()
    data["v"] = CACHE_VERSION
    if fp:
        data["fp"] = fp
    try:
        _cache_path(slot).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def token_for_slot(slot: str) -> str:
    if slot == "1":
        return _env("YOUTUBE_REFRESH_TOKEN")
    return _env(f"YOUTUBE_REFRESH_TOKEN_{slot}")


def check_slot(slot: str, force: bool = False) -> dict:
    cid = _env("YOUTUBE_CLIENT_ID")
    csec = _env("YOUTUBE_CLIENT_SECRET")
    rt = token_for_slot(slot)
    email = _env(f"ACCOUNT_{slot}_EMAIL")
    env_name = _env(f"CHANNEL_{slot}_NAME", "")
    if slot == "1" and not env_name:
        env_name = "ReZain"
    out = {
        "slot": slot,
        "name": env_name or f"Slot {slot}",
        "display": env_name or f"Slot {slot}",
        "email": email or "-",
        "configured": bool(cid and rt),
        "token_ok": False,
        "readonly_ok": False,
        "channel_id": "",
        "channel_title": "",
        "subs": "-",
        "views": "-",
        "videos": "-",
        "error": "",
    }
    if not rt:
        out["error"] = "chua co refresh token slot nay"
        return out
    fp = _fp(rt)
    if not force:
        cached = _read_cache(slot, fp)
        if cached and cached.get("ok"):
            merged = dict(cached)
            merged["slot"] = slot
            merged["display"] = cached.get("channel_title") or out["name"]
            merged["email"] = email or merged.get("email", "-")
            merged["name"] = env_name or merged.get("name", f"Slot {slot}")
            return merged
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
            out["error"] = "thieu scope readonly (chay lai Dang nhap)"
            _write_cache(slot, {**out, "ok": False}, fp)
            return out
        if r.status_code != 200:
            out["error"] = f"channels {r.status_code}"
            return out
        items = r.json().get("items", [])
        if not items:
            out["error"] = "mail nay chua tao kenh YouTube"
            return out
        ch = items[0]
        st = ch.get("statistics", {})
        title = ch.get("snippet", {}).get("title", "")
        out.update(
            {
                "readonly_ok": True,
                "channel_id": ch.get("id", ""),
                "channel_title": title,
                "display": title or out["name"],
                "subs": st.get("subscriberCount", "0"),
                "views": st.get("viewCount", "0"),
                "videos": st.get("videoCount", "0"),
            }
        )
        _write_cache(slot, {**out, "ok": True}, fp)
    except Exception as e:
        out["error"] = str(e)[:150]
    return out


def check_all(force: bool = False) -> list:
    accs = [check_slot(s, force) for s in ("1", "2", "3")]
    seen: dict = {}
    for a in accs:
        if a["readonly_ok"] and a["channel_id"]:
            first = seen.get(a["channel_id"])
            if first:
                a["duplicate_of"] = first
                a["error"] = f"TRUNG KENH voi slot {first} - kiem tra lai token"
            else:
                seen[a["channel_id"]] = a["slot"]
    return accs


def by_slot(accs: list) -> dict:
    return {a["slot"]: a for a in accs}
