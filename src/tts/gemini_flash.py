from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..config import Settings
from ..errors import PipelineError
from ..logging_utils import get_logger


def _is_retryable_tts_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(code in message for code in ["429", "500", "503", "timeout"])


class Gemini25FlashTTS:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__, step="tts")
        self.client = genai.Client(api_key=settings.secrets.google_api_key)

    def _write_wav(self, pcm_bytes: bytes, output_path: Path) -> Path:
        # Gemini TTS returns raw PCM, so we wrap it into a standard WAV container.
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(pcm_bytes)
        return output_path

    def _apply_speed(self, input_path: Path, output_path: Path, speed: float) -> Path:
        command = [
            self.settings.ffmpeg.binary,
            "-y",
            "-i",
            str(input_path),
            "-filter:a",
            f"atempo={speed:.3f}",
            str(output_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise PipelineError(
                f"failed to adjust Gemini TTS speed: {result.stderr.strip() or result.returncode}",
                code=30,
                step="tts",
            )
        return output_path

    def _build_tts_prompt(self, transcript: str) -> str:
        return (
            "TTS the following transcript.\n"
            "Read only the TRANSCRIPT section aloud.\n"
            "Follow any square-bracket audio tags such as [excited], [whispers], or [short pause].\n"
            "Do not read section labels, director notes, or these instructions out loud.\n\n"
            "### DIRECTOR'S NOTES\n"
            "- Style: magnetic, emotionally expressive, short-form social video narrator.\n"
            "- Pacing: energetic and fluid, but still clear and easy to understand.\n"
            "- Delivery: punch key words naturally; respect inline audio tags when present.\n\n"
            "### TRANSCRIPT\n"
            f"{transcript.strip()}\n"
        )

    @retry(
        retry=retry_if_exception(_is_retryable_tts_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    def synthesize(self, text: str, output_path: Path) -> Path:
        if not text.strip():
            raise PipelineError("cannot synthesize empty voiceover text", code=30, step="tts")

        self.logger.info("requesting Gemini TTS audio with model %s", self.settings.tts.model)
        try:
            response = self.client.models.generate_content(
                model=self.settings.tts.model,
                contents=self._build_tts_prompt(text),
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.settings.tts.voice_name,
                            )
                        )
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Gemini TTS request failed")
            raise exc

        pcm_bytes = None
        for candidate in response.candidates or []:
            parts = getattr(candidate.content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data and inline_data.data:
                    pcm_bytes = inline_data.data
                    break
            if pcm_bytes:
                break

        if not pcm_bytes:
            raise PipelineError("Gemini TTS returned no audio bytes", code=30, step="tts")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_output_path = output_path
        if abs(float(self.settings.tts.speed) - 1.0) > 0.001:
            base_output_path = output_path.with_name(f"{output_path.stem}_base{output_path.suffix}")
        self._write_wav(pcm_bytes, base_output_path)
        if base_output_path != output_path:
            self.logger.info("adjusting Gemini TTS playback speed to %.2fx", self.settings.tts.speed)
            return self._apply_speed(base_output_path, output_path, float(self.settings.tts.speed))
        return output_path


def create_tts_engine(settings: Settings) -> Gemini25FlashTTS:
    return Gemini25FlashTTS(settings)
