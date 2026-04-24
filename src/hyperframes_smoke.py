from __future__ import annotations

from pathlib import Path

from .config import Settings
from .errors import PipelineError
from .hyperframes_runner import run_hyperframes_render
from .models import Ingredient, MealScan, NutritionTotals, ScriptPlan, ScriptSegment
from .models.scan import NutritionValues
from .render_hyperframes import prepare_hf_project_dir, render_hyperframes_index
from .utils import ensure_directory, timestamp_slug


def _dummy_meal_scan() -> MealScan:
    ing = Ingredient(
        name="Demo ingredient",
        nutritional_actual=NutritionValues(
            calories=120.0,
            protein=8.0,
            fat=4.0,
            carbohydrates=14.0,
            glycemic_load=6.0,
        ),
    )
    return MealScan(
        meal_name="HyperFrames smoke meal",
        meal_description="Local smoke test without LOGI, OpenAI images, Gemini TTS, or Whisper.",
        ingredients=[ing],
        potential_health_risks=["Demo risk A", "Demo risk B", "Demo risk C"],
        nutritionists_opinion=["Demo nutritionist note for UI copy."],
        totals=NutritionTotals.from_ingredients([ing]),
    )


def _dummy_script_plan() -> ScriptPlan:
    d = 2.0
    p = 0.05
    return ScriptPlan(
        hook_line="HyperFrames smoke test hook line.",
        segments=[
            ScriptSegment(
                section_id="header",
                script="Smoke header narration.",
                duration_sec=d,
                pause_after_sec=p,
            ),
            ScriptSegment(
                section_id="meal_intro",
                script="Smoke meal intro narration.",
                duration_sec=d,
                pause_after_sec=p,
            ),
            ScriptSegment(
                section_id="nutrition",
                script="Smoke nutrition narration.",
                duration_sec=d,
                pause_after_sec=p,
            ),
            ScriptSegment(
                section_id="ingredients",
                script="Smoke ingredients narration.",
                duration_sec=d,
                pause_after_sec=p,
            ),
            ScriptSegment(
                section_id="insights",
                script="Smoke insights narration.",
                duration_sec=d,
                pause_after_sec=p,
            ),
        ],
    )


def run_hyperframes_smoke(
    settings: Settings,
    *,
    hf_project: Path | None = None,
    output_mp4: Path | None = None,
) -> Path:
    """
    Run only `hyperframes render` on a project directory.

    No Gemini TTS, no Whisper subtitles, no LOGI, no OpenAI image generation.
    """
    root = settings.project_root
    artifacts = ensure_directory(root / settings.app.artifacts_dir)
    run_root = ensure_directory(artifacts / f"hyperframes_smoke_{timestamp_slug()}")
    out_path = output_mp4 or (run_root / "hyperframes_smoke.mp4")
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if hf_project is not None:
        hf_dir = hf_project.resolve()
        index = hf_dir / "index.html"
        if not index.is_file():
            raise PipelineError(
                f"--hf-project must be a directory containing index.html: {hf_dir}",
                code=51,
                step="hyperframes",
            )
    else:
        hf_dir = prepare_hf_project_dir(run_root, settings)
        placeholder = root / settings.render.placeholder_asset
        food_path = placeholder if placeholder.is_file() else None
        render_hyperframes_index(
            meal_scan=_dummy_meal_scan(),
            script_plan=_dummy_script_plan(),
            settings=settings,
            hf_project_dir=hf_dir,
            voice_duration_sec=12.0,
            food_image_path=food_path,
            food_image_url=None,
            dish="smoke test",
            language="en",
        )

    return run_hyperframes_render(hf_dir, out_path, settings)
