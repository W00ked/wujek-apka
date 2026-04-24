from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError


class AppConfig(BaseModel):
    output_dir: Path = Path("output")
    artifacts_dir: Path = Path("artifacts")
    latest_link: str = "copy"
    log_level: str = "INFO"


class RenderConfig(BaseModel):
    ui_backend: Literal["playwright", "hyperframes"] = "hyperframes"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    max_duration_sec: float | None = None
    intro_max_sec: int = 7
    ui_target_duration_sec: int = 23
    ui_warmup_sec: float = 3.0
    ui_end_hold_sec: float = 0.0
    record_timeout_buffer_sec: float = 8.0
    pad_to_30s: bool = False
    placeholder_asset: Path = Path("assets/ingredient_placeholder.png")


class LogiConfig(BaseModel):
    base_url: str
    timeout_sec: int = 60
    language: str = "en"


class OpenAIConfig(BaseModel):
    model: str = Field(min_length=1)
    timeout_sec: int = 60
    max_retries: int = 3


class TTSConfig(BaseModel):
    model: str = "gemini-3.1-flash-tts-preview"
    voice_name: str = Field(min_length=1)
    timeout_sec: int = 60
    max_retries: int = 3
    output_format: str = "wav"
    speed: float = 1.0


class SubtitlesConfig(BaseModel):
    enabled: bool = False
    model: str = "small"
    device: Literal["cpu", "cuda", "auto"] = "cpu"
    compute_type: str = "int8"
    language: str | None = "en"
    word_timestamps: bool = True
    max_words_per_line: int = 4
    max_chars_per_line: int = 24
    font_name: str = "Poppins SemiBold"
    font_size: int = 68
    bold: bool = False
    alignment: int = 2
    margin_l: int = 120
    margin_r: int = 120
    margin_v: int = 380
    primary_color: str = "&H00FFFFFF"
    highlight_color: str = "&H0038D9FF"
    outline_color: str = "&H00000000"
    back_color: str = "&H50000000"
    outline: float = 1.5
    shadow: float = 0.0
    border_style: Literal[1, 3] = 3
    pop_in_ms: int = 140
    fade_in_ms: int = 40
    fade_out_ms: int = 60
    fontsdir: Path | None = Path("assets/fonts")


class HeyGenConfig(BaseModel):
    enabled: bool = True
    api_base_url: str = "https://api.heygen.com"
    video_generate_path: str = "/v3/videos"
    status_path: str = "/v3/videos/{video_id}"
    avatar_look_path: str = "/v3/avatars/looks/{look_id}"
    avatar_looks_path: str = "/v3/avatars/looks"
    avatar_id: str = Field(default="")
    voice_id: str = Field(default="")
    # Legacy /v2 only. Ignored by the v3 direct video API.
    avatar_style: Literal["circle", "closeUp", "normal"] = "closeUp"
    preferred_orientation: Literal["portrait", "landscape", "square"] = "portrait"
    auto_select_orientation_match: bool = True
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    resolution: Literal["720p", "1080p", "4k"] = "1080p"
    voice_speed: float = 1.0
    timeout_sec: int = 60
    poll_interval_sec: int = 3
    job_timeout_sec: int = 300
    # If intro job fails (avatar/voice/API), continue with UI-only video instead of aborting.
    skip_intro_on_failure: bool = True


class FFmpegConfig(BaseModel):
    binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"


class PlaywrightConfig(BaseModel):
    browser: str = "chromium"
    font_wait_timeout_sec: int = 30


class HyperFramesConfig(BaseModel):
    """Local HyperFrames composition project (see hyperframes init)."""

    project_template_dir: Path = Path("hyperframes_composition")
    npx_command: str = "npx"
    # 0.4.17+ resolves FFmpeg on Windows via `where`; older npx cache used `which` and always failed.
    cli_package: str = "hyperframes@0.4.17"
    render_timeout_sec: float = 3600.0
    quality: Literal["draft", "standard", "high"] = "standard"
    quiet: bool = True
    extra_args: list[str] = Field(default_factory=list)
    node_options: str | None = None


class SecretsConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    logi_api_key: str = Field(alias="LOGI_API_KEY")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    google_api_key: str = Field(alias="GOOGLE_API_KEY")
    heygen_api_key: str | None = Field(default=None, alias="HEYGEN_API_KEY")


class Settings(BaseModel):
    app: AppConfig
    render: RenderConfig
    logi: LogiConfig
    openai: OpenAIConfig
    tts: TTSConfig
    subtitles: SubtitlesConfig
    heygen: HeyGenConfig
    ffmpeg: FFmpegConfig
    playwright: PlaywrightConfig
    hyperframes: HyperFramesConfig
    secrets: SecretsConfig
    project_root: Path


def load_settings(config_path: str | Path = "config.yaml") -> Settings:
    path = Path(config_path).resolve()
    if not path.exists():
        raise ConfigurationError(f"config file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    project_root = path.parent
    env_path = project_root / ".env"
    try:
        if env_path.is_file():
            # Project .env wins over stale keys in Windows user/system environment.
            load_dotenv(env_path, override=True)
            secrets = SecretsConfig(_env_file=env_path)
        else:
            secrets = SecretsConfig()
    except Exception as exc:  # noqa: BLE001
        raise ConfigurationError(f"missing required environment variables: {exc}") from exc

    try:
        return Settings(
            project_root=project_root,
            secrets=secrets,
            app=AppConfig.model_validate(raw.get("app", {})),
            render=RenderConfig.model_validate(raw.get("render", {})),
            logi=LogiConfig.model_validate(raw.get("logi", {})),
            openai=OpenAIConfig.model_validate(raw.get("openai", {})),
            tts=TTSConfig.model_validate(raw.get("tts", {})),
            subtitles=SubtitlesConfig.model_validate(raw.get("subtitles", {})),
            heygen=HeyGenConfig.model_validate(raw.get("heygen", {})),
            ffmpeg=FFmpegConfig.model_validate(raw.get("ffmpeg", {})),
            playwright=PlaywrightConfig.model_validate(raw.get("playwright", {})),
            hyperframes=HyperFramesConfig.model_validate(raw.get("hyperframes", {})),
        )
    except Exception as exc:  # noqa: BLE001
        raise ConfigurationError(f"invalid config: {exc}") from exc
