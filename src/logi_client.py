from __future__ import annotations

from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from .config import Settings
from .errors import PipelineError, ValidationError
from .logging_utils import get_logger
from .models import MealScan, ScanResponse
from .utils import read_json, write_json


class LogiRetryableError(Exception):
    """Transient LOGI error that can be retried."""


def build_scan_payload(
    *,
    prompt: str | None,
    image_url: str | None,
    language: str,
) -> dict[str, str]:
    if bool(prompt) == bool(image_url):
        raise ValidationError("provide exactly one of --prompt or --image-url", step="logi")

    payload = {"lang": language}
    if prompt:
        payload["prompt"] = prompt
    if image_url:
        payload["image_url"] = image_url
    return payload


def load_cached_scan(path: Path) -> tuple[ScanResponse, MealScan]:
    raw = read_json(path)
    response = ScanResponse.model_validate(raw)
    if not response.success:
        raise PipelineError("cached scan indicates failure", code=10, step="logi", path=path)
    meal_scan = response.to_meal_scan()
    if not meal_scan.ingredients:
        raise PipelineError("cached scan has no ingredients", code=10, step="logi", path=path)
    return response, meal_scan


def create_logi_scanner(settings: Settings):
    logger = get_logger(__name__, step="logi")

    @retry(
        retry=retry_if_exception_type(LogiRetryableError),
        stop=stop_after_attempt(2),
        wait=wait_random_exponential(multiplier=1, min=2, max=5),
        reraise=True,
    )
    def _scan(payload: dict[str, str], output_path: Path) -> tuple[ScanResponse, MealScan]:
        logger.info("requesting LOGI scan")
        try:
            with httpx.Client(timeout=settings.logi.timeout_sec) as client:
                response = client.post(
                    settings.logi.base_url,
                    headers={
                        "x-api-key": settings.secrets.logi_api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            logger.warning("LOGI request timed out; retrying once")
            raise LogiRetryableError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise PipelineError(f"LOGI request failed: {exc}", code=10, step="logi") from exc

        if response.status_code == 429:
            raise PipelineError("LOGI rate limit reached; wait about 15 minutes", code=11, step="logi")
        if response.status_code in {400, 401}:
            raise PipelineError(
                f"LOGI request rejected with status {response.status_code}",
                code=10,
                step="logi",
            )
        if response.status_code == 502:
            logger.warning("LOGI returned 502; retrying once")
            raise LogiRetryableError("LOGI returned 502")
        if response.status_code >= 500:
            raise PipelineError(
                f"LOGI returned server error {response.status_code}",
                code=10,
                step="logi",
            )
        if response.status_code != 200:
            raise PipelineError(
                f"unexpected LOGI status {response.status_code}",
                code=10,
                step="logi",
            )

        try:
            raw = response.json()
        except ValueError as exc:
            raise PipelineError("LOGI returned invalid JSON", code=10, step="logi") from exc

        write_json(output_path, raw)
        parsed = ScanResponse.model_validate(raw)
        if not parsed.success:
            raise PipelineError(
                f"LOGI reported unsuccessful scan: {raw}",
                code=10,
                step="logi",
                path=output_path,
            )

        meal_scan = parsed.to_meal_scan()
        if not meal_scan.ingredients:
            raise PipelineError("LOGI returned no ingredients", code=10, step="logi", path=output_path)

        return parsed, meal_scan

    return _scan
