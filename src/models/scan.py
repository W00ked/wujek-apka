from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, computed_field, model_validator

from ..logging_utils import get_logger


def _as_str_list(value: Any) -> list[str]:
    """LOGI may return a string, null, or mixed list for opinion / risk fields."""
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out
    return []


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _optional_str(value: Any, *, max_len: int = 8000) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    stripped = value.strip()
    if not stripped:
        return None
    return stripped[:max_len]


class NutritionValues(BaseModel):
    model_config = ConfigDict(extra="ignore")

    calories: float | None = None
    protein: float | None = None
    fat: float | None = None
    carbohydrates: float | None = None
    saturated_fat: float | None = None
    fiber: float | None = None
    glycemic_index: float | None = None
    glycemic_load: float | None = None
    sugars: float | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_logi_numbers(cls, data: Any) -> Any:
        if data is None:
            return {}
        if not isinstance(data, dict):
            return {}
        payload = dict(data)
        if payload.get("sugars") is None and payload.get("sugars_total") is not None:
            payload["sugars"] = payload.get("sugars_total")
        for key in (
            "calories",
            "protein",
            "fat",
            "carbohydrates",
            "saturated_fat",
            "fiber",
            "glycemic_index",
            "glycemic_load",
            "sugars",
        ):
            if key not in payload:
                continue
            coerced = _safe_float(payload[key])
            payload[key] = coerced
        return payload


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str | None = None
    weight: float | None = None
    category: str | None = None
    nutritional_reference: NutritionValues = Field(default_factory=NutritionValues)
    nutritional_actual: NutritionValues = Field(default_factory=NutritionValues)
    match_confidence: float | None = None
    thumbnail_url: str | None = None

    @computed_field
    @property
    def glycemic_index_label(self) -> str | None:
        value = self.nutritional_reference.glycemic_index
        return None if value is None else f"{value:.0f}"


def _nutrition_block(raw: Any) -> NutritionValues:
    if not isinstance(raw, dict):
        return NutritionValues()
    try:
        return NutritionValues.model_validate(raw)
    except ValidationError:
        return NutritionValues()


def _ingredient_fallback(row: dict[str, Any]) -> Ingredient:
    """Minimal Ingredient when strict validation fails (odd types / partial LOGI payloads)."""
    name = _optional_str(row.get("name"), max_len=500) or "Unknown ingredient"
    return Ingredient(
        name=name,
        description=_optional_str(row.get("description")),
        weight=_safe_float(row.get("weight")),
        category=_optional_str(row.get("category"), max_len=200),
        nutritional_reference=_nutrition_block(row.get("nutritional_reference")),
        nutritional_actual=_nutrition_block(row.get("nutritional_actual")),
        match_confidence=_safe_float(row.get("match_confidence")),
        thumbnail_url=_optional_str(row.get("thumbnail_url"), max_len=2000),
    )


def _parse_ingredient_row(item: Any, index: int) -> Ingredient | None:
    logger = get_logger(__name__, step="logi")
    if not isinstance(item, dict):
        logger.warning("skip ingredients[%s]: not an object", index)
        return None
    try:
        return Ingredient.model_validate(item)
    except ValidationError as exc:
        logger.warning("ingredients[%s] strict parse failed, using fallback (%s)", index, exc)
        try:
            return _ingredient_fallback(item)
        except ValidationError as exc2:
            logger.warning("ingredients[%s] skipped: %s", index, exc2)
            return None


class NutritionTotals(BaseModel):
    calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbohydrates: float = 0.0
    saturated_fat: float | None = None
    sugars: float | None = None

    @classmethod
    def from_ingredients(cls, ingredients: list[Ingredient]) -> "NutritionTotals":
        saturated_total = 0.0
        saturated_present = False
        sugars_total = 0.0
        sugars_present = False

        totals = cls(
            calories=sum((item.nutritional_actual.calories or 0.0) for item in ingredients),
            protein=sum((item.nutritional_actual.protein or 0.0) for item in ingredients),
            fat=sum((item.nutritional_actual.fat or 0.0) for item in ingredients),
            carbohydrates=sum((item.nutritional_actual.carbohydrates or 0.0) for item in ingredients),
        )

        for ingredient in ingredients:
            if ingredient.nutritional_actual.saturated_fat is not None:
                saturated_total += ingredient.nutritional_actual.saturated_fat
                saturated_present = True
            if ingredient.nutritional_actual.sugars is not None:
                sugars_total += ingredient.nutritional_actual.sugars
                sugars_present = True

        totals.saturated_fat = saturated_total if saturated_present else None
        totals.sugars = sugars_total if sugars_present else None
        return totals


class MealScan(BaseModel):
    meal_name: str
    meal_description: str | None = None
    ingredients: list[Ingredient]
    potential_health_risks: list[str] = Field(default_factory=list)
    nutritionists_opinion: list[str] = Field(default_factory=list)
    totals: NutritionTotals

    @computed_field
    @property
    def primary_opinion(self) -> str | None:
        return self.nutritionists_opinion[0] if self.nutritionists_opinion else None

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "MealScan":
        raw_ingredients = data.get("ingredients", [])
        if not isinstance(raw_ingredients, list):
            raw_ingredients = []

        ingredients: list[Ingredient] = []
        for idx, row in enumerate(raw_ingredients):
            parsed = _parse_ingredient_row(row, idx)
            if parsed is not None:
                ingredients.append(parsed)

        meal_name = _optional_str(data.get("mealName"), max_len=500) or "Meal"
        meal_description = _optional_str(data.get("mealDescription"))

        return cls(
            meal_name=meal_name,
            meal_description=meal_description,
            ingredients=ingredients,
            potential_health_risks=_as_str_list(data.get("potentialHealthRisks")),
            nutritionists_opinion=_as_str_list(data.get("nutritionistsOpinion")),
            totals=NutritionTotals.from_ingredients(ingredients),
        )


class ScanResponse(BaseModel):
    success: bool
    scanId: str
    duration: int | None = None
    processing_mode: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    def to_meal_scan(self) -> MealScan:
        return MealScan.from_api_data(self.data)
