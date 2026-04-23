from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from jinja2 import Template

from src.models.scan import MealScan


def sum_field(ingredients: list[dict], field: str) -> float:
    total = 0.0
    for ingredient in ingredients:
        actual = ingredient.get("nutritional_actual", {})
        value = actual.get(field)
        if value is not None:
            total += float(value)
    return total


def format_number(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}".rstrip("0").rstrip(".")


def main() -> None:
    load_dotenv()

    api_key = os.getenv("LOGI_API_KEY")
    if not api_key:
        raise RuntimeError("LOGI_API_KEY is missing in .env")

    response = requests.post(
        "https://apilogi.com/demo/scan",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "prompt": "grilled chicken salad with olive oil",
            "lang": "en",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(f"LOGI returned unsuccessful response: {json.dumps(payload, indent=2)}")

    data = payload["data"]
    meal = MealScan.from_api_data(data)
    print(f"parsed ingredients: {len(meal.ingredients)} (same rules as logi-video)")
    ingredients = data.get("ingredients", [])

    total_gl = sum_field(ingredients, "glycemic_load")
    total_calories = sum_field(ingredients, "calories")
    total_carbs = sum_field(ingredients, "carbohydrates")
    total_sugars = sum_field(ingredients, "sugars_total")
    total_fat = sum_field(ingredients, "fat")
    total_saturated = sum_field(ingredients, "saturated_fat")
    total_protein = sum_field(ingredients, "protein")

    template_path = Path("tamplate.html")
    output_path = Path("preview.html")

    template = Template(template_path.read_text(encoding="utf-8"))
    rendered_html = template.render(
        mealName=data.get("mealName", ""),
        mealDescription=data.get("mealDescription", ""),
        ingredients=ingredients,
        nutritionistsOpinion=data.get("nutritionistsOpinion", []),
        potentialHealthRisks=data.get("potentialHealthRisks", []),
        total_gl=format_number(total_gl),
        total_calories=format_number(total_calories),
        total_carbs=format_number(total_carbs),
        total_sugars=format_number(total_sugars),
        total_fat=format_number(total_fat),
        total_saturated=format_number(total_saturated),
        total_protein=format_number(total_protein),
    )
    output_path.write_text(rendered_html, encoding="utf-8")

    print(f"status: {response.status_code}")
    print(f"scanId: {payload.get('scanId')}")
    print(f"saved: {output_path.resolve()}")
    print("(raw JSON is large; use scan.json from artifacts or a JSON file viewer if needed)")


if __name__ == "__main__":
    main()