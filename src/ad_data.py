from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import MealScan, ScriptPlan
from .utils import round_display


def _sum_actual(ingredients: list[Any], field: str) -> float | None:
    total = 0.0
    found = False
    for item in ingredients:
        value = getattr(item.nutritional_actual, field)
        if value is not None:
            total += float(value)
            found = True
    return total if found else None


def _gl_band(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 20:
        return "high"
    if value >= 11:
        return "medium"
    return "low"


def _ingredient_payload(ingredient: Any) -> dict[str, Any]:
    actual = ingredient.nutritional_actual
    reference = ingredient.nutritional_reference
    gl = actual.glycemic_load
    gi = reference.glycemic_index
    return {
        "name": ingredient.name,
        "description": ingredient.description,
        "category": ingredient.category,
        "weight": None if ingredient.weight is None else round_display(float(ingredient.weight)),
        "calories": round_display(actual.calories),
        "carbs": round_display(actual.carbohydrates),
        "fat": round_display(actual.fat),
        "protein": round_display(actual.protein),
        "glycemic_index": None if gi is None else round_display(float(gi)),
        "glycemic_load": None if gl is None else round_display(float(gl)),
        "thumbnail_url": ingredient.thumbnail_url,
    }


def build_logi_ad_data(
    *,
    meal_scan: MealScan,
    script_plan: ScriptPlan,
    dish: str | None,
    food_image_asset: str | None,
    food_image_url: str | None,
    language: str,
) -> dict[str, Any]:
    ingredients = list(meal_scan.ingredients)
    total_gl = _sum_actual(ingredients, "glycemic_load")
    nested_food_image_asset = f"../{food_image_asset}" if food_image_asset else None
    primary_risks = meal_scan.potential_health_risks[:3]
    if not primary_risks:
        primary_risks = [
            "Watch glycemic load",
            "Check portion size",
            "Balance the macros",
        ]

    script_by_section = {segment.section_id: segment.script for segment in script_plan.segments}
    return {
        "language": language,
        "dish": dish or meal_scan.meal_name,
        "food_image": {
            "asset": food_image_asset,
            "nested_asset": nested_food_image_asset,
            "public_url": food_image_url,
        },
        "meal": {
            "name": meal_scan.meal_name,
            "description": meal_scan.meal_description,
            "primary_opinion": meal_scan.primary_opinion,
        },
        "metrics": {
            "glycemic_load": {
                "value": round_display(total_gl),
                "raw": total_gl,
                "band": _gl_band(total_gl),
            },
            "calories": round_display(meal_scan.totals.calories),
            "carbs": round_display(meal_scan.totals.carbohydrates),
            "fat": round_display(meal_scan.totals.fat),
            "protein": round_display(meal_scan.totals.protein),
            "sugars": None
            if meal_scan.totals.sugars is None
            else round_display(meal_scan.totals.sugars),
            "saturated_fat": None
            if meal_scan.totals.saturated_fat is None
            else round_display(meal_scan.totals.saturated_fat),
        },
        "ingredients": [_ingredient_payload(item) for item in ingredients[:8]],
        "risks": primary_risks,
        "insights": meal_scan.nutritionists_opinion[:4],
        "script": {
            "hook_line": script_plan.hook_line,
            "sections": script_by_section,
        },
        "cta": {
            "headline": "Snap. Scan. Understand.",
            "subtitle": (
                "Turn one food photo into calories, glycemic load, ingredients, "
                "and plain-English meal insights."
            ),
            "button": "Try LOGI",
        },
    }


def relative_asset_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
