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


def create(kind: str, idea: dict) -> dict:
    rec = {
        "id": uuid.uuid4().hex[:10],
        "kind": kind,
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


def uploads_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in load() if r.get("youtube_id") and r.get("created_at", "").startswith(today))
