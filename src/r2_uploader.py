from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .errors import PipelineError
from .logging_utils import get_logger


@dataclass
class R2UploadResult:
    object_key: str
    public_url: str


def slugify_for_object_key(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "meal"


def build_r2_object_key(*, dish: str, cache_key: str, extension: str, key_prefix: str) -> str:
    prefix = key_prefix.strip("/")
    slug = slugify_for_object_key(dish)
    ext = extension.lstrip(".").lower()
    return f"{prefix}/{slug}-{cache_key}.{ext}" if prefix else f"{slug}-{cache_key}.{ext}"


def build_public_url(base_url: str, object_key: str) -> str:
    return f"{base_url.rstrip('/')}/{object_key.lstrip('/')}"


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".webp":
        return "image/webp"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "image/png"


def upload_to_r2(
    local_path: Path,
    *,
    dish: str,
    cache_key: str,
    settings: Settings,
) -> R2UploadResult:
    logger = get_logger(__name__, step="r2")
    secrets = settings.secrets
    missing = [
        name
        for name, value in {
            "R2_ACCOUNT_ID": secrets.r2_account_id,
            "R2_ACCESS_KEY_ID": secrets.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": secrets.r2_secret_access_key,
            "R2_BUCKET": secrets.r2_bucket,
            "R2_PUBLIC_BASE_URL": secrets.r2_public_base_url,
        }.items()
        if not value
    ]
    if missing:
        raise PipelineError(
            f"missing R2 configuration for generated image upload: {', '.join(missing)}",
            code=26,
            step="r2",
        )

    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PipelineError(
            "boto3 is required for Cloudflare R2 upload; install project dependencies again",
            code=26,
            step="r2",
        ) from exc

    object_key = build_r2_object_key(
        dish=dish,
        cache_key=cache_key,
        extension=local_path.suffix,
        key_prefix=settings.r2.key_prefix,
    )
    endpoint_url = f"https://{secrets.r2_account_id}.r2.cloudflarestorage.com"
    public_url = build_public_url(secrets.r2_public_base_url or "", object_key)

    logger.info("uploading generated food image to R2: %s", object_key)
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=secrets.r2_access_key_id,
        aws_secret_access_key=secrets.r2_secret_access_key,
        region_name="auto",
    )
    try:
        client.upload_file(
            str(local_path),
            secrets.r2_bucket,
            object_key,
            ExtraArgs={
                "ContentType": _content_type(local_path),
                "CacheControl": settings.r2.cache_control,
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise PipelineError(f"R2 upload failed: {exc}", code=26, step="r2") from exc
    return R2UploadResult(object_key=object_key, public_url=public_url)
