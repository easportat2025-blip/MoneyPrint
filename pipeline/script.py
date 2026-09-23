import gemini_client


SCRIPT_PROMPT = """Write a natural English voiceover script for a faceless documentary
video titled: "{title}"

Scenes and narration drafts:
{scenes}

Rules:
- Spoken style, present tense, concrete imagery, no "hey guys"
- No scene numbers, no stage directions, no emojis
- Smooth transitions between scenes
- Total length should match the draft narrations roughly (do not double length)

Return JSON: {{"description":"YouTube description 2-4 sentences with 3 hashtags",
"voiceover":"full continuous script"}}
"""


def build(idea: dict, scenes: list) -> dict:
    drafts = []
    for i, s in enumerate(scenes, 1):
        drafts.append(f"{i}. {s['narration']}")
    client = gemini_client.GeminiClient()
    prompt = SCRIPT_PROMPT.format(
        title=idea.get("title", ""),
        scenes="\n".join(drafts),
    )
    data = client.generate_json(prompt, temperature=0.5)
    voiceover = (data.get("voiceover") or "").strip()
    description = (data.get("description") or "").strip()
    if not voiceover:
        voiceover = " ".join(s["narration"] for s in scenes)
    if not description:
        description = idea.get("hook", "")
    return {"voiceover": voiceover, "description": description}
