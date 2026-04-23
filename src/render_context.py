"""Shared Jinja context for Playwright and HyperFrames HTML renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .models import MealScan, ScriptPlan
from .utils import round_display


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_emphasis_targets(section_id: str, script: str, meal_scan: MealScan) -> list[str]:
    script_lower = script.lower()
    if section_id == "header":
        return []
    if section_id == "meal_intro":
        return ["meal_title", "meal_description"]
    if section_id == "nutrition":
        targets: list[str] = []
        keyword_map = {
            "glycemic_load": ("blood sugar", "glycemic", "glucose", "sugar"),
            "calories": ("calorie", "calories"),
            "protein": ("protein",),
            "fat": ("fat", "fats"),
            "carbohydrates": ("carb", "carbs", "carbohydrate", "carbohydrates"),
            "saturated": ("saturated",),
        }
        for target, keywords in keyword_map.items():
            if any(keyword in script_lower for keyword in keywords):
                targets.append(target)
        return _dedupe_keep_order(targets or ["glycemic_load", "calories", "protein", "fat"])
    if section_id == "ingredients":
        targets = [
            f"ingredient:{ingredient.name}"
            for ingredient in meal_scan.ingredients
            if ingredient.name and ingredient.name.lower() in script_lower
        ]
        if not targets:
            targets = [f"ingredient:{ingredient.name}" for ingredient in meal_scan.ingredients[:3]]
        return _dedupe_keep_order(targets[:4])
    if section_id == "insights":
        targets = [f"insight:{idx}" for idx, _ in enumerate(meal_scan.nutritionists_opinion[:2])]
        if meal_scan.potential_health_risks:
            targets.append("risk:0")
        return _dedupe_keep_order(targets or ["insight:0"])
    return []


def _cue(offset_sec: float, cue_type: str, target: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"offset_sec": round(max(0.0, offset_sec), 3), "type": cue_type}
    if target:
        payload["target"] = target
    return payload


def _build_micro_cues(section_id: str, duration_sec: float, emphasis_targets: list[str]) -> list[dict[str, Any]]:
    duration = max(0.6, float(duration_sec))

    def at(value: float) -> float:
        return round(min(max(0.0, value), max(0.0, duration - 0.18)), 3)

    cues: list[dict[str, Any]] = []
    if section_id == "header":
        return []
    elif section_id == "meal_intro":
        cues.extend(
            [
                _cue(at(1.15), "accent_nudge", emphasis_targets[0] if emphasis_targets else "meal_title"),
                _cue(at(2.35), "accent_nudge", emphasis_targets[-1] if emphasis_targets else "meal_description"),
            ]
        )
    elif section_id == "nutrition":
        for idx, target in enumerate(emphasis_targets[:4]):
            cues.append(_cue(at(0.8 + idx * 1.0), "stat_pulse", target))
    elif section_id == "ingredients":
        cues.append(_cue(at(0.24), "ingredient_stagger", "ingredients"))
        for idx, target in enumerate(emphasis_targets[:3]):
            cues.append(_cue(at(1.1 + idx * 1.1), "ingredient_focus", target))
    elif section_id == "insights":
        if emphasis_targets:
            cues.append(_cue(at(1.0), "insight_spotlight", emphasis_targets[0]))
        if len(emphasis_targets) > 1:
            cues.append(_cue(at(2.2), "insight_spotlight", emphasis_targets[1]))
        cues.append(_cue(at(max(0.3, duration - 1.1)), "section_settle", "insights"))
    return cues


def _build_motion_segments(script_plan: ScriptPlan, meal_scan: MealScan) -> list[dict[str, Any]]:
    presets = {
        "header": ("hook", "snap"),
        "meal_intro": ("intro", "smooth"),
        "nutrition": ("nutrition_focus", "smooth"),
        "ingredients": ("ingredient_scan", "scan"),
        "insights": ("insight_payoff", "settle"),
    }
    motion_segments: list[dict[str, Any]] = []
    for segment in script_plan.segments:
        visual_style, camera_mode = presets.get(segment.section_id, ("default", "smooth"))
        emphasis_targets = _build_emphasis_targets(segment.section_id, segment.script, meal_scan)
        motion_segments.append(
            {
                **segment.model_dump(),
                "visual_style": visual_style,
                "camera_mode": camera_mode,
                "emphasis_targets": emphasis_targets,
                "micro_cues": _build_micro_cues(segment.section_id, segment.duration_sec, emphasis_targets),
            }
        )
    return motion_segments


def video_script_json_for_inline(video_script: dict[str, Any]) -> str:
    raw = json.dumps(video_script, ensure_ascii=True)
    return raw.replace("</", "\\u003c/")


def build_template_context(
    meal_scan: MealScan,
    script_plan: ScriptPlan,
    settings: Settings,
    voice_duration_sec: float,
) -> dict[str, Any]:
    placeholder_asset = settings.render.placeholder_asset.name
    ingredients = list(meal_scan.ingredients)

    gl_sum = 0.0
    gl_any = False
    for ing in ingredients:
        v = ing.nutritional_actual.glycemic_load
        if v is not None:
            gl_sum += float(v)
            gl_any = True
    total_gl = None if not gl_any else gl_sum

    opinions = meal_scan.nutritionists_opinion or [meal_scan.meal_description or "No extra insight available."]
    video_script = {
        "motion_version": 1,
        "hook_line": script_plan.hook_line,
        "target_ui_duration_sec": voice_duration_sec,
        "end_hold_sec": max(0.0, float(settings.render.ui_end_hold_sec)),
        "segments": _build_motion_segments(script_plan, meal_scan),
    }

    w = int(settings.render.width)
    h = int(settings.render.height)
    comp_dur = max(0.5, float(voice_duration_sec))

    return {
        "mealName": meal_scan.meal_name,
        "mealDescription": meal_scan.meal_description,
        "total_calories": round_display(meal_scan.totals.calories),
        "total_carbs": round_display(meal_scan.totals.carbohydrates),
        "total_sugars": None if meal_scan.totals.sugars is None else round_display(meal_scan.totals.sugars),
        "total_fat": round_display(meal_scan.totals.fat),
        "total_saturated": None
        if meal_scan.totals.saturated_fat is None
        else round_display(meal_scan.totals.saturated_fat),
        "total_protein": round_display(meal_scan.totals.protein),
        "total_gl": round_display(total_gl),
        "ingredients": ingredients,
        "opinions": opinions,
        "risks": meal_scan.potential_health_risks,
        "nutritionistsOpinion": opinions,
        "potentialHealthRisks": meal_scan.potential_health_risks,
        "placeholder_asset": placeholder_asset,
        "video_script_json": video_script_json_for_inline(video_script),
        # HyperFrames composition / GSAP
        "hf_width": w,
        "hf_height": h,
        "hf_composition_duration": f"{comp_dur:.3f}",
        "hf_gsap_duration": comp_dur,
        "hf_composition_id": "logi-ui",
    }


def resolve_project_root(settings: Settings) -> Path:
    template_path = settings.project_root / "tamplate.html"
    if template_path.exists():
        return settings.project_root
    return Path(__file__).resolve().parent.parent
