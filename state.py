import json
import uuid
from datetime import datetime, timezone
import config


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> list:
    if not config.STATE_FILE.exists():
        return []
    try:
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save(records: list) -> None:
    config.STATE_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def create(kind: str, idea: dict, channel: str = "", slot: str = "") -> dict:
    rec = {
        "id": uuid.uuid4().hex[:10],
        "kind": kind,
        "channel": channel,
        "slot": slot,
        "status": "planned",
        "title": idea.get("title", ""),
        "idea": idea,
        "scenes": [],
        "error": "",
        "youtube_id": "",
        "youtube_url": "",
        "created_at": _now(),
        "updated_at": _now(),
        "stages": {},
    }
    records = load()
    records.insert(0, rec)
    save(records)
    return rec


def update(rec_id: str, **fields) -> dict | None:
    records = load()
    for rec in records:
        if rec["id"] == rec_id:
            rec.update(fields)
            rec["updated_at"] = _now()
            save(records)
            return rec
    return None


def stage(rec_id: str, name: str, ok: bool = True, detail: str = "") -> None:
    records = load()
    for rec in records:
        if rec["id"] == rec_id:
            rec.setdefault("stages", {})[name] = {
                "ok": ok,
                "detail": detail,
                "at": _now(),
            }
            rec["updated_at"] = _now()
            save(records)
            return


def get(rec_id: str) -> dict | None:
    for rec in load():
        if rec["id"] == rec_id:
            return rec
    return None


def used_titles() -> set:
    return {r.get("title", "").lower() for r in load() if r.get("title")}


def used_media_urls() -> set:
    urls = set()
    for r in load():
        for u in r.get("media_urls", []) or []:
            if u:
                urls.add(u)
    return urls


USAGE_FILE = config.ROOT / "gemini_usage.json"


def gemini_usage() -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        if USAGE_FILE.exists():
            d = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            if d.get("date") == today:
                return d
    except (json.JSONDecodeError, OSError):
        pass
    return {"date": today, "count": 0}


def bump_gemini(n: int = 1) -> int:
    d = gemini_usage()
    d["count"] = d.get("count", 0) + n
    try:
        USAGE_FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass
    return d["count"]


def uploads_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in load() if r.get("youtube_id") and r.get("created_at", "").startswith(today))


def uploads_today_by_slot() -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    out: dict = {}
    for r in load():
        if not r.get("youtube_id") or not r.get("created_at", "").startswith(today):
            continue
        key = r.get("slot") or r.get("channel") or "?"
        out[key] = out.get(key, 0) + 1
    return out


UNITS_FILE = config.ROOT / "units_usage.json"
UNITS_BUDGET = 10000


def units_spent_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        if UNITS_FILE.exists():
            d = json.loads(UNITS_FILE.read_text(encoding="utf-8"))
            if d.get("date") == today:
                return int(d.get("units", 0))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        pass
    return 0


def spend_units(n: int) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    spent = units_spent_today() + n
    try:
        UNITS_FILE.write_text(
            json.dumps({"date": today, "units": spent}), encoding="utf-8"
        )
    except OSError:
        pass
    return spent


def units_left(reserve: int = 0) -> int:
    return max(UNITS_BUDGET - units_spent_today() - reserve, 0)
