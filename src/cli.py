from __future__ import annotations

from pathlib import Path

import click

from .config import load_settings
from .errors import PipelineError
from .pipeline import PipelineRequest, run_pipeline


@click.command()
@click.option("--config", "config_path", type=click.Path(path_type=Path), default="config.yaml")
@click.option(
    "--dish",
    type=str,
    default=None,
    help="Dish name. Generates a food image, uploads it, then scans it with LOGI.",
)
@click.option("--prompt", type=str, default=None)
@click.option("--image-url", type=str, default=None)
@click.option("--use-cached-scan", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--skip-intro", is_flag=True, default=False)
@click.option("--regenerate-image", is_flag=True, default=False)
@click.option("--image-variants", type=click.IntRange(1, 4), default=None)
@click.option("--max-image-cost-usd", type=float, default=None)
@click.option("--allow-high-cost", is_flag=True, default=None)
@click.option("--language", type=str, default="en")
def main(
    config_path: Path,
    dish: str | None,
    prompt: str | None,
    image_url: str | None,
    use_cached_scan: Path | None,
    skip_intro: bool,
    regenerate_image: bool,
    image_variants: int | None,
    max_image_cost_usd: float | None,
    allow_high_cost: bool | None,
    language: str,
) -> None:
    """Run the LOGI vertical video pipeline."""

    try:
        settings = load_settings(config_path)
        output_path = run_pipeline(
            PipelineRequest(
                dish=dish,
                prompt=prompt,
                image_url=image_url,
                use_cached_scan=use_cached_scan,
                skip_intro=skip_intro,
                regenerate_image=regenerate_image,
                image_variants=image_variants,
                max_image_cost_usd=max_image_cost_usd,
                allow_high_cost=allow_high_cost,
                language=language,
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
