# HyperFrames (UI video)

This pipeline can render the LOGI HTML template with **HyperFrames** instead of recording the page with Playwright.

## Requirements

- **Node.js** 22 or newer (`node -v`)
- **FFmpeg** on `PATH` (same as the rest of the pipeline; you can set full paths in `config.yaml` under `ffmpeg`)
- **Chrome** for headless capture: run once if renders fail with a browser error:

  ```bash
  npx hyperframes browser ensure
  ```

- **npx** available in the shell that runs the app. On Windows, if `npx` fails from Python, set `hyperframes.npx_command` in `config.yaml` to the full path of `npx.cmd` (e.g. under `Program Files\nodejs`). If the integrated terminal prepends a broken Cursor `node`/`npm` shim, run CLI checks from repo root with `.\scripts\hyperframes-run.ps1 --yes hyperframes@0.4.17 doctor` (the script prepends system Node to `PATH`).

## Configuration

- `render.ui_backend: hyperframes` — use HyperFrames for the UI segment (default in this project).
- `render.ui_backend: playwright` — legacy: static server + Playwright video capture.
- `hyperframes.project_template_dir` — folder created with `hyperframes init` (this repo ships `hyperframes_composition/`). Each run copies it to `artifacts/<run>/hf_project/` and overwrites `index.html`.

## Manual render (debug)

From a copied project directory that contains `index.html`:

```bash
cd path/to/hf_project
npx hyperframes render . --output out.mp4 --fps 30 --quiet
```

## Switching back to Playwright

Set `render.ui_backend: playwright` in `config.yaml`. The Playwright path still uses `tamplate.html`, `scroll_driver.js`, and `assets/vendor/gsap.min.js` as before.
