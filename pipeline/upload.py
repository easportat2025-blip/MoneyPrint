import json
import time
from pathlib import Path
import requests
import config

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
STATUS_URL = "https://www.googleapis.com/youtube/v3/videos"


def get_access_token() -> str:
    if not (config.YOUTUBE_CLIENT_ID and config.YOUTUBE_REFRESH_TOKEN):
        raise RuntimeError("YOUTUBE_CLIENT_ID / YOUTUBE_REFRESH_TOKEN missing")
    data = {
        "client_id": config.YOUTUBE_CLIENT_ID,
        "client_secret": config.YOUTUBE_CLIENT_SECRET,
        "refresh_token": config.YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    r = requests.post(OAUTH_TOKEN_URL, data=data, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"token refresh failed: {r.status_code} {r.text[:300]}")
    return r.json()["access_token"]


def upload(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    kind: str,
) -> dict:
    token = get_access_token()
    privacy = "public"
    category = "28"
    if kind == "short":
        tags = list({*(tags or []), "shorts", "space", "science"})
        title = title[:90]
        if "#Shorts" not in title and not description.startswith("#Shorts"):
            description = "#Shorts " + description
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],
            "categoryId": category,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    size = video_path.stat().st_size
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(size),
        "X-Upload-Content-Type": "video/mp4",
    }
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
        timeout=60,
    )
    if init.status_code not in (200, 201):
        raise RuntimeError(f"resumable init failed: {init.status_code} {init.text[:400]}")
    upload_url = init.headers.get("Location")
    if not upload_url:
        raise RuntimeError("no upload Location header")

    chunk = 8 * 1024 * 1024
    offset = 0
    with open(video_path, "rb") as f:
        while True:
            if config.kill_requested():
                raise RuntimeError("kill switch on")
            data = f.read(chunk)
            if not data:
                break
            end = offset + len(data) - 1
            h = {
                "Authorization": f"Bearer {token}",
                "Content-Range": f"bytes {offset}-{end}/{size}",
                "Content-Length": str(len(data)),
                "Content-Type": "video/mp4",
            }
            r = requests.put(upload_url, headers=h, data=data, timeout=300)
            if r.status_code in (200, 201):
                result = r.json()
                return _finalize(token, result)
            if r.status_code != 308:
                raise RuntimeError(f"chunk failed: {r.status_code} {r.text[:300]}")
            offset = end + 1
            time.sleep(0.3)
    raise RuntimeError("upload ended without final response")


CAPTION_URL = "https://www.googleapis.com/upload/youtube/v3/captions"


def upload_captions(
    video_id: str, srt_path: Path, language: str = "en", name: str = "English"
) -> str:
    token = get_access_token()
    body = {
        "snippet": {
            "videoId": video_id,
            "language": language,
            "name": name,
            "isDraft": False,
        }
    }
    data = srt_path.read_bytes()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(len(data)),
        "X-Upload-Content-Type": "text/plain",
    }
    init = requests.post(
        CAPTION_URL,
        params={"uploadType": "resumable", "part": "snippet"},
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
        timeout=60,
    )
    if init.status_code not in (200, 201):
        raise RuntimeError(
            f"caption init failed: {init.status_code} {init.text[:300]}"
        )
    location = init.headers.get("Location")
    if not location:
        raise RuntimeError("no caption upload Location")
    r = requests.put(
        location,
        headers={"Content-Length": str(len(data))},
        data=data,
        timeout=120,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"caption put failed: {r.status_code} {r.text[:300]}")
    return r.json().get("id", "")


def delete_video(video_id: str) -> bool:
    token = get_access_token()
    r = requests.delete(
        STATUS_URL,
        params={"id": video_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code in (200, 204):
        return True
    raise RuntimeError(f"delete failed: {r.status_code} {r.text[:300]}")


def _finalize(token: str, result: dict) -> dict:
    vid = result.get("id", "")
    url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
    return {
        "youtube_id": vid,
        "youtube_url": url,
        "title": result.get("snippet", {}).get("title", ""),
    }
