from pathlib import Path
import config
import state
from pipeline import plan as plan_mod
from pipeline import research as research_mod
from pipeline import script as script_mod
from pipeline import tts as tts_mod
from pipeline import media as media_mod
from pipeline import assemble as assemble_mod
from pipeline import upload as upload_mod
from pipeline import cleanup as cleanup_mod


def _check_quota() -> bool:
    return state.uploads_today() < config.MAX_DAILY_UPLOADS


def run_one(kind: str = "short") -> dict:
    if config.kill_requested():
        raise RuntimeError("kill switch on")
    if not _check_quota():
        raise RuntimeError("daily upload quota reached")

    if kind == "short":
        duration = config.SHORT_MAX_SEC - 5
        scene_sec = config.SHORT_SCENE_SEC
    else:
        duration = 420
        scene_sec = config.LONG_SCENE_SEC

    idea = plan_mod.next_idea(kind)
    rec = state.create(kind, idea)
    rec_id = rec["id"]
    workdir = config.CACHE_DIR / rec_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        state.update(rec_id, status="researching")
        scenes = research_mod.research(idea, duration, scene_sec)
        state.stage(rec_id, "research", True, f"{len(scenes)} scenes")
        state.update(rec_id, scenes=scenes)

        state.update(rec_id, status="scripting")
        script = script_mod.build(idea, scenes)
        state.stage(rec_id, "script", True)

        state.update(rec_id, status="tts")
        audio_path = workdir / "voice.mp3"
        tts_mod.synthesize(script["voiceover"], audio_path)
        audio_dur = tts_mod.duration(audio_path)
        state.stage(rec_id, "tts", True, f"{audio_dur:.1f}s")

        target = duration if kind == "short" else max(duration, int(audio_dur) + 10)
        n_scenes = max(len(scenes), int(target / scene_sec) + 1)
        if n_scenes > len(scenes):
            extra = research_mod.research(
                idea, n_scenes * scene_sec, scene_sec
            )
            seen = {s["narration"] for s in scenes}
            for s in extra:
                if s["narration"] not in seen and len(scenes) < n_scenes:
                    scenes.append(s)
                    seen.add(s["narration"])
            state.update(rec_id, scenes=scenes)

        state.update(rec_id, status="fetching_media")
        vertical = kind == "short"
        images = media_mod.fetch_all(scenes, workdir / "media", vertical)
        state.stage(rec_id, "media", True, f"{len(images)} images")

        state.update(rec_id, status="rendering")
        final = assemble_mod.assemble(images, audio_path, workdir / "render", kind)
        state.stage(rec_id, "render", True, f"{final.stat().st_size} bytes")

        state.update(rec_id, status="uploading")
        tags = idea.get("tags") or ["space", "science"]
        result = upload_mod.upload(
            final,
            idea.get("title", "ReZain"),
            script["description"],
            tags,
            kind,
        )
        state.update(
            rec_id,
            status="uploaded",
            youtube_id=result["youtube_id"],
            youtube_url=result["youtube_url"],
            title=result.get("title") or idea.get("title", ""),
        )
        state.stage(rec_id, "upload", True, result["youtube_url"])

        state.update(rec_id, status="cleaning")
        cleanup_mod.job_workdir(workdir)
        state.update(rec_id, status="done")
        state.stage(rec_id, "cleanup", True)
        return state.get(rec_id)

    except Exception as e:
        state.update(rec_id, status="failed", error=str(e)[:500])
        state.stage(rec_id, "error", False, str(e)[:500])
        raise
