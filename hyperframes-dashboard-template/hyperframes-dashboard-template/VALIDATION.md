# HyperFrames validation checklist

- [x] Main root uses `id="main"`, `data-composition-id="dashboard"`, `data-start="0"`, `data-width="1080"`, and `data-height="1920"`.
- [x] All nested composition files are wrapped in `<template>`.
- [x] Every nested root defines `data-composition-id`, `data-width`, and `data-height`.
- [x] Composition slots include `id`, `class="clip"`, `data-composition-id`, `data-composition-src`, `data-start`, and `data-track-index`.
- [x] Composition slots do not include `data-duration`.
- [x] Primitive visible clips include unique `id`, `class="clip"`, `data-start`, `data-duration`, and `data-track-index`.
- [x] No `data-layer` or `data-end` attributes are used.
- [x] No video or audio playback is manually controlled.
- [x] Timelines use `gsap.timeline({ paused: true })`.
- [x] Each timeline is registered in `window.__timelines` under its exact composition id.
- [x] Layout uses absolute positioning for deterministic rendering.
- [x] CSS is embedded and scoped to local composition roots.
- [x] Main choreography is deterministic and does not use timers, randomness, interactions, or wall-clock APIs.
- [x] Placeholder imagery is CSS-based and documented in `assets/README.md`.

Recommended CLI commands:

```bash
npx hyperframes lint
npx hyperframes preview
npx hyperframes render --quality draft --output preview.mp4
npx hyperframes render --output output.mp4
```
