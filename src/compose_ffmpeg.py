from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Settings
from .errors import PipelineError
from .logging_utils import get_logger


def _run(command: list[str], *, step: str) -> subprocess.CompletedProcess[str]:
    logger = get_logger(__name__, step=step)
    logger.debug("running command: %s", " ".join(command))
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        binary = command[0] if command else "?"
        raise PipelineError(
            f"Nie znaleziono programu: {binary}. Zainstaluj FFmpeg (ffmpeg + ffprobe) i dodaj katalog bin do PATH "
            f"albo ustaw w config.yaml pełne ścieżki: ffmpeg.binary oraz ffmpeg.ffprobe_binary. "
            f"(np. winget install Gyan.FFmpeg lub pobierz z https://www.gyan.dev/ffmpeg/builds/)",
            code=60,
            step=step,
        ) from exc
    if result.returncode != 0:
        logger.error("command failed: %s", result.stderr)
        raise PipelineError(
            f"{step} failed with exit code {result.returncode}",
            code=60,
            step=step,
        )
    return result


def _escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def probe_has_audio(path: Path, settings: Settings) -> bool:
    """True if file has at least one audio stream (HeyGen photo avatars are often video-only)."""
    result = subprocess.run(
        [
            settings.ffmpeg.ffprobe_binary,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def probe_duration(path: Path, settings: Settings) -> float:
    result = _run(
        [
            settings.ffmpeg.ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        step="ffprobe",
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise PipelineError(f"could not parse duration for {path}", code=60, step="ffprobe") from exc


def normalize_video(
    input_path: Path,
    output_path: Path,
    settings: Settings,
    *,
    strip_audio: bool = True,
    start_offset_sec: float = 0.0,
    fill_canvas: bool = False,
) -> Path:
    """Scale/pad to canvas. UI clips use strip_audio=True; HeyGen intro must keep strip_audio=False."""
    if fill_canvas:
        scale_filter = (
            f"scale={settings.render.width}:{settings.render.height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={settings.render.width}:{settings.render.height},"
            f"fps={settings.render.fps},format=yuv420p,setsar=1"
        )
    else:
        scale_filter = (
            f"scale={settings.render.width}:{settings.render.height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={settings.render.width}:{settings.render.height}:(ow-iw)/2:(oh-ih)/2:color=white,"
            f"fps={settings.render.fps},format=yuv420p,setsar=1"
        )
    command: list[str] = [
        settings.ffmpeg.binary,
        "-y",
    ]
    if start_offset_sec > 0:
        command += ["-ss", f"{start_offset_sec:.3f}"]
    command += [
        "-i",
        str(input_path),
    ]
    command += [
        "-vf",
        scale_filter,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-metadata:s:v:0",
        "rotate=0",
    ]
    if strip_audio:
        command += ["-an", str(output_path)]
    else:
        command += [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(output_path),
        ]
    _run(command, step="ffmpeg-normalize")
    return output_path


def truncate_clip_keep_audio(
    input_path: Path,
    output_path: Path,
    max_duration_sec: float,
    settings: Settings,
) -> Path:
    """Shorten clip to at most max_duration_sec. Re-encode video; keep or add AAC if present."""
    dur = probe_duration(input_path, settings)
    use_sec = min(dur, max_duration_sec)
    has_a = probe_has_audio(input_path, settings)
    command: list[str] = [
        settings.ffmpeg.binary,
        "-y",
        "-i",
        str(input_path),
        "-t",
        f"{use_sec:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_a:
        command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(output_path)]
    else:
        command += ["-an", str(output_path)]
    _run(command, step="ffmpeg-intro-truncate")
    return output_path


def trim_or_pad_video(
    input_path: Path,
    output_path: Path,
    target_duration_sec: float,
    settings: Settings,
) -> Path:
    source_duration = probe_duration(input_path, settings)
    delta = max(0.0, target_duration_sec - source_duration)
    vf = []
    if delta > 0.05:
        vf.append(f"tpad=stop_mode=clone:stop_duration={delta:.3f}")
    if vf:
        vf.append("format=yuv420p")

    command = [
        settings.ffmpeg.binary,
        "-y",
        "-i",
        str(input_path),
    ]
    if vf:
        command += ["-vf", ",".join(vf)]
    command += [
        "-t",
        f"{target_duration_sec:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(output_path),
    ]
    _run(command, step="ffmpeg-trim-pad")
    return output_path


def mux_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    settings: Settings,
) -> Path:
    _run(
        [
            settings.ffmpeg.binary,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ],
        step="ffmpeg-mux-audio",
    )
    return output_path


def burn_ass_subtitles(
    input_path: Path,
    ass_path: Path,
    output_path: Path,
    settings: Settings,
) -> Path:
    filter_value = f"ass='{_escape_filter_path(ass_path)}'"
    if settings.subtitles.fontsdir:
        filter_value += f":fontsdir='{_escape_filter_path(settings.subtitles.fontsdir)}'"
    _run(
        [
            settings.ffmpeg.binary,
            "-y",
            "-i",
            str(input_path),
            "-vf",
            filter_value,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        step="ffmpeg-burn-subtitles",
    )
    return output_path


def ensure_stereo_aac_audio(path_in: Path, path_out: Path, settings: Settings) -> Path:
    """Guarantee exactly one stereo AAC track for concat. If input has no audio, add silence (same duration as video)."""
    logger = get_logger(__name__, step="ffmpeg")
    if probe_has_audio(path_in, settings):
        _run(
            [
                settings.ffmpeg.binary,
                "-y",
                "-i",
                str(path_in),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(path_out),
            ],
            step="ffmpeg-aac-normalize",
        )
        return path_out

    logger.warning(
        "clip has no audio track (e.g. HeyGen still/photo output); adding silent AAC so concat keeps UI sound"
    )
    _run(
        [
            settings.ffmpeg.binary,
            "-y",
            "-i",
            str(path_in),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ac",
            "2",
            "-shortest",
            str(path_out),
        ],
        step="ffmpeg-silent-pad",
    )
    return path_out


def concat_two_segments(first: Path, second: Path, output_path: Path, settings: Settings) -> Path:
    """Join two clips with filter_complex. Both must have video + audio (use ensure_stereo_aac_audio first)."""
    _run(
        [
            settings.ffmpeg.binary,
            "-y",
            "-i",
            str(first),
            "-i",
            str(second),
            "-filter_complex",
            "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]",
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        step="ffmpeg-concat-av",
    )
    return output_path


def concat_videos(video_paths: list[Path], output_path: Path, settings: Settings) -> Path:
    """Concatenate 2+ segments (fallback list demuxer). Two segments use filter concat so intro without audio does not drop UI audio."""
    if len(video_paths) == 2:
        stem = output_path.stem
        parent = output_path.parent
        a = ensure_stereo_aac_audio(video_paths[0], parent / f"{stem}_seg0_aac.mp4", settings)
        b = ensure_stereo_aac_audio(video_paths[1], parent / f"{stem}_seg1_aac.mp4", settings)
        return concat_two_segments(a, b, output_path, settings)
    list_path = output_path.with_suffix(".txt")
    lines = [f"file '{path.as_posix()}'" for path in video_paths]
    list_path.write_text("\n".join(lines), encoding="utf-8")
    _run(
        [
            settings.ffmpeg.binary,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        step="ffmpeg-concat",
    )
    return output_path


def final_trim(input_path: Path, output_path: Path, settings: Settings) -> Path:
    _run(
        [
            settings.ffmpeg.binary,
            "-y",
            "-i",
            str(input_path),
            "-t",
            str(settings.render.max_duration_sec),
            "-c",
            "copy",
            str(output_path),
        ],
        step="ffmpeg-final-trim",
    )
    return output_path


def copy_latest(final_path: Path, latest_path: Path) -> None:
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_path, latest_path)
