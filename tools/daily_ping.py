"""Daily ping: build yesterday-vs-today performance report.

Runs on GitHub Actions (see daily-ping.yml). Reads state.json + views_history.json
from the logs branch, refreshes per-video views, then prints a markdown report
to stdout AND writes DAILY.md (committed by the workflow).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

VN = timezone(timedelta(hours=7))


def _load(p: Path):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _yt_token() -> str | None:
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "")
    csec = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    rt = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
    if not (cid and rt):
        return None
    try:
        t = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": csec,
                "refresh_token": rt,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        return t.json().get("access_token") if t.status_code == 200 else None
    except requests.RequestException:
        return None


def refresh_views(records: list) -> dict:
    vids = [r["youtube_id"] for r in records if r.get("youtube_id")]
    out: dict = {}
    token = _yt_token()
    if not token:
        print("WARN refresh_views: no access token", file=sys.stderr)
        return out
    if not vids:
        return out
    try:
        for i in range(0, len(vids), 50):
            chunk = vids[i : i + 50]
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"id": ",".join(chunk), "part": "statistics,snippet"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            if r.status_code != 200:
                print(
                    f"WARN refresh_views: videos.list HTTP {r.status_code} "
                    f"chunk {i // 50 + 1}: {r.text[:150]}",
                    file=sys.stderr,
                )
                break
            for it in r.json().get("items", []):
                st = it.get("statistics", {})
                out[it["id"]] = {
                    "views": int(st.get("viewCount", 0)),
                    "title": it.get("snippet", {}).get("title", ""),
                }
    except requests.RequestException:
        pass
    return out


SLOT_ALIAS = {
    "1": "1",
    "2": "2",
    "3": "3",
    "rezain": "1",
    "seigh": "2",
    "rescey": "3",
    "channel2": "2",
    "channel3": "3",
    "?": "?",
}

SLOT_LABEL = {
    "1": "Slot 1 (ReZain)",
    "2": "Slot 2 (seigh)",
    "3": "Slot 3 (rescey)",
    "?": "Chua gan nhan",
}


def _slot_key(r: dict) -> str:
    raw = str(r.get("slot") or r.get("channel") or "?").strip()
    return SLOT_ALIAS.get(raw.lower(), raw)


def main() -> int:
    today_vn = datetime.now(VN).date()
    today_utc = today_vn.isoformat()
    state = _load(ROOT / "state.json") or []
    hist = _load(ROOT / "views_history.json") or {}

    fresh = refresh_views(state)
    stale = False
    if fresh:
        hist[today_utc] = fresh
        for d in sorted(hist)[:-30]:
            del hist[d]
        try:
            (ROOT / "views_history.json").write_text(
                json.dumps(hist, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            print(f"WARN cannot save views_history.json: {e}", file=sys.stderr)
    elif hist:
        stale = True
        print("WARN refresh failed, using last snapshot", file=sys.stderr)

    days = sorted(hist)
    cur = hist.get(days[-1], {}) if days else {}
    prev = hist.get(days[-2], {}) if len(days) > 1 else {}

    by_slot: dict = {}
    for r in state:
        if not r.get("youtube_id"):
            continue
        slot = _slot_key(r)
        vid = r["youtube_id"]
        v = cur.get(vid, {}).get("views", 0)
        try:
            age_h = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            ).total_seconds() / 3600
        except (ValueError, KeyError, TypeError):
            age_h = 0
        d = by_slot.setdefault(slot, {"n": 0, "views": 0, "top": (0, "")})
        d["n"] += 1
        d["views"] += v
        if v > d["top"][0]:
            d["top"] = (v, cur.get(vid, {}).get("title", vid))

    new_today = [
        r
        for r in state
        if r.get("youtube_id")
        and r.get("created_at", "")[:10] == datetime.now(timezone.utc).date().isoformat()
    ]
    fails = [
        r
        for r in state
        if r.get("status") == "failed"
        and r.get("created_at", "")[:10] == datetime.now(timezone.utc).date().isoformat()
    ]

    total = sum(v.get("views", 0) for v in cur.values())
    total_prev = sum(v.get("views", 0) for v in prev.values())
    gain = total - total_prev if prev else 0

    top = sorted(cur.items(), key=lambda kv: -kv[1].get("views", 0))[:5]
    gainers = sorted(
        ((vid, cur[vid]["views"] - prev.get(vid, {}).get("views", 0)) for vid in cur if vid in prev),
        key=lambda kv: -kv[1],
    )[:5]

    L = []
    L.append(f"# Daily ping {today_vn.strftime('%d/%m/%Y')}")
    L.append("")
    if stale and days:
        L.append(f"_Refresh that bai - dung so lieu cu ngay {days[-1]}._")
        L.append("")
    L.append(f"Total views (all tracked): **{total}** (+{gain} vs snapshot truoc)")
    L.append("")
    L.append("## Theo kenh")
    for slot in sorted(by_slot):
        d = by_slot[slot]
        label = SLOT_LABEL.get(slot, f"Slot {slot}")
        L.append(
            f"- {label}: {d['n']} video, {d['views']} views "
            f"(top: {d['top'][1][:50]} - {d['top'][0]})"
        )
    L.append("")
    L.append(f"## Video moi ({len(new_today)})")
    for r in new_today:
        L.append(
            f"- [{r.get('slot') or r.get('channel')}] {r.get('title', '')[:55]} "
            f"({r.get('status')}) https://www.youtube.com/watch?v={r.get('youtube_id')}"
        )
    L.append("")
    L.append(f"## Fail ({len(fails)})")
    for r in fails:
        L.append(f"- {r.get('title', '')[:55]} :: {(r.get('error') or '')[:120]}")
    L.append("")
    L.append("## Top tang truong")
    for vid, g in gainers:
        L.append(f"- +{g}: {cur[vid].get('title', vid)[:55]}")
    L.append("")
    report = "\n".join(L)
    (ROOT / "DAILY.md").write_text(report, encoding="utf-8")
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", "replace").decode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
