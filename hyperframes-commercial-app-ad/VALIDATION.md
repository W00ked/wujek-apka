# Validation checklist

Static structure was prepared against the HyperFrames contract:

- Main root: `id="main"`, `data-composition-id="dashboard"`, `data-start="0"`, `data-width="1080"`, `data-height="1920"`.
- Nested composition slots use `data-composition-id`, `data-composition-src`, `data-start`, and `data-track-index`.
- Nested composition slots intentionally do not use `data-duration`.
- All external composition files are wrapped in `<template>`.
- Every nested root defines `data-composition-id`, `data-width`, and `data-height`.
- Every primitive visible clip has `id`, `class="clip"`, `data-start`, `data-duration`, and `data-track-index`.
- Audio clips have `id`, `src`, `data-start`, `data-duration`, `data-volume`, and `data-track-index`.
- Every composition creates `gsap.timeline({ paused: true })`.
- Every composition registers `window.__timelines["composition-id"]` with the matching composition id.
- No `data-layer` or `data-end` attributes are used.
- No media playback is controlled in scripts.
- The root timeline extends to 30 seconds.

Run the official linter before final rendering:

```bash
npx hyperframes lint
```
