from __future__ import annotations

import base64
import hashlib
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import ImageGenerationConfig, Settings
from .errors import PipelineError, ValidationError
from .logging_utils import get_logger
from .utils import ensure_directory, read_json, write_json


@dataclass
class CostEstimate:
    text_input_tokens: int
    image_input_tokens: int
    image_output_tokens: int
    variants: int
    estimated_cost_usd: float

    def model_dump(self) -> dict[str, Any]:
        return {
            "text_input_tokens": self.text_input_tokens,
            "image_input_tokens": self.image_input_tokens,
            "image_output_tokens": self.image_output_tokens,
            "variants": self.variants,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


@dataclass
class FoodImageArtifact:
    dish: str
    prompt: str
    cache_key: str
    image_path: Path
    metadata_path: Path
    cost_estimate: CostEstimate
    cache_metadata_path: Path | None = None
    public_url: str | None = None
    reused_cache: bool = False


def build_food_image_prompt(dish: str, *, language: str = "en") -> str:
    normalized = " ".join(dish.split())
    if not normalized:
        raise ValidationError("dish cannot be empty", step="image")

    language_hint = "English" if language == "en" else language
    return (
        f"Create a premium, photorealistic vertical food photograph of: {normalized}.\n"
        "The image must look like a real meal photo prepared for a high-performing "
        "TikTok ad for a nutrition app.\n"
        "Use natural window light, appetizing texture, realistic colors, visible "
        "ingredients, and professional food styling.\n"
        "Frame it as a modern smartphone food photo: close enough to feel delicious, "
        "wide enough for app UI animation.\n"
        "Use a clean plate or bowl, subtle table surface, shallow depth of field, "
        "crisp detail, and no messy distractions.\n"
        "Avoid text, labels, logos, watermarks, hands, people, cutlery blocking the "
        "food, packaging, brand names, or UI.\n"
        "The dish should be recognizable from the user's short description, not a "
        "generic stock-food image.\n"
        "Composition: portrait crop, hero food centered slightly above the middle, "
        "rich highlights, premium commercial finish.\n"
        f"Prompt language/context: {language_hint}. Output only the image."
    )


def estimate_text_tokens(text: str) -> int:
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def estimate_image_output_tokens(size: str, quality: str) -> int:
    if quality == "auto":
        quality_key = "high"
    elif quality == "standard":
        quality_key = "medium"
    elif quality == "hd":
        quality_key = "high"
    else:
        quality_key = quality
    size_key = "1024x1536" if size == "auto" else size
    # DALL·E 3 sizes: map to nearest GPT Image bucket for rough cost hints.
    if size_key == "1024x1792":
        size_key = "1024x1536"
    elif size_key == "1792x1024":
        size_key = "1536x1024"
    token_table: dict[str, dict[str, int]] = {
        "low": {"1024x1024": 272, "1024x1536": 408, "1536x1024": 400},
        "medium": {"1024x1024": 1056, "1024x1536": 1584, "1536x1024": 1568},
        "high": {"1024x1024": 4160, "1024x1536": 6240, "1536x1024": 6208},
    }
    return token_table.get(quality_key, token_table["high"]).get(size_key, 6240)


def estimate_generation_cost(
    prompt: str,
    config: ImageGenerationConfig,
    *,
    variants: int,
    image_input_tokens: int = 0,
    cached_text_input: bool = False,
    cached_image_input: bool = False,
) -> CostEstimate:
    text_tokens = estimate_text_tokens(prompt)
    output_tokens = estimate_image_output_tokens(config.size, config.quality) * variants
    pricing = config.pricing
    text_rate = pricing.text_cached_input_per_1m if cached_text_input else pricing.text_input_per_1m
    image_input_rate = (
        pricing.image_cached_input_per_1m if cached_image_input else pricing.image_input_per_1m
    )
    cost = (
        text_tokens * text_rate
        + image_input_tokens * image_input_rate
        + output_tokens * pricing.image_output_per_1m
    ) / 1_000_000
    return CostEstimate(
        text_input_tokens=text_tokens,
        image_input_tokens=image_input_tokens,
        image_output_tokens=output_tokens,
        variants=variants,
        estimated_cost_usd=cost,
    )


def image_cache_key(dish: str, prompt: str, config: ImageGenerationConfig, *, variants: int) -> str:
    payload = "|".join(
        [
            "dish",
            " ".join(dish.lower().split()),
            config.model,
            config.prompt_version,
            config.size,
            config.quality,
            config.output_format,
            str(config.output_compression),
            str(variants),
            prompt,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _response_to_json(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if hasattr(response, "dict"):
        return response.dict()
    return {"response_type": type(response).__name__, "repr": repr(response)}


def _first_image_b64(response: Any) -> str:
    data = getattr(response, "data", None)
    if not data:
        raise PipelineError("OpenAI image generation returned no images", code=25, step="image")
    first = data[0]
    b64_json = getattr(first, "b64_json", None)
    if not b64_json and isinstance(first, dict):
        b64_json = first.get("b64_json")
    if not b64_json:
        raise PipelineError(
            "OpenAI image generation did not return base64 image data",
            code=25,
            step="image",
        )
    return b64_json


def _copy_cache_to_run(
    cache_image: Path,
    cache_meta: Path,
    run_dir: Path,
    output_format: str,
) -> FoodImageArtifact:
    metadata = read_json(cache_meta)
    prompt = metadata["prompt"]
    dish = metadata["dish"]
    cache_key = metadata["cache_key"]
    cost = CostEstimate(**metadata["cost_estimate"])
    run_image = run_dir / f"generated_food_image.{output_format}"
    shutil.copy2(cache_image, run_image)
    run_meta = run_dir / "image_generation.json"
    write_json(run_meta, {**metadata, "reused_cache": True})
    (run_dir / "image_prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(run_dir / "cost_estimate.json", cost.model_dump())
    return FoodImageArtifact(
        dish=dish,
        prompt=prompt,
        cache_key=cache_key,
        image_path=run_image,
        metadata_path=run_meta,
        cost_estimate=cost,
        cache_metadata_path=cache_meta,
        public_url=metadata.get("public_url"),
        reused_cache=True,
    )


def record_food_image_public_url(artifact: FoodImageArtifact, public_url: str) -> None:
    metadata = read_json(artifact.metadata_path)
    metadata["public_url"] = public_url
    write_json(artifact.metadata_path, metadata)
    cache_meta = artifact.cache_metadata_path
    if cache_meta and cache_meta.exists():
        cache_metadata = read_json(cache_meta)
        cache_metadata["public_url"] = public_url
        write_json(cache_meta, cache_metadata)
    artifact.public_url = public_url


def prepare_food_image(
    dish: str,
    settings: Settings,
    run_dir: Path,
    *,
    regenerate_image: bool = False,
    image_variants: int | None = None,
    max_image_cost_usd: float | None = None,
    allow_high_cost: bool | None = None,
    language: str = "en",
) -> FoodImageArtifact:
    logger = get_logger(__name__, step="image")
    config = settings.image_generation
    variants = image_variants or config.variants
    if variants < 1:
        raise ValidationError("image variants must be at least 1", step="image")

    prompt = build_food_image_prompt(dish, language=language)
    cache_key = image_cache_key(dish, prompt, config, variants=variants)
    cost = estimate_generation_cost(prompt, config, variants=variants)
    write_json(run_dir / "cost_estimate.json", cost.model_dump())
    (run_dir / "image_prompt.txt").write_text(prompt, encoding="utf-8")

    limit = max_image_cost_usd if max_image_cost_usd is not None else config.max_cost_usd
    allow = config.allow_high_cost if allow_high_cost is None else allow_high_cost
    if cost.estimated_cost_usd > limit and not allow:
        raise PipelineError(
            f"estimated image generation cost ${cost.estimated_cost_usd:.4f} "
            f"exceeds limit ${limit:.4f}",
            code=25,
            step="image",
        )

    cache_root = ensure_directory(settings.project_root / config.cache_dir / cache_key)
    cache_image = cache_root / f"generated_food_image.{config.output_format}"
    cache_meta = cache_root / "metadata.json"
    if cache_image.exists() and cache_meta.exists() and not regenerate_image:
        logger.info("reusing cached generated food image: %s", cache_key)
        return _copy_cache_to_run(cache_image, cache_meta, run_dir, config.output_format)

    logger.info("requesting OpenAI image generation model=%s size=%s", config.model, config.size)
    client = OpenAI(api_key=settings.secrets.openai_api_key, timeout=settings.openai.timeout_sec)

    @retry(
        retry=retry_if_exception_type((APIError, APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(settings.openai.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    def _generate() -> Any:
        model_lower = str(config.model).lower()
        kwargs: dict[str, Any] = {
            "model": config.model,
            "prompt": prompt,
            "size": config.size,
        }
        if model_lower.startswith("dall-e-3"):
            kwargs["n"] = 1
            q = str(config.quality).lower()
            if q in ("standard", "hd"):
                kwargs["quality"] = q
            elif q in ("high", "medium", "auto"):
                kwargs["quality"] = "hd"
            else:
                kwargs["quality"] = "standard"
            kwargs["response_format"] = "b64_json"
            return client.images.generate(**kwargs)

        if model_lower.startswith("dall-e"):
            kwargs["n"] = variants
            kwargs["response_format"] = "b64_json"
            return client.images.generate(**kwargs)

        kwargs["n"] = variants
        kwargs["quality"] = config.quality
        kwargs["output_format"] = config.output_format
        if config.output_format in {"jpeg", "webp"} and config.output_compression is not None:
            kwargs["output_compression"] = config.output_compression
        return client.images.generate(**kwargs)

    try:
        response = _generate()
    except (APIError, APITimeoutError, RateLimitError) as exc:
        raise PipelineError(
            f"OpenAI image generation failed: {exc}",
            code=25,
            step="image",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise PipelineError(
            f"OpenAI image generation failed: {exc}",
            code=25,
            step="image",
        ) from exc

    image_bytes = base64.b64decode(_first_image_b64(response))
    run_image = run_dir / f"generated_food_image.{config.output_format}"
    run_image.write_bytes(image_bytes)
    shutil.copy2(run_image, cache_image)

    metadata = {
        "dish": dish,
        "prompt": prompt,
        "prompt_version": config.prompt_version,
        "cache_key": cache_key,
        "model": config.model,
        "size": config.size,
        "quality": config.quality,
        "output_format": config.output_format,
        "output_compression": config.output_compression,
        "variants": variants,
        "cost_estimate": cost.model_dump(),
        "response": _response_to_json(response),
        "reused_cache": False,
    }
    run_meta = run_dir / "image_generation.json"
    write_json(run_meta, metadata)
    write_json(cache_meta, metadata)

    return FoodImageArtifact(
        dish=dish,
        prompt=prompt,
        cache_key=cache_key,
        image_path=run_image,
        metadata_path=run_meta,
        cost_estimate=cost,
        cache_metadata_path=cache_meta,
        reused_cache=False,
    )
