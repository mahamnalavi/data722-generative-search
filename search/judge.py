"""The judge: a second AI, from a different company, that grades the system's outputs.

Answering model: gpt-oss-120b (Groq). Query writer: Claude (Anthropic). Judge: Gemini (Google).
Three different model families, so no model grades its own work.

What it grades:
  - chat answers: is the first suggested product right for the need (good / partial / wrong)?
    Is every stated reason supported by the product's facts (yes / no)? Is the reply in the
    shopper's language (yes / no)?
  - definitions: is the AI definition accurate for the product's facts (Y / P / N), the
    same scale the student used in the hand-check, so judge and human can be compared.

Several items are graded per call (free-tier quota), and every verdict is saved as it
arrives, so an interrupted run resumes where it stopped.
"""

import json
import os
import time

from .llm import USAGE, _parse_json

PREFERRED = ("flash-lite", "flash")
SKIP = ("image", "tts", "audio", "live", "embedding", "vision", "thinking-exp", "learnlm", "gemma")

CHAT_RUBRIC = """You are grading a shopping assistant for an online household-goods store in Pakistan.
For each item you get the shopper's request, the assistant's reply, and the products it suggested with their facts.
Grade each item:
- "first_pick": "good" if the first suggested product does what the shopper asked for, "partial" if related but not
  quite, "wrong" if not. Use "none" if no product was suggested.
- "reasons_supported": "yes" if every reason given is supported by that product's listed facts or uses, else "no".
  Use "n/a" if no product was suggested.
- "language_match": "yes" if the reply is in the shopper's language (English, Urdu script or Roman Urdu), else "no".
- "note": at most 12 words explaining any "partial", "wrong" or "no".
Judge only from what is shown. Return JSON: {"grades": [{"id": "...", "first_pick": "...", "reasons_supported": "...", "language_match": "...", "note": "..."}]}

ITEMS:
"""

DEF_RUBRIC = """You are checking product descriptions for an online household-goods store.
For each item you get the product's facts and an AI-written definition of what it is for.
Grade each definition:
- "Y": accurate and useful
- "P": partly right (a small error, or an obvious use missing)
- "N": wrong or misleading (states something the facts do not support, or the wrong use)
Add a "note" of at most 12 words for P or N.
Return JSON: {"grades": [{"id": "...", "verdict": "Y|P|N", "note": "..."}]}

ITEMS:
"""


class GeminiJudge:
    def __init__(self, api_key=None, model=None):
        from google import genai
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model = model or self.pick_model()

    def pick_model(self):
        names = [m.name for m in self.client.models.list()
                 if "generateContent" in (m.supported_actions or []) and not any(x in m.name for x in SKIP)]
        for pref in PREFERRED:
            stable = [n for n in names if pref in n and "preview" not in n and "exp" not in n]
            if stable:
                return sorted(stable)[-1]
        if not names:
            raise RuntimeError("No Gemini text model available for judging")
        return sorted(names)[-1]

    def grade(self, rubric, items, task):
        from google.genai import types
        prompt = rubric + json.dumps(items, ensure_ascii=False, indent=1)
        cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json")
        for attempt in range(6):
            t0 = time.time()
            try:
                r = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
                break
            except Exception as e:
                if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < 5:
                    print(f"  judge rate limit; waiting 30s (attempt {attempt + 1})")
                    time.sleep(30)
                    continue
                raise
        um = r.usage_metadata
        USAGE.add(task, self.model, getattr(um, "prompt_token_count", 0) or 0,
                  (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0),
                  time.time() - t0, len(items))
        return {g["id"]: g for g in _parse_json(r.text).get("grades", []) if "id" in g}


def run_batches(judge, rubric, items, task, cache_file, batch_size=8, pause=4):
    """Grade items in batches, saving after every batch; items already in cache_file are skipped."""
    done = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
    todo = [it for it in items if it["id"] not in done]
    for i in range(0, len(todo), batch_size):
        batch = todo[i:i + batch_size]
        try:
            done.update(judge.grade(rubric, batch, task))
        except Exception as e:
            print(f"  stopped: {type(e).__name__}: {str(e)[:160]}. Re-run this cell later to resume.")
            break
        json.dump(done, open(cache_file, "w"), indent=1, ensure_ascii=False)
        print(f"  graded {len(done)}/{len(items)}")
        time.sleep(pause)
    return done
