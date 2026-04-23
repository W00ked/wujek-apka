from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx

from .config import Settings
from .errors import ConfigurationError, PipelineError
from .logging_utils import get_logger


def _extract_video_id(payload: dict) -> str | None:
    for key in ("video_id", "videoId"):
        if key in payload:
            return payload[key]
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("video_id", "videoId"):
            if key in data:
                return data[key]
    return None


def _extract_error_message(payload: dict) -> str | None:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return None


def _extract_status(payload: dict) -> tuple[str | None, str | None]:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return None, None
    status = data.get("status")
    video_url = data.get("video_url") or data.get("videoUrl") or data.get("url")
    return status, video_url


def _extract_failure_detail(payload: dict) -> str:
    """Best-effort message from HeyGen error payloads (shape varies by endpoint/version)."""
    data = payload.get("data", payload)
    direct_error = _extract_error_message(payload)
    if direct_error:
        return direct_error[:2000]
    if isinstance(data, dict):
        for key in ("failure_message", "message", "msg", "reason", "detail", "failure_code", "error"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()[:2000]
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=True)[:2000]
    return json.dumps(payload, ensure_ascii=True)[:2000]


class HeyGenClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__, step="heygen")

    def _validate_config(self) -> None:
        if not self.settings.secrets.heygen_api_key:
            raise ConfigurationError("HEYGEN_API_KEY is required unless --skip-intro is used")
        if not self.settings.heygen.avatar_id:
            raise ConfigurationError("heygen.avatar_id is required unless --skip-intro is used")
        if not self.settings.heygen.voice_id:
            raise ConfigurationError("heygen.voice_id is required unless --skip-intro is used")

    def generate_intro(self, script_text: str, output_path: Path) -> Path:
        self._validate_config()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=self.settings.heygen.timeout_sec) as client:
            avatar_id = self._resolve_avatar_id(client)
            video_id = self._create_job(client, script_text, avatar_id)
            video_url = self._poll_for_video_url(client, video_id)
            self._download_video(client, video_url, output_path)
        return output_path

    def _build_url(self, template: str, **kwargs: str) -> str:
        return urljoin(self.settings.heygen.api_base_url, template.format(**kwargs))

    def _resolve_avatar_id(self, client: httpx.Client) -> str:
        configured_avatar_id = self.settings.heygen.avatar_id
        look = self._get_avatar_look(client, configured_avatar_id)
        if look is None:
            self.logger.warning(
                "could not resolve avatar look details for %s; using configured look as-is",
                configured_avatar_id,
            )
            return configured_avatar_id

        preferred = look.get("preferred_orientation")
        self.logger.info(
            "configured HeyGen look %s orientation=%s native=%sx%s",
            configured_avatar_id,
            preferred,
            look.get("image_width"),
            look.get("image_height"),
        )
        desired = self.settings.heygen.preferred_orientation
        if not self.settings.heygen.auto_select_orientation_match or preferred == desired:
            return configured_avatar_id

        group_id = look.get("group_id")
        if not isinstance(group_id, str) or not group_id:
            self.logger.warning("avatar look %s has no group_id; cannot auto-select %s look", configured_avatar_id, desired)
            return configured_avatar_id

        replacement = self._find_matching_look(client, group_id, desired)
        if replacement is None:
            self.logger.warning(
                "no %s look found for avatar group %s; keeping configured look %s",
                desired,
                group_id,
                configured_avatar_id,
            )
            return configured_avatar_id

        replacement_id = replacement.get("id")
        if not isinstance(replacement_id, str) or not replacement_id:
            return configured_avatar_id
        self.logger.info(
            "switching HeyGen look from %s (%s) to %s (%s) for mobile framing",
            configured_avatar_id,
            preferred,
            replacement_id,
            replacement.get("preferred_orientation"),
        )
        return replacement_id

    def _get_avatar_look(self, client: httpx.Client, look_id: str) -> dict | None:
        url = self._build_url(self.settings.heygen.avatar_look_path, look_id=look_id)
        headers = {"x-api-key": self.settings.secrets.heygen_api_key}
        response = client.get(url, headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            detail = _extract_failure_detail(response.json())
            raise PipelineError(
                f"HeyGen avatar look request failed: {detail}",
                code=40,
                step="heygen",
            )
        body = response.json()
        data = body.get("data")
        return data if isinstance(data, dict) else None

    def _find_matching_look(self, client: httpx.Client, group_id: str, orientation: str) -> dict | None:
        headers = {"x-api-key": self.settings.secrets.heygen_api_key}
        token: str | None = None
        while True:
            params: dict[str, str | int] = {"group_id": group_id, "limit": 50}
            if token:
                params["token"] = token
            response = client.get(self._build_url(self.settings.heygen.avatar_looks_path), headers=headers, params=params)
            if response.status_code >= 400:
                detail = _extract_failure_detail(response.json())
                raise PipelineError(
                    f"HeyGen avatar looks request failed: {detail}",
                    code=40,
                    step="heygen",
                )
            body = response.json()
            for item in body.get("data", []):
                if not isinstance(item, dict):
                    continue
                if item.get("status") not in (None, "completed"):
                    continue
                if item.get("preferred_orientation") == orientation:
                    return item
            if not body.get("has_more"):
                return None
            token = body.get("next_token")
            if not isinstance(token, str) or not token:
                return None

    def _create_job(self, client: httpx.Client, script_text: str, avatar_id: str) -> str:
        payload = {
            "type": "avatar",
            "avatar_id": avatar_id,
            "voice_id": self.settings.heygen.voice_id,
            "script": script_text,
            "aspect_ratio": self.settings.heygen.aspect_ratio,
            "resolution": self.settings.heygen.resolution,
            "voice_settings": {
                "speed": self.settings.heygen.voice_speed,
            },
        }
        url = self._build_url(self.settings.heygen.video_generate_path)
        headers = {"x-api-key": self.settings.secrets.heygen_api_key, "Content-Type": "application/json"}

        self.logger.info("creating HeyGen intro job")
        response = client.post(url, headers=headers, json=payload)
        if response.status_code >= 500:
            raise PipelineError(
                f"HeyGen create failed with status {response.status_code}",
                code=40,
                step="heygen",
            )
        if response.status_code >= 400:
            detail = _extract_failure_detail(response.json())
            raise PipelineError(
                f"HeyGen rejected intro request with status {response.status_code}: {detail}",
                code=40,
                step="heygen",
            )

        body = response.json()
        video_id = _extract_video_id(body)
        if not video_id:
            raise PipelineError("HeyGen response did not include video_id", code=40, step="heygen")
        return video_id

    def _poll_for_video_url(self, client: httpx.Client, video_id: str) -> str:
        headers = {"x-api-key": self.settings.secrets.heygen_api_key}
        url = self._build_url(self.settings.heygen.status_path, video_id=video_id)
        deadline = time.monotonic() + self.settings.heygen.job_timeout_sec

        while time.monotonic() < deadline:
            response = client.get(url, headers=headers)
            if response.status_code >= 400:
                detail = _extract_failure_detail(response.json())
                raise PipelineError(
                    f"HeyGen status request failed with status {response.status_code}: {detail}",
                    code=40,
                    step="heygen",
                )
            body = response.json()
            status, video_url = _extract_status(body)
            st = (status or "").lower()
            if st == "completed" and video_url:
                return video_url
            if st in ("failed", "error"):
                detail = _extract_failure_detail(body)
                self.logger.error("HeyGen job failed (video_id=%s): %s", video_id, detail)
                raise PipelineError(
                    f"HeyGen intro generation failed: {detail}",
                    code=40,
                    step="heygen",
                )
            time.sleep(self.settings.heygen.poll_interval_sec)

        raise PipelineError("HeyGen intro generation timed out", code=40, step="heygen")

    def _download_video(self, client: httpx.Client, video_url: str, output_path: Path) -> None:
        self.logger.info("downloading HeyGen intro")
        response = client.get(video_url)
        if response.status_code >= 400:
            raise PipelineError(
                f"failed to download HeyGen intro: status {response.status_code}",
                code=40,
                step="heygen",
            )
        output_path.write_bytes(response.content)
