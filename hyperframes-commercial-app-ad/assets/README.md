# Asset manifest

This ad package uses the supplied app screenshots as source plates so the commercial remains visually faithful to the current UI. Replace these files with cleaner export assets when available.

## Included source plates

- `assets/hero-burger-close.jpg` — cropped burger/fries hero image used in the opening hook.
- `assets/screens/app-add-empty.png` — add-meal sheet before typing.
- `assets/screens/app-add-filled.png` — add-meal sheet after the food description/photo is present.
- `assets/screens/app-add-loading.png` — add button loading state.
- `assets/screens/app-journal-loading.png` — journal card loading state.
- `assets/screens/app-journal-result.png` — journal card with Burger with fries result.
- `assets/screens/app-meal-detail.png` — meal detail hero/nutrition area.
- `assets/screens/app-nutrition.png` — nutrition card focused viewport.
- `assets/screens/app-ingredients-top.png` — ingredients list top.
- `assets/screens/app-ingredients-bottom.png` — ingredients bottom and insights transition.
- `assets/screens/app-insights.png` — full meal insights card.

## Suggested later replacements

- `avatar-reactor.mov` or `avatar-reactor.webm` — optional talking/reacting avatar overlay for the hook. Keep it as a separate video clip and animate a wrapper, not the video element directly.
- `brand-logo.png` — optional app logo for the CTA end card.
- Real app screen recordings can replace the screenshot plates; if added, keep playback declarative with `data-start`, `data-media-start`, `data-duration`, and `data-volume`.

## Audio

The generated WAV files are subtle SFX placeholders:

- `audio/tap-soft.wav`
- `audio/whoosh-soft.wav`
- `audio/scan-sweep.wav`
- `audio/result-pop.wav`
- `audio/cta-chime.wav`
- `audio/subtle-bed.wav`
