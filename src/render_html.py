from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, select_autoescape

from .config import Settings
from .errors import PipelineError
from .models import MealScan, ScriptPlan
from .render_context import build_template_context, resolve_project_root
from .template_logi import build_playwright_runtime_template


def render_page(
    meal_scan: MealScan,
    script_plan: ScriptPlan,
    settings: Settings,
    output_dir: Path,
    voice_duration_sec: float,
) -> Path:
    project_root = resolve_project_root(settings)
    template_source = (project_root / "tamplate.html").read_text(encoding="utf-8")
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(build_playwright_runtime_template(template_source))

    output_dir.mkdir(parents=True, exist_ok=True)
    placeholder_src = project_root / settings.render.placeholder_asset
    placeholder_dst = output_dir / settings.render.placeholder_asset.name
    if placeholder_src.exists():
        shutil.copy2(placeholder_src, placeholder_dst)

    scroll_driver_src = project_root / "templates" / "scroll_driver.js"
    shutil.copy2(scroll_driver_src, output_dir / "scroll_driver.js")
    gsap_src = project_root / "assets" / "vendor" / "gsap.min.js"
    if not gsap_src.exists():
        raise PipelineError("missing local GSAP runtime: assets/vendor/gsap.min.js", code=40, step="render")
    shutil.copy2(gsap_src, output_dir / "gsap.min.js")

    html = template.render(
        **build_template_context(
            meal_scan=meal_scan,
            script_plan=script_plan,
            settings=settings,
            voice_duration_sec=voice_duration_sec,
        )
    )

    page_path = output_dir / "page.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path
