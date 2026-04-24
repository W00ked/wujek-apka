from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .compose_ffmpeg import (
    burn_ass_subtitles,
    concat_videos,
    copy_latest,
    final_trim,
    mux_audio,
    normalize_video,
    probe_duration,
    probe_has_audio,
    truncate_clip_keep_audio,
    trim_or_pad_video,
)
from .config import Settings
from .errors import PipelineError, ValidationError
from .heygen_client import HeyGenClient
from .hyperframes_runner import copy_hf_artifacts_to_page_mirror, run_hyperframes_render
from .image_generation import FoodImageArtifact, prepare_food_image, record_food_image_public_url
from .llm_script import create_script_planner
from .logi_client import build_scan_payload, create_logi_scanner, load_cached_scan
from .logging_utils import configure_logging, get_logger
from .models import MealScan, ScanResponse
from .record_browser import record_page
from .render_html import render_page
from .render_hyperframes import prepare_hf_project_dir, render_hyperframes_index
from .r2_uploader import upload_to_r2
from .subtitles import generate_subtitle_assets
from .tts import create_tts_engine
from .utils import ensure_directory, timestamp_slug


@dataclass
class PipelineRequest:
    dish: str | None = None
    prompt: str | None = None
    image_url: str | None = None
    use_cached_scan: Path | None = None
    skip_intro: bool = False
    regenerate_image: bool = False
    image_variants: int | None = None
    max_image_cost_usd: float | None = None
    allow_high_cost: bool | None = None
    language: str = "en"


def _init_run_dir(settings: Settings) -> Path:
    artifacts_root = ensure_directory(settings.project_root / settings.app.artifacts_dir)
    run_dir = ensure_directory(artifacts_root / timestamp_slug())
    log_path = run_dir / "run.log"
    configure_logging(
        log_path,
        settings.app.log_level,
        [
            settings.secrets.logi_api_key,
            settings.secrets.openai_api_key,
            settings.secrets.google_api_key,
            settings.secrets.heygen_api_key or "",
            settings.secrets.r2_access_key_id or "",
            settings.secrets.r2_secret_access_key or "",
        ],
    )
    return run_dir


def _prepare_dish_image(
    request: PipelineRequest,
    settings: Settings,
    run_dir: Path,
) -> FoodImageArtifact | None:
    if not request.dish:
        return None
    artifact = prepare_food_image(
        request.dish,
        settings,
        run_dir,
        regenerate_image=request.regenerate_image,
        image_variants=request.image_variants,
        max_image_cost_usd=request.max_image_cost_usd,
        allow_high_cost=request.allow_high_cost,
        language=request.language,
    )
    if artifact.public_url:
        return artifact
    upload_result = upload_to_r2(
        artifact.image_path,
        dish=artifact.dish,
        cache_key=artifact.cache_key,
        settings=settings,
    )
    record_food_image_public_url(artifact, upload_result.public_url)
    return artifact


def _validate_request(request: PipelineRequest) -> None:
    has_image_options = bool(
        request.regenerate_image or request.image_variants or request.max_image_cost_usd
    )
    if request.use_cached_scan:
        if has_image_options and not request.dish:
            raise ValidationError("image options require --dish", step="validation")
        return
    input_count = sum(bool(value) for value in (request.dish, request.prompt, request.image_url))
    if input_count != 1:
        raise ValidationError(
            "provide exactly one of --dish, --prompt, or --image-url",
            step="validation",
        )
    if has_image_options and not request.dish:
        raise ValidationError("image options require --dish", step="validation")


def _load_or_scan(
    request: PipelineRequest,
    settings: Settings,
    run_dir: Path,
    food_image: FoodImageArtifact | None = None,
) -> tuple[ScanResponse, MealScan]:
    scan_path = run_dir / "scan.json"
    if request.use_cached_scan:
        logger = get_logger(__name__, step="logi")
        logger.info("loading cached LOGI scan")
        response, meal_scan = load_cached_scan(request.use_cached_scan)
        shutil.copy2(request.use_cached_scan, scan_path)
        return response, meal_scan

    prompt = request.prompt
    image_url = request.image_url
    if food_image:
        prompt = None
        image_url = food_image.public_url
        if not image_url:
            raise PipelineError(
                "generated food image has no public URL for LOGI",
                code=26,
                step="r2",
            )

    payload = build_scan_payload(
        prompt=prompt,
        image_url=image_url,
        language=settings.logi.language,
    )
    scanner = create_logi_scanner(settings)
    return scanner(payload, scan_path)


def run_pipeline(request: PipelineRequest, settings: Settings) -> Path:
    run_dir = _init_run_dir(settings)
    logger = get_logger(__name__, step="pipeline")
    logger.info("starting pipeline run at %s", run_dir)
    _validate_request(request)

    food_image = _prepare_dish_image(request, settings, run_dir)
    response, meal_scan = _load_or_scan(request, settings, run_dir, food_image)

    script_planner = create_script_planner(settings)
    script_plan = script_planner(meal_scan, run_dir / "script_plan.json")

    tts_engine = create_tts_engine(settings)
    voice_path = run_dir / f"voice.{settings.tts.output_format}"
    tts_engine.synthesize(script_plan.tts_transcript_text(), voice_path)
    voice_duration_sec = probe_duration(voice_path, settings)
    logger.info("Gemini voice duration: %.3fs", voice_duration_sec)

    page_dir = ensure_directory(run_dir / "page")
    raw_video_dir = ensure_directory(run_dir / "raw_video")

    if settings.render.ui_backend == "hyperframes":
        hf_project_dir = prepare_hf_project_dir(run_dir, settings)
        render_hyperframes_index(
            meal_scan=meal_scan,
            script_plan=script_plan,
            settings=settings,
            hf_project_dir=hf_project_dir,
            voice_duration_sec=voice_duration_sec,
            food_image_path=food_image.image_path if food_image else None,
            food_image_url=food_image.public_url if food_image else request.image_url,
            dish=request.dish,
            language=request.language,
        )
        copy_hf_artifacts_to_page_mirror(hf_project_dir, page_dir)
        ui_raw_video = run_hyperframes_render(
            hf_project_dir,
            raw_video_dir / "ui_hyperframes.mp4",
            settings,
        )
        ui_warmup_sec = 0.0
    else:
        render_page(
            meal_scan=meal_scan,
            script_plan=script_plan,
            settings=settings,
            output_dir=page_dir,
            voice_duration_sec=voice_duration_sec,
        )
        ui_raw_video = record_page(
            page_dir,
            raw_video_dir,
            settings,
            expected_ui_duration_sec=voice_duration_sec,
        )
        ui_warmup_sec = max(0.0, float(settings.render.ui_warmup_sec))

    ui_normalized = normalize_video(
        ui_raw_video,
        run_dir / "ui_normalized.mp4",
        settings,
        start_offset_sec=ui_warmup_sec,
    )
    ui_video = trim_or_pad_video(
        ui_normalized,
        run_dir / "ui.mp4",
        voice_duration_sec,
        settings,
    )
    ui_with_audio = mux_audio(ui_video, voice_path, run_dir / "ui_with_audio.mp4", settings)

    intro_video: Path | None = None
    if settings.heygen.enabled and not request.skip_intro:
        intro_client = HeyGenClient(settings)
        try:
            intro_raw = intro_client.generate_intro(script_plan.hook_line, run_dir / "intro_raw.mp4")
            intro_raw_duration_sec = probe_duration(intro_raw, settings)
            intro_has_audio = probe_has_audio(intro_raw, settings)
            logger.info(
                "HeyGen intro duration before normalize: %.3fs (has_audio=%s)",
                intro_raw_duration_sec,
                intro_has_audio,
            )
            intro_normalized = normalize_video(
                intro_raw,
                run_dir / "intro_normalized.mp4",
                settings,
                strip_audio=not intro_has_audio,
                fill_canvas=True,
            )
            intro_video = truncate_clip_keep_audio(
                intro_normalized,
                run_dir / "intro.mp4",
                float(settings.render.intro_max_sec),
                settings,
            )
            logger.info("HeyGen intro duration after truncate: %.3fs", probe_duration(intro_video, settings))
        except PipelineError as exc:
            if exc.step == "heygen" and settings.heygen.skip_intro_on_failure:
                logger.warning("HeyGen intro skipped, continuing with UI-only: %s", exc)
            else:
                raise

    stitched_input = ui_with_audio
    if intro_video:
        stitched_input = concat_videos([intro_video, ui_with_audio], run_dir / "stitched.mp4", settings)

    final_path = stitched_input
    if settings.render.max_duration_sec is not None:
        final_path = final_trim(stitched_input, run_dir / "final.mp4", settings)
    if settings.subtitles.enabled:
        _, ass_path = generate_subtitle_assets(final_path, run_dir, settings)
        final_path = burn_ass_subtitles(
            final_path,
            ass_path,
            run_dir / "final_with_subtitles.mp4",
            settings,
        )
    logger.info("Final video duration: %.3fs", probe_duration(final_path, settings))

    output_dir = ensure_directory(settings.project_root / settings.app.output_dir)
    output_name = f"{response.scanId}_{timestamp_slug()}.mp4"
    output_path = output_dir / output_name
    shutil.copy2(final_path, output_path)
    if settings.app.latest_link == "copy":
        copy_latest(output_path, output_dir / "latest.mp4")

    logger.info("pipeline finished: %s", output_path)
    return output_path
