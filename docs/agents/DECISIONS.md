# Project decisions

## HyperFrames over Playwright

UI segment jest renderowany przez HyperFrames, a nie nagrywany przez Playwright, bo HyperFrames daje bardziej deterministyczny render sceny wideo.

## Static project mode

Aktualny tryb to `static_project`.
Template HyperFrames jest utrzymywany jako osobny projekt kompozycji, a pipeline tylko synchronizuje dane i assety.

## Local assets

GSAP i runtime dynamiczny powinny być lokalne, nie CDN, żeby render był stabilny.

## Deterministic animation

Animacje muszą być deterministyczne:
- bez timerów,
- bez losowości,
- bez interakcji,
- bez wall-clock APIs.

## Windows compatibility

Ścieżki do `npx`, FFmpeg i narzędzi mogą wymagać pełnych pathów, bo środowiska terminalowe/IDE potrafią mieć inny PATH.