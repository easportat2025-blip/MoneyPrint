import gemini_client


SCRIPT_PROMPT = """Write a natural {lang} voiceover script for a faceless documentary
video titled: "{title}"

Scenes and narration drafts:
{scenes}

Rules:
- FIRST LINE = the hook: spoken question/claim matching the title,
  under 10 words, no greeting ("hey guys" banned)
- Spoken style, present tense, concrete imagery
- No scene numbers, no stage directions, no emojis
- Open loop early, escalate mid, payoff in the FINAL line (loop-friendly)
- WRITE EVERYTHING IN {lang}. No other language anywhere.
- STRICT LENGTH: total voiceover MUST be under {target_chars} characters
  (count roughly, shorter is fine, longer is NOT allowed)

Return JSON: {{"description":"YouTube description 2-4 sentences with 3 hashtags, in {lang}",
"voiceover":"full continuous script in {lang}"}}
"""


def build(idea: dict, scenes: list, target_chars: int = 750) -> dict:
    import config

    lang = config.LANG_NAME
    drafts = []
    for i, s in enumerate(scenes, 1):
        drafts.append(f"{i}. {s['narration']}")
    client = gemini_client.GeminiClient()
    prompt = SCRIPT_PROMPT.format(
        title=idea.get("title", ""),
        scenes="\n".join(drafts),
        lang=lang,
        target_chars=target_chars,
    )
    data = client.generate_json(prompt, temperature=0.5)
    voiceover = (data.get("voiceover") or "").strip()
    description = (data.get("description") or "").strip()
    if not voiceover:
        voiceover = " ".join(s["narration"] for s in scenes)
    if not description:
        description = idea.get("hook", "")
    return {"voiceover": voiceover, "description": description}
