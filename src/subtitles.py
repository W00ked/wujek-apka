from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import PipelineError
from .logging_utils import get_logger

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "their",
    "this",
    "to",
    "up",
    "wait",
    "with",
    "you",
    "your",
}


@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _run_ffmpeg(command: list[str], *, step: str) -> None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise PipelineError(f"missing ffmpeg binary for {step}", code=60, step=step) from exc
    if result.returncode != 0:
        raise PipelineError(
            f"{step} failed: {result.stderr.strip() or result.returncode}",
            code=60,
            step=step,
        )


def extract_audio_wav(video_path: Path, wav_path: Path, settings: Settings) -> Path:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            settings.ffmpeg.binary,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ],
        step="subtitles-extract-audio",
    )
    return wav_path


def transcribe_whisper(wav_path: Path, settings: Settings) -> list[Any]:
    logger = get_logger(__name__, step="subtitles")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise PipelineError(
            "faster-whisper is not installed. Add it to the environment before enabling subtitles.",
            code=70,
            step="subtitles",
        ) from exc

    logger.info(
        "transcribing subtitles with faster-whisper model=%s device=%s compute_type=%s",
        settings.subtitles.model,
        settings.subtitles.device,
        settings.subtitles.compute_type,
    )
    try:
        model = WhisperModel(
            settings.subtitles.model,
            device=settings.subtitles.device,
            compute_type=settings.subtitles.compute_type,
        )
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=settings.subtitles.language,
            word_timestamps=settings.subtitles.word_timestamps,
        )
        logger.info("faster-whisper detected language=%s", getattr(info, "language", "unknown"))
        return list(segments_iter)
    except Exception as exc:  # noqa: BLE001
        raise PipelineError(f"subtitle transcription failed: {exc}", code=70, step="subtitles") from exc


def _chunk_words(words: list[str], max_words: int, max_chars: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for word in words:
        candidate = _clean_text(" ".join([*current, word]))
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            chunks.append(current)
            current = [word]
            continue
        current.append(word)
    if current:
        chunks.append(current)
    return chunks


def _segment_from_words(words: list[Any], fallback_start: float, fallback_end: float) -> SubtitleSegment | None:
    pieces = [_clean_text(str(getattr(word, "word", ""))) for word in words]
    text = _clean_text(" ".join(piece for piece in pieces if piece))
    if not text:
        return None

    starts = [float(value) for value in (getattr(word, "start", None) for word in words) if value is not None]
    ends = [float(value) for value in (getattr(word, "end", None) for word in words) if value is not None]
    start = starts[0] if starts else fallback_start
    end = ends[-1] if ends else fallback_end
    if end <= start:
        end = max(fallback_end, start + 0.15)
    return SubtitleSegment(start=start, end=end, text=text)


def _split_text_without_word_timestamps(
    text: str,
    start: float,
    end: float,
    max_words: int,
    max_chars: int,
) -> list[SubtitleSegment]:
    words = [part for part in _clean_text(text).split(" ") if part]
    if not words:
        return []
    chunks = _chunk_words(words, max_words, max_chars)
    total = max(end - start, 0.15 * len(chunks))
    chunk_duration = total / len(chunks)
    segments: list[SubtitleSegment] = []
    for idx, chunk in enumerate(chunks):
        chunk_start = start + (idx * chunk_duration)
        chunk_end = end if idx == len(chunks) - 1 else chunk_start + chunk_duration
        segments.append(SubtitleSegment(chunk_start, max(chunk_end, chunk_start + 0.15), " ".join(chunk)))
    return segments


def postprocess_segments(raw_segments: list[Any], settings: Settings) -> list[SubtitleSegment]:
    max_words = int(settings.subtitles.max_words_per_line)
    max_chars = int(settings.subtitles.max_chars_per_line)
    processed: list[SubtitleSegment] = []

    for raw_segment in raw_segments:
        raw_start = float(getattr(raw_segment, "start", 0.0) or 0.0)
        raw_end = float(getattr(raw_segment, "end", raw_start + 0.5) or (raw_start + 0.5))
        words = list(getattr(raw_segment, "words", None) or [])
        if settings.subtitles.word_timestamps and words:
            current: list[Any] = []
            for word in words:
                token = _clean_text(str(getattr(word, "word", "")))
                if not token:
                    continue
                candidate = _segment_from_words([*current, word], raw_start, raw_end)
                if current and candidate and (
                    len(current) >= max_words or len(candidate.text) > max_chars
                ):
                    segment = _segment_from_words(current, raw_start, raw_end)
                    if segment:
                        processed.append(segment)
                    current = [word]
                    continue
                current.append(word)
            if current:
                segment = _segment_from_words(current, raw_start, raw_end)
                if segment:
                    processed.append(segment)
            continue

        processed.extend(
            _split_text_without_word_timestamps(
                str(getattr(raw_segment, "text", "")),
                raw_start,
                raw_end,
                max_words,
                max_chars,
            )
        )

    normalized: list[SubtitleSegment] = []
    for segment in processed:
        text = _clean_text(segment.text)
        if not text:
            continue
        start = max(0.0, float(segment.start))
        end = max(float(segment.end), start + 0.15)
        if normalized and start < normalized[-1].end:
            start = normalized[-1].end
            end = max(end, start + 0.15)
        normalized.append(SubtitleSegment(start=start, end=end, text=text))
    return normalized


def _format_ass_time(seconds: float) -> str:
    total_centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(total_centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _format_srt_time(seconds: float) -> str:
    total_milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _escape_ass_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
    return escaped.replace("\n", r"\N")


def _select_highlight_keyword(text: str) -> str | None:
    candidates = []
    for match in re.finditer(r"[A-Za-z][A-Za-z'-]*", text):
        word = match.group(0)
        normalized = word.lower()
        if normalized in STOPWORDS or len(normalized) < 4:
            continue
        score = len(normalized)
        if normalized in {"glucose", "protein", "fiber", "calories", "sodium", "fat", "sauce"}:
            score += 5
        candidates.append((score, match.start(), word))
    if not candidates:
        numeric = re.search(r"\b\d+(?:\.\d+)?\b", text)
        return numeric.group(0) if numeric else None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _apply_highlight(text: str, settings: Settings) -> str:
    keyword = _select_highlight_keyword(text)
    if not keyword:
        return _escape_ass_text(text)

    pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return _escape_ass_text(text)

    before = _escape_ass_text(text[: match.start()])
    highlighted = _escape_ass_text(match.group(0))
    after = _escape_ass_text(text[match.end() :])
    return (
        before
        + r"{\1c"
        + settings.subtitles.highlight_color
        + r"\bord2.4}"
        + highlighted
        + r"{\r}"
        + after
    )


def _ass_event_text(text: str, settings: Settings) -> str:
    pop_in_ms = max(0, int(settings.subtitles.pop_in_ms))
    fade_in_ms = max(0, int(settings.subtitles.fade_in_ms))
    fade_out_ms = max(0, int(settings.subtitles.fade_out_ms))
    base = _apply_highlight(text, settings)
    animation = (
        r"{\fscx94\fscy94"
        + rf"\t(0,{pop_in_ms},\fscx100\fscy100)"
        + rf"\fad({fade_in_ms},{fade_out_ms})"
        + "}"
    )
    return animation + base


def write_srt(segments: list[SubtitleSegment], output_path: Path) -> Path:
    lines: list[str] = []
    for idx, segment in enumerate(segments, start=1):
        lines.extend(
            [
                str(idx),
                f"{_format_srt_time(segment.start)} --> {_format_srt_time(segment.end)}",
                segment.text,
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def write_ass(
    segments: list[SubtitleSegment],
    output_path: Path,
    video_width: int,
    video_height: int,
    settings: Settings,
) -> Path:
    style = settings.subtitles
    bold = -1 if style.bold else 0
    content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,"
        f"{style.font_name},{style.font_size},{style.primary_color},&H000000FF,{style.outline_color},"
        f"{style.back_color},{bold},0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
        f"{style.alignment},{style.margin_l},{style.margin_r},{style.margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for segment in segments:
        content.append(
            "Dialogue: 0,"
            f"{_format_ass_time(segment.start)},{_format_ass_time(segment.end)},Default,,0,0,0,,"
            f"{_ass_event_text(segment.text, settings)}"
        )
    output_path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return output_path


def generate_subtitle_assets(video_path: Path, run_dir: Path, settings: Settings) -> tuple[Path, Path]:
    logger = get_logger(__name__, step="subtitles")
    wav_path = run_dir / "subtitles_audio.wav"
    srt_path = run_dir / "subtitles.srt"
    ass_path = run_dir / "subtitles.ass"

    extract_audio_wav(video_path, wav_path, settings)
    raw_segments = transcribe_whisper(wav_path, settings)
    segments = postprocess_segments(raw_segments, settings)
    if not segments:
        raise PipelineError("subtitle transcription produced no segments", code=70, step="subtitles")

    write_srt(segments, srt_path)
    write_ass(
        segments,
        ass_path,
        video_width=settings.render.width,
        video_height=settings.render.height,
        settings=settings,
    )
    logger.info("subtitle assets ready: %s and %s", srt_path, ass_path)
    return srt_path, ass_path
