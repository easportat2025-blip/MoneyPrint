import json
import re
from pathlib import Path
import config

VIEWS_FILE = config.ROOT / "views_history.json"
STATE_FILE = config.ROOT / "state_from_logs.json"

STOP = {
    "the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is", "was",
    "why", "what", "how", "that", "this", "it", "you", "your", "we", "i",
    "did", "do", "does", "at", "by", "with", "from", "as", "but", "not",
    "who", "which", "when", "are", "were", "have", "has", "had", "be",
    "them", "they", "he", "she", "his", "her", "their", "its", "one", "two",
    "if", "so", "no", "just", "can", "will", "would", "could", "more", "most",
    "than", "then", "there", "here", "about", "into", "over", "up", "down",
    "out", "all", "new", "own", "now", "get", "got", "make", "made", "every",
    "before", "after", "never", "always", "still", "yet", "only", "also",
}


def _load(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def snapshots() -> dict:
    return _load(VIEWS_FILE) or {}


def titles_with_views() -> list:
    hist = snapshots()
    if not hist:
        return []
    latest = hist[sorted(hist)[-1]]
    return sorted(
        [{"id": k, "views": v.get("views", 0), "title": v.get("title", "")} for k, v in latest.items()],
        key=lambda x: -x["views"],
    )


def top_titles(n: int = 8, min_views: int = 20) -> list:
    return [t for t in titles_with_views() if t["views"] >= min_views][:n]


def winning_words(n: int = 12) -> list:
    top = top_titles(8, 20)
    if not top:
        return []
    words: dict = {}
    for t in top:
        for w in re.findall(r"[a-z']+", t["title"].lower()):
            if len(w) < 4 or w in STOP:
                continue
            words[w] = words.get(w, 0) + 1
    ranked = sorted(words.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, c in ranked if c >= 1][:n]


def proven_block() -> str:
    top = top_titles(6, 20)
    if not top:
        return ""
    lines = []
    for t in top:
        lines.append(f"- ({t['views']} views) {t['title']}")
    words = winning_words(10)
    extra = f"\nWords that repeat in winners: {', '.join(words)}" if words else ""
    return (
        "PROVEN WINNERS on this channel (do NOT copy them, create clearly "
        "different topics with the same energy):\n"
        + "\n".join(lines)
        + extra
    )
