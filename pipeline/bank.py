import json
import re
from pathlib import Path
import requests
import config

BANK_FILE = config.ROOT / "bank" / "clips.json"
UA = {"User-Agent": "MoneyPrint-ReZain/1.0 (educational bot)"}

TOPICS = [
    "black hole",
    "mars surface",
    "galaxy",
    "nebula",
    "moon",
    "earth from space",
    "astronaut",
    "rocket launch",
    "solar system",
    "exoplanet",
    "james webb telescope",
    "saturn",
    "jupiter",
    "sun surface",
    "starfield",
]


def load() -> dict:
    if BANK_FILE.exists():
        try:
            return json.loads(BANK_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"topics": {}}


def save(bank: dict) -> None:
    BANK_FILE.parent.mkdir(parents=True, exist_ok=True)
    BANK_FILE.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")


def _words(s: str) -> set:
    return set(re.findall(r"[a-z]+", s.lower()))


def find(query: str, skip: set | None = None, vertical: bool = True) -> dict | None:
    skip = skip or set()
    bank = load()
    topics = bank.get("topics", {})
    if not topics:
        return None
    qw = _words(query)
    scored = []
    for topic, clips in topics.items():
        tw = _words(topic)
        overlap = len(qw & tw)
        if overlap or any(w in query.lower() for w in tw):
            scored.append((overlap, topic))
    scored.sort(reverse=True)
    for _, topic in scored:
        cands = topics.get(topic, [])
        fresh = [c for c in cands if c.get("url") and c["url"] not in skip]
        pool = fresh or cands
        if pool:
            return pool[0]
    return None


def _nasa_links(query: str, limit: int = 12) -> list:
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image"},
            timeout=25,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("collection", {}).get("items", [])[:10]
        out = []
        for it in items:
            links = sorted(
                [ln for ln in (it.get("links") or []) if ln.get("href")],
                key=lambda ln: ln.get("width", 0) or 0,
                reverse=True,
            )
            for ln in links:
                h = ln["href"]
                if re.search(r"\.(jpg|jpeg|png)(\?|$)", str(h), re.I):
                    out.append(
                        {"url": h, "type": "image", "source": "nasa", "topic": query}
                    )
                    break
            if len(out) >= limit:
                break
        return out
    except requests.RequestException:
        return []


def build(topics: list | None = None, per_topic: int = 10) -> dict:
    topics = topics or TOPICS
    bank = load()
    store = bank.setdefault("topics", {})
    for topic in topics:
        if config.kill_requested():
            break
        have = {c.get("url") for c in store.get(topic, [])}
        fresh = [c for c in _nasa_links(topic, per_topic) if c["url"] not in have]
        store.setdefault(topic, []).extend(fresh)
        print(f"{topic}: +{len(fresh)} (total {len(store[topic])})")
    save(bank)
    return bank


def stats() -> dict:
    bank = load()
    topics = bank.get("topics", {})
    return {
        "topics": len(topics),
        "clips": sum(len(v) for v in topics.values()),
        "detail": {k: len(v) for k, v in topics.items()},
    }
