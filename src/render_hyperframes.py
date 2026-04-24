from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, select_autoescape

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


def _sync_hf_project_shared_assets(hf_project_dir: Path, settings: Settings, project_root: Path) -> None:
    """Copy vendor GSAP and optional placeholder into hf_project/assets (used by all render modes)."""
    assets_dir = hf_project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    placeholder_src = project_root / settings.render.placeholder_asset
    placeholder_name = settings.render.placeholder_asset.name
    if placeholder_src.exists():
        shutil.copy2(placeholder_src, assets_dir / placeholder_name)

    gsap_src = project_root / "assets" / "vendor" / "gsap.min.js"
    if not gsap_src.exists():
        raise PipelineError("missing local GSAP runtime: assets/vendor/gsap.min.js", code=40, step="render")
    shutil.copy2(gsap_src, assets_dir / "gsap.min.js")


def render_hyperframes_index(
    meal_scan: MealScan,
    script_plan: ScriptPlan,
    settings: Settings,
    hf_project_dir: Path,
    voice_duration_sec: float,
) -> Path:
    """Prepare hf_project: sync assets; either keep static index.html or render Jinja from tamplate.html."""
    project_root = resolve_project_root(settings)
    index_path = hf_project_dir / "index.html"

    _sync_hf_project_shared_assets(hf_project_dir, settings, project_root)

    if settings.hyperframes.render_mode == "static_project":
        if not index_path.is_file():
            raise PipelineError(
                "static_project mode: missing hf_project/index.html (check hyperframes.project_template_dir)",
                code=40,
                step="render",
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
