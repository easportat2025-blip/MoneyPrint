import time
from google import genai
from google.genai import errors
import config


class GeminiError(Exception):
    pass


class GeminiClient:
    def __init__(self, keys=None, model=None, max_retries=6):
        self.keys = list(keys or config.GEMINI_KEYS)
        self.model = model or config.GEMINI_MODEL
        self.max_retries = max_retries
        if not self.keys:
            raise GeminiError("no GEMINI keys configured")

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        last_err = None
        attempts = 0
        idx = 0
        while attempts < self.max_retries:
            if config.kill_requested():
                raise GeminiError("kill switch on")
            key = self.keys[idx % len(self.keys)]
            try:
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={"temperature": temperature},
                )
                text = (resp.text or "").strip()
                if not text:
                    raise GeminiError("empty response")
                return text
            except errors.APIError as e:
                last_err = e
                code = getattr(e, "code", None)
                if code in (429, 503, 500, None):
                    idx += 1
                    attempts += 1
                    time.sleep(min(2**attempts, 60))
                    continue
                raise GeminiError(str(e)) from e
            except Exception as e:
                last_err = e
                idx += 1
                attempts += 1
                time.sleep(min(2**attempts, 60))
        raise GeminiError(f"all retries failed: {last_err}")

    def generate_json(self, prompt: str, temperature: float = 0.5):
        import json
        import re

        text = self.generate(
            prompt + "\n\nReturn ONLY valid JSON. No markdown fences, no commentary.",
            temperature=temperature,
        )
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
        start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
        end = max(text.rfind("}"), text.rfind("]"))
        if end > start:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise GeminiError(f"invalid json: {e}: {text[:300]}") from e
