from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .config import Settings
from .errors import PipelineError
from .logging_utils import get_logger


def run_hyperframes_render(
    hf_project_dir: Path,
    output_mp4: Path,
    settings: Settings,
) -> Path:
    """
    Invoke `hyperframes render` on a project directory containing index.html.
    Returns path to the rendered MP4 (same as output_mp4).
    """
    logger = get_logger(__name__, step="hyperframes")
    hf_project_dir = hf_project_dir.resolve()
    output_mp4 = output_mp4.resolve()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        settings.hyperframes.npx_command,
        "--yes",
        "hyperframes",
        "render",
        str(hf_project_dir),
        "--output",
        str(output_mp4),
        "--fps",
        str(int(settings.render.fps)),
        "--quality",
        settings.hyperframes.quality,
        "--format",
        "mp4",
    ]
    if settings.hyperframes.quiet:
        cmd.append("--quiet")
    cmd.extend(settings.hyperframes.extra_args)

    env = os.environ.copy()
    if settings.hyperframes.node_options:
        env["NODE_OPTIONS"] = settings.hyperframes.node_options

    timeout = max(60, int(settings.hyperframes.render_timeout_sec))
    logger.info("running HyperFrames render: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            cwd=str(hf_project_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(
            f"HyperFrames render timed out after {timeout}s",
            code=50,
            step="hyperframes",
        ) from exc
    except FileNotFoundError as exc:
        raise PipelineError(
            f"HyperFrames CLI not found ({settings.hyperframes.npx_command}). Install Node.js 22+ and ensure npx is on PATH.",
            code=50,
            step="hyperframes",
        ) from exc

    if result.stdout:
        logger.info("%s", result.stdout.rstrip())
    if result.stderr:
        logger.warning("%s", result.stderr.rstrip())

    if result.returncode != 0:
        raise PipelineError(
            f"hyperframes render failed (exit {result.returncode})",
            code=50,
            step="hyperframes",
        )

    if not output_mp4.is_file():
        raise PipelineError(
            f"HyperFrames did not produce output file: {output_mp4}",
            code=50,
            step="hyperframes",
        )

    return output_mp4


def copy_hf_artifacts_to_page_mirror(hf_project_dir: Path, page_dir: Path) -> None:
    """Optional: keep page/index.html mirror for debugging (index + assets)."""
    import shutil

    page_dir.mkdir(parents=True, exist_ok=True)
    idx = hf_project_dir / "index.html"
    if idx.exists():
        shutil.copy2(idx, page_dir / "index.html")
    assets_src = hf_project_dir / "assets"
    if assets_src.is_dir():
        dest = page_dir / "assets"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(assets_src, dest)
