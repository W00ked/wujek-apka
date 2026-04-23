from __future__ import annotations

from pathlib import Path

import click

from .config import load_settings
from .errors import PipelineError
from .pipeline import PipelineRequest, run_pipeline


@click.command()
@click.option("--config", "config_path", type=click.Path(path_type=Path), default="config.yaml")
@click.option("--prompt", type=str, default=None)
@click.option("--image-url", type=str, default=None)
@click.option("--use-cached-scan", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--skip-intro", is_flag=True, default=False)
def main(
    config_path: Path,
    prompt: str | None,
    image_url: str | None,
    use_cached_scan: Path | None,
    skip_intro: bool,
) -> None:
    """Run the LOGI vertical video pipeline."""

    try:
        settings = load_settings(config_path)
        output_path = run_pipeline(
            PipelineRequest(
                prompt=prompt,
                image_url=image_url,
                use_cached_scan=use_cached_scan,
                skip_intro=skip_intro,
            ),
            settings,
        )
    except PipelineError as exc:
        click.echo(f"[{exc.step}] {exc}", err=True)
        raise SystemExit(exc.code) from exc
    except Exception as exc:  # noqa: BLE001
        click.echo(f"[unexpected] {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(str(output_path))


if __name__ == "__main__":
    main()
