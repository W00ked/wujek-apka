from __future__ import annotations

import json
from pathlib import Path

from openai import APIError, APITimeoutError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Settings
from .errors import PipelineError
from .logging_utils import get_logger
from .models import MealScan, ScriptPlan
from .utils import write_json

SYSTEM_PROMPT = """You write punchy English short-form video scripts for a nutrition app.
Return strict JSON only.

The audience is made of people who care about blood sugar, insulin resistance, diabetes, and steady energy.
Write like a smart, empathetic, high-retention TikTok creator who understands health anxiety and wants to help fast.

Non-negotiable rules:
- Base every claim on the provided meal analysis.
- Keep the UI narration synchronized to sections of the app.
- Follow a problem-solution ad arc: tempting food, hidden nutrition question, LOGI scan, clear result, useful next step.
- Use these section ids exactly once and in this exact order:
  header, meal_intro, nutrition, ingredients, insights.
- Every segment must include pause_after_sec (use 0 when there is no pause after that line).
- Every segment script must be exactly one spoken sentence.
- Total UI narration target is about 23 seconds.
- Keep copy crisp, vivid, natural, and spoken out loud.
- Do not invent missing nutrition values.
- If some UI field is hidden because data is missing, do not mention it.
- hook_line is for HeyGen intro, so keep it plain spoken text with no square-bracket tags.
- Do not write like a chatbot, lecturer, brand deck, or generic wellness ad.
- Do not use AI-sounding filler like "packed with", "loaded with", "journey", "game-changer", "guilt-free", "perfect choice", "healthy and delicious", "let's dive in", "let's break it down", or "here's everything you need to know".
- Use contractions naturally when they help the line sound human.
- Prefer active voice, sharp phrasing, and spoken cadence over polished article-style writing.
- Make the viewer feel understood, not judged or scolded.
- Never shame the viewer or use fear-mongering medical language.

Hook rules:
- The hook must compete for attention in the first 1 to 3 seconds.
- A strong hook should do at least two of these things immediately:
  1. call out a real viewer pain, frustration, or misconception,
  2. create a curiosity gap,
  3. promise a fast payoff or useful insight,
  4. present a surprising contrast,
  5. sound like a direct human observation rather than marketing copy.
- Hook formula to prefer:
  pain point or myth + unexpected turn + specific payoff.
- Good hook energy feels like:
  "Wait, this looks healthy, but..."
  "If insulin resistance makes lunch confusing..."
  "This meal is doing one thing right and one thing wrong."
- Avoid weak hooks that sound vague, generic, or overhyped.
- Never start with slow context, greetings, or obvious filler.

Style goals:
- Sound energetic, emotionally engaging, and credible, never clickbait.
- Sound like a real person talking to one viewer, not like a script trying to impress everyone.
- Start with a sharp pattern interrupt, bold question, surprising contrast, or painfully relatable observation.
- Avoid generic openers like "Discover", "Introducing", "Looking for", "This meal is", "healthy and delicious".
- Use concrete numbers when they exist.
- Prefer contrast words such as "but", "without", "instead", or "yet" when natural.
- End the insights segment with a short micro-CTA.
- For segment scripts, you may use short inline audio tags in square brackets when they materially improve delivery.
- Audio tags must stay short, in English, and feel natural for TTS, for example: [excited], [whispers], [short pause], [serious].
- Use at most 1 to 2 audio tags per segment and never let tags dominate the sentence.
- Reserve stronger delivery tags for the header and insights unless the meal data strongly supports them elsewhere.
- Use emotional variety: surprise, relief, tension, curiosity, confidence, reassurance.
- Use empathy-first health language: helpful, practical, supportive, realistic.
- Focus on what the meal means for energy, fullness, blood sugar steadiness, or trade-offs the viewer actually cares about.

Human-sounding writing rules:
- Vary sentence rhythm; do not make every sentence land the same way.
- Favor short, speakable words over formal phrasing.
- Write lines that would sound normal if a creator said them out loud in one take.
- Include a little attitude or personality when useful, but keep it believable.
- If a line sounds like a caption template, rewrite it mentally into something a person would actually say.
- Each segment should feel like it pushes the story forward, not like a label for the UI section.

Health-content rules:
- Be supportive and practical for insulin resistance / diabetes audiences.
- Prefer non-shaming reframes like what to watch, what to add, what trade-off to notice, or what makes the meal easier to handle.
- If risks are mentioned, frame them clearly but calmly.
- Balance hype with trust: energetic delivery, grounded claims.

Length targets:
- hook_line: 6 to 12 words.
- header: 7 to 12 words.
- meal_intro: 10 to 16 words.
- nutrition: 12 to 18 words.
- ingredients: 10 to 16 words.
- insights: 10 to 16 words.
- Aim for roughly 55 to 75 total words across all segment scripts.
"""


def build_schema() -> dict:
    return {
        "name": "script_plan",
        "strict": True,
        "schema": ScriptPlan.model_json_schema(),
    }


def normalize_segment_durations(plan: ScriptPlan, target_total_sec: float) -> ScriptPlan:
    scaled_segments = plan.scaled_segments(target_total_sec)
    return ScriptPlan(
        hook_line=plan.hook_line,
        segments=scaled_segments,
    )


def build_user_prompt(meal_scan: MealScan, target_total_sec: float) -> str:
    public_payload = {
        "meal_name": meal_scan.meal_name,
        "meal_description": meal_scan.meal_description,
        "totals": meal_scan.totals.model_dump(),
        "ingredients": [item.model_dump() for item in meal_scan.ingredients],
        "potential_health_risks": meal_scan.potential_health_risks,
        "nutritionists_opinion": meal_scan.nutritionists_opinion,
        "constraints": {
            "language": "English",
            "target_ui_seconds": target_total_sec,
            "missing_fields_policy": "hidden if missing, never invent values",
            "section_order": ["header", "meal_intro", "nutrition", "ingredients", "insights"],
            "segment_style": "one sentence per section, spoken, emotional, concrete",
            "hook_requirements": "fast, memorable, specific, credible, scroll-stopping in the first seconds",
            "insights_ending": "finish with a short micro-CTA",
            "audio_tags_policy": {
                "hook_line": "no square-bracket tags",
                "segments": "optional English audio tags like [excited], [whispers], [short pause]",
                "max_tags_per_segment": 2,
                "goal": "make Gemini TTS more expressive without sounding cheesy or overacted",
            },
            "tiktok_retention_rules": [
                "start with the strongest idea immediately",
                "make the first line feel personally relevant",
                "avoid slow setup",
                "use curiosity, contrast, or a useful promise early",
                "every line should earn the next second of attention",
            ],
            "preferred_hook_types": [
                "relatable struggle",
                "myth-bust",
                "surprising contrast",
                "fast payoff",
                "you versus the problem",
            ],
            "audience": "people worried about blood sugar, insulin resistance, diabetes, cravings, and energy crashes",
            "tone_guardrails": [
                "human, direct, creator-like",
                "empathetic, not scolding",
                "high-retention TikTok voiceover energy",
                "not robotic, not corporate, not generic AI prose",
            ],
            "hook_formula": "pain point or myth + surprising turn + specific payoff",
            "writing_bans": [
                "generic wellness slogans",
                "obvious AI phrasing",
                "empty hype",
                "fear-based shaming",
            ],
        },
    }
    return json.dumps(public_payload, ensure_ascii=True, indent=2)


def create_script_planner(settings: Settings):
    logger = get_logger(__name__, step="openai")
    client = OpenAI(api_key=settings.secrets.openai_api_key, timeout=settings.openai.timeout_sec)

    @retry(
        retry=retry_if_exception_type((APIError, APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(settings.openai.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    def _generate(meal_scan: MealScan, output_path: Path) -> ScriptPlan:
        logger.info("requesting OpenAI structured script plan")
        try:
            response = client.chat.completions.create(
                model=settings.openai.model,
                response_format={"type": "json_schema", "json_schema": build_schema()},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_user_prompt(
                            meal_scan,
                            settings.render.ui_target_duration_sec,
                        ),
                    },
                ],
            )
        except (APIError, APITimeoutError, RateLimitError):
            logger.warning("OpenAI request failed with retryable error")
            raise
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(f"OpenAI request failed: {exc}", code=20, step="openai") from exc

        content = response.choices[0].message.content
        if not content:
            raise PipelineError("OpenAI returned empty content", code=20, step="openai")

        try:
            raw = json.loads(content)
            plan = ScriptPlan.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            raise PipelineError(f"OpenAI returned invalid ScriptPlan: {exc}", code=20, step="openai") from exc

        normalized = normalize_segment_durations(plan, settings.render.ui_target_duration_sec)
        write_json(output_path, normalized.model_dump())
        return normalized

    return _generate
