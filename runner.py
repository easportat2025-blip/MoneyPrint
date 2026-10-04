from pathlib import Path
import config
import state
from pipeline import plan as plan_mod
from pipeline import research as research_mod
from pipeline import script as script_mod
from pipeline import tts as tts_mod
from pipeline import media as media_mod
from pipeline import assemble as assemble_mod
from pipeline import music as music_mod
from pipeline import upload as upload_mod
from pipeline import cleanup as cleanup_mod


def pick_keyframes(n: int, k: int) -> set:
    """Hook (0) + payoff (n-1) + evenly spaced middles, max k keyframes."""
    if n <= 0:
        return set()
    k = max(2, min(k, n))
    if k == 2:
        return {0, n - 1}
    mids = set()
    for j in range(1, k - 1):
        mids.add(round(j * (n - 1) / (k - 1)))
    return {0, n - 1} | mids


def _check_quota() -> bool:
    return state.uploads_today() < config.MAX_DAILY_UPLOADS


FATAL_PATTERNS = [
    "missing",
    "insufficient",
    "invalid_grant",
    "access_denied",
    "unauthorized",
    "quotaexceeded",
    "uploadlimitexceeded",
    "verify failed",
    "kill switch",
    "daily upload quota",
]


def _fatal(msg: str) -> bool:
    m = msg.lower()
    return any(p in m for p in FATAL_PATTERNS)


def attempt(rec_id: str, stage: str, fn, *args, retries: int = None, **kwargs):
    import time

    tries = 1 + (config.RETRY_MAX if retries is None else retries)
    last = None
    for i in range(tries):
        if config.kill_requested():
            raise RuntimeError("kill switch on")
        try:
            out = fn(*args, **kwargs)
            if i > 0:
                state.stage(rec_id, stage, True, f"ok sau {i + 1} lan thu")
            return out
        except Exception as e:
            last = e
            msg = str(e)[:300]
            if _fatal(msg):
                raise
            if i < tries - 1:
                wait = config.RETRY_BASE_SEC * (2**i)
                state.stage(rec_id, stage, False, f"thu {i + 1} loi: {msg} - doi {wait}s")
                time.sleep(wait)
    raise last


def run_one(kind: str = "short") -> dict:
    if config.kill_requested():
        raise RuntimeError("kill switch on")
    if not _check_quota():
        raise RuntimeError("daily upload quota reached")

    if kind == "short":
        duration = config.SHORT_MAX_SEC - 5
        scene_sec = config.SHORT_SCENE_SEC
    else:
        duration = config.LONG_TARGET_SEC
        scene_sec = config.LONG_SCENE_SEC
    stickman_mode = config.VISUAL_STYLE == "stickman"
    research_sec = config.STICKMAN_SCENE_SEC if stickman_mode else scene_sec

    idea = plan_mod.next_idea(kind)
    rec = state.create(kind, idea, config.CHANNEL_NAME, config.CHANNEL)
    rec_id = rec["id"]
    workdir = config.CACHE_DIR / rec_id
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        state.update(rec_id, status="researching")
        scenes = research_mod.research(idea, duration, research_sec)
        state.stage(rec_id, "research", True, f"{len(scenes)} scenes")
        state.update(rec_id, scenes=scenes)

        state.update(rec_id, status="scripting")
        target_chars = 700 if kind == "short" else 5800
        script = script_mod.build(idea, scenes, target_chars)
        vo, trimmed = tts_mod.fit_to_cap(
            script["voiceover"], (duration if kind == "short" else 600) - 3, config.LANG
        )
        if trimmed:
            script["voiceover"] = vo
        state.stage(
            rec_id,
            "script",
            True,
            f"{len(script['voiceover'])} chars"
            + (f" (cat {trimmed} de vua 55s)" if trimmed else ""),
        )

        state.update(rec_id, status="tts")
        audio_path = workdir / "voice.mp3"
        srt_tmp = workdir / "voice.srt"
        audio_path, used_voice = attempt(
            rec_id,
            "tts",
            tts_mod.synthesize,
            script["voiceover"],
            audio_path,
            srt_path=srt_tmp,
        )
        audio_dur = tts_mod.duration(audio_path)
        sentences = tts_mod.parse_sentences(srt_tmp)
        try:
            shift = tts_mod.trim_leading_silence(audio_path)
            if shift > 0:
                sentences = tts_mod.shift_sentences(sentences, shift)
                audio_dur = tts_mod.duration(audio_path)
        except Exception as e:
            shift = 0.0
            state.stage(rec_id, "trim", False, str(e)[:150])
        state.stage(
            rec_id, "tts", True, f"{audio_dur:.1f}s {used_voice} {len(sentences)} cau"
        )

        state.update(rec_id, status="mixing_music")
        mixed_path = workdir / "mixed.m4a"
        _, credit = attempt(
            rec_id, "music", music_mod.mix, audio_path, mixed_path, seed=rec_id
        )
        state.stage(rec_id, "music", True, credit or "voice only")

        target = duration if kind == "short" else max(duration, int(audio_dur) + 10)
        eff_sec = research_sec if stickman_mode else scene_sec
        n_scenes = max(len(scenes), int(target / eff_sec) + 1)
        if n_scenes > len(scenes):
            extra = research_mod.research(
                idea, n_scenes * eff_sec, eff_sec
            )
            seen = {s["narration"] for s in scenes}
            for s in extra:
                if s["narration"] not in seen and len(scenes) < n_scenes:
                    scenes.append(s)
                    seen.add(s["narration"])
            state.update(rec_id, scenes=scenes)

        state.update(rec_id, status="fetching_media")
        vertical = kind == "short"
        credits = []
        if config.VISUAL_STYLE == "stickman":
            from pipeline import stickman

            base = workdir / "render" / "base.mp4"
            cap_total = min(audio_dur, duration) if kind == "short" else audio_dur
            n = max(3, int(cap_total / config.STICKMAN_SCENE_SEC))
            use = scenes[:n] if len(scenes) >= n else (
                list(scenes) + [scenes[-1]] * (n - len(scenes))
            )
            seconds = max(cap_total / len(use), 1.0)
            n_keys = 5 if kind == "short" else 8
            keyframes = pick_keyframes(len(use), n_keys)
            stickman.render(
                use,
                base,
                w=config.SHORT_W if vertical else config.LONG_W,
                h=config.SHORT_H if vertical else config.LONG_H,
                fps=config.STICKMAN_FPS,
                seconds_per_scene=seconds,
                watermark=f"@{config.CHANNEL_NAME}",
                keyframes=keyframes,
            )
            items = [(base, True, "", "")]
            state.stage(
                rec_id,
                "media",
                True,
                f"stickman {len(use)} scenes / {len(keyframes)} keyframes "
                f"{base.stat().st_size} bytes",
            )
        else:
            skip = state.used_media_urls()
            items = attempt(
                rec_id,
                "media",
                media_mod.fetch_all,
                scenes,
                workdir / "media",
                vertical,
                scene_sec,
                skip,
            )
            n_vid = sum(1 for _, is_v, _u, _c in items if is_v)
            urls = [u for _, _, u, _c in items if u]
            credits = sorted({c for _, _, _u, c in items if c})
            state.update(rec_id, media_urls=urls)
            state.stage(
                rec_id,
                "media",
                True,
                f"{n_vid} video clips + {len(items) - n_vid} images",
            )
        hook_checks = []
        hook_checks.append(("motion-first-frame", bool(items and items[0][1])))
        hook_checks.append(
            (
                "first-word-instant",
                bool(sentences and sentences[0]["start"] < 0.2),
            )
        )
        hook_checks.append(
            (
                "hook-short",
                bool(
                    sentences and len(sentences[0]["text"].split()) <= 12
                ),
            )
        )
        passed = [k for k, v in hook_checks if v]
        state.stage(
            rec_id,
            "hook3s",
            len(passed) == len(hook_checks),
            f"{len(passed)}/{len(hook_checks)}: " + ", ".join(passed),
        )

        state.update(rec_id, status="rendering")
        title_text = idea.get("title") or config.CHANNEL_NAME
        final, srt_path = attempt(
            rec_id,
            "render",
            assemble_mod.assemble,
            items,
            mixed_path,
            sentences,
            scenes,
            audio_dur,
            title_text,
            workdir / "render",
            kind,
        )
        info = assemble_mod.probe(final)
        state.stage(
            rec_id,
            "render",
            True,
            f"{info['width']}x{info['height']} {info['duration']:.1f}s "
            f"{final.stat().st_size} bytes",
        )

        state.update(rec_id, status="uploading")
        tags = idea.get("tags") or ["space", "science"]
        description = script["description"]
        if credit:
            description += f"\n\nMusic: {credit}"
        if credits:
            description += "\nImagery: " + "; ".join(credits[:4])
        if kind == "long":
            chapters = assemble_mod.build_chapters(
                scenes, sentences, idea.get("beats")
            )
            if chapters.count("\n") >= 2:
                description += "\n\nChapters:\n" + chapters
                state.stage(
                    rec_id, "chapters", True, f"{chapters.count(chr(10)) + 1} chapters"
                )
        result = attempt(
            rec_id,
            "upload",
            upload_mod.upload,
            final,
            idea.get("title", "ReZain"),
            description,
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

        vid = result["youtube_id"]
        series = f"{config.CHANNEL_NAME} Shorts"
        no_scope = False

        def _skip(name: str) -> bool:
            state.stage(
                rec_id,
                name,
                False,
                "bo qua: token thieu scope force-ssl (login lai de bat)",
            )
            return False

        if config.ENABLE_CAPTIONS and not no_scope:
            try:
                cap_id = upload_mod.upload_captions(vid, srt_path)
                state.stage(rec_id, "captions", bool(cap_id), cap_id or "het quota units")
            except upload_mod.MissingScopeError:
                no_scope = True
                _skip("captions")
            except Exception as e:
                state.stage(rec_id, "captions", False, str(e)[:200])

        if config.ENABLE_THUMB:
            try:
                tp = workdir / "render" / "thumb.png"
                if kind == "long":
                    assemble_mod.build_thumb(final, idea.get("title", ""), tp)
                else:
                    assemble_mod.build_short_thumb(final, idea.get("title", ""), tp)
                ok = upload_mod.set_thumbnail(vid, tp)
                state.stage(rec_id, "thumbnail", ok, f"{tp.stat().st_size} bytes")
            except Exception as e:
                print(f"[thumbnail] FULL ERROR: {e}", flush=True)
                state.stage(rec_id, "thumbnail", False, str(e)[:200])

        if config.ENABLE_COMMENT and not no_scope:
            try:
                q = script.get("question") or ""
                txt = f"{q}\n\nFollow for more {config.NICHE.split(',')[0]} shorts.".strip()
                cid = upload_mod.insert_comment(vid, txt)
                state.stage(rec_id, "comment", bool(cid), cid or "het quota")
            except upload_mod.MissingScopeError:
                no_scope = True
                _skip("comment")
            except Exception as e:
                state.stage(rec_id, "comment", False, str(e)[:200])

        if config.ENABLE_PLAYLIST and not no_scope:
            try:
                pid = upload_mod.ensure_playlist(series)
                ok = upload_mod.add_to_playlist(pid, vid)
                state.stage(rec_id, "playlist", ok, series)
            except upload_mod.MissingScopeError:
                no_scope = True
                _skip("playlist")
            except Exception as e:
                state.stage(rec_id, "playlist", False, str(e)[:200])

        state.stage(
            rec_id,
            "units",
            True,
            f"{state.units_spent_today()}/{state.UNITS_BUDGET} used today",
        )

        state.update(rec_id, status="cleaning")
        cleanup_mod.job_workdir(workdir)
        state.update(rec_id, status="done")
        state.stage(rec_id, "cleanup", True)
        return state.get(rec_id)

    except Exception as e:
        state.update(rec_id, status="failed", error=str(e)[:500])
        state.stage(rec_id, "error", False, str(e)[:500])
        raise
