from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, select_autoescape

from .ad_data import build_logi_ad_data
from .config import Settings
from .errors import PipelineError
from .models import MealScan, ScriptPlan
from .render_context import build_template_context, resolve_project_root
from .template_logi import build_hyperframes_runtime_template


def prepare_hf_project_dir(run_dir: Path, settings: Settings) -> Path:
    """Copy HyperFrames skeleton into this run (isolated from other runs)."""
    template_root = (settings.project_root / settings.hyperframes.project_template_dir).resolve()
    if not template_root.is_dir():
        raise PipelineError(
            f"HyperFrames template directory not found: {template_root}",
            code=40,
            step="render",
        )
    hf_dir = run_dir / "hf_project"
    if hf_dir.exists():
        shutil.rmtree(hf_dir)
    shutil.copytree(template_root, hf_dir)
    return hf_dir


def _sync_hf_project_shared_assets(
    hf_project_dir: Path,
    settings: Settings,
    project_root: Path,
    food_image_path: Path | None = None,
) -> str | None:
    """Copy shared runtime assets into hf_project/assets."""
    assets_dir = hf_project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    placeholder_src = project_root / settings.render.placeholder_asset
    placeholder_name = settings.render.placeholder_asset.name
    if placeholder_src.exists():
        shutil.copy2(placeholder_src, assets_dir / placeholder_name)

    gsap_src = project_root / "assets" / "vendor" / "gsap.min.js"
    if not gsap_src.exists():
        raise PipelineError(
            "missing local GSAP runtime: assets/vendor/gsap.min.js",
            code=40,
            step="render",
        )
    shutil.copy2(gsap_src, assets_dir / "gsap.min.js")

    dynamic_src = project_root / "assets" / "hyperframes" / "dynamic-ad.js"
    if not dynamic_src.exists():
        raise PipelineError(
            "missing HyperFrames dynamic runtime: assets/hyperframes/dynamic-ad.js",
            code=40,
            step="render",
        )
    shutil.copy2(dynamic_src, assets_dir / "dynamic-ad.js")

    if food_image_path and food_image_path.exists():
        image_name = f"generated_food_image{food_image_path.suffix.lower()}"
        shutil.copy2(food_image_path, assets_dir / image_name)
        return f"assets/{image_name}"
    return None


def _inject_dynamic_scripts(html_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8")
    if "logi_ad_data.js" in text and "dynamic-ad.js" in text:
        return
    prefix = "../assets" if html_path.parent.name == "compositions" else "./assets"
    scripts = (
        f'    <script src="{prefix}/logi_ad_data.js"></script>\n'
        f'    <script src="{prefix}/dynamic-ad.js"></script>\n'
    )
    marker = "    <script>\n      window.__timelines"
    if marker in text:
        text = text.replace(marker, scripts + marker, 1)
    else:
        text = text.replace("</body>", scripts + "</body>", 1)
    html_path.write_text(text, encoding="utf-8")


def _write_dynamic_ad_payload(
    *,
    hf_project_dir: Path,
    meal_scan: MealScan,
    script_plan: ScriptPlan,
    food_image_asset: str | None,
    food_image_url: str | None,
    dish: str | None,
    language: str,
) -> None:
    assets_dir = hf_project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    payload = build_logi_ad_data(
        meal_scan=meal_scan,
        script_plan=script_plan,
        dish=dish,
        food_image_asset=food_image_asset,
        food_image_url=food_image_url,
        language=language,
    )
    js = (
        "window.LOGI_AD_DATA = "
        + json.dumps(payload, ensure_ascii=True, indent=2)
        + ";\nwindow.__LOGI_AD_DATA__ = window.LOGI_AD_DATA;\n"
    )
    (assets_dir / "logi_ad_data.js").write_text(js, encoding="utf-8")
    _inject_dynamic_scripts(hf_project_dir / "index.html")


def render_hyperframes_index(
    meal_scan: MealScan,
    script_plan: ScriptPlan,
    settings: Settings,
    hf_project_dir: Path,
    voice_duration_sec: float,
    food_image_path: Path | None = None,
    food_image_url: str | None = None,
    dish: str | None = None,
    language: str = "en",
) -> Path:
    """Prepare hf_project index and dynamic assets."""
    project_root = resolve_project_root(settings)
    index_path = hf_project_dir / "index.html"

    food_image_asset = _sync_hf_project_shared_assets(
        hf_project_dir,
        settings,
        project_root,
        food_image_path,
    )

    if settings.hyperframes.render_mode == "static_project":
        if not index_path.is_file():
            raise PipelineError(
                "static_project mode: missing hf_project/index.html "
                "(check hyperframes.project_template_dir)",
                code=40,
                step="render",
            )
        _write_dynamic_ad_payload(
            hf_project_dir=hf_project_dir,
            meal_scan=meal_scan,
            script_plan=script_plan,
            food_image_asset=food_image_asset,
            food_image_url=food_image_url,
            dish=dish,
            language=language,
        )
        return index_path

    template_source = (project_root / "tamplate.html").read_text(encoding="utf-8")
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(build_hyperframes_runtime_template(template_source))

    ctx = build_template_context(
        meal_scan=meal_scan,
        script_plan=script_plan,
        settings=settings,
        voice_duration_sec=voice_duration_sec,
    )
    placeholder_name = settings.render.placeholder_asset.name
    ctx["placeholder_asset"] = f"assets/{placeholder_name}"

    html = template.render(**ctx)
    index_path.write_text(html, encoding="utf-8")
    return index_path
