# HyperFrames validation checklist

Static structural audit passed before packaging.

- Main root uses `id="main"`, `data-composition-id="dashboard"`, `data-start="0"`, `data-width="1080"`, and `data-height="1920"`.
- Nested files are wrapped in `<template>`.
- Nested roots define `data-composition-id`, `data-width`, and `data-height`.
- Composition slots include `id`, `class="clip"`, `data-composition-id`, `data-composition-src`, `data-start`, and `data-track-index`.
- Composition slots do not include `data-duration`.
- Primitive visible clips include unique `id`, `class="clip"`, `data-start`, `data-duration`, and `data-track-index`.
- Timeline keys match composition IDs.
- All timelines use `gsap.timeline({ paused: true })` and register in `window.__timelines`.
- No `data-layer` or `data-end` attributes are used.
- No video/audio playback is manually controlled.
- No `setTimeout`, `setInterval`, `Date.now`, `Math.random`, or `requestAnimationFrame` is used.
- UI layout is deterministic and absolute-positioned.
- Image clips have fixed dimensions and `object-fit: cover`.
- CSS is scoped to each composition root.

Recommended runtime checks:

```bash
npx hyperframes lint
npx hyperframes preview
npx hyperframes render --quality draft --output preview.mp4
npx hyperframes render --output output.mp4
```
