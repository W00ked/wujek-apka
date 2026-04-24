# Asset manifest for the HyperFrames dashboard template

The supplied screenshots did not include separable source assets, so the template uses deterministic CSS placeholders for all app imagery. Replace these placeholders with production assets when available.

Suggested asset filenames and dimensions:

- `avatar-user.png` — 256x256 transparent or square profile image. Usage: `compositions/header.html`, replace `#header-avatar` background.
- `food-chicken-cheese-salad.jpg` — 340x340. Usage: `compositions/journal-card.html`, replace `#journal-thumb-1` CSS background.
- `food-hamburger.jpg` — 340x340. Usage: `compositions/journal-card.html`, replace `#journal-thumb-2` CSS background.
- `food-fried-egg-ketchup.jpg` — 340x340. Usage: `compositions/journal-card.html`, replace `#journal-thumb-3` CSS background.
- `education-insulin-resistance.jpg` — 1200x660. Usage: `compositions/education.html`, replace `#education-image-1` CSS background.
- `education-insulin-factors.jpg` — 724x660. Usage: `compositions/education.html`, replace `#education-image-2` CSS background.
- `mascot-feedback.png` — 640x500 transparent PNG. Usage: `compositions/tools.html`, replace `#tools-feedback-berry` text placeholder.
- `mascot-rate-app.png` — 640x500 transparent PNG. Usage: `compositions/tools.html`, replace `#tools-rate-berry` text placeholder.
- `mascot-share.png` — 640x500 transparent PNG. Usage: `compositions/tools.html`, replace `#tools-share-berry` text placeholder.

If replacing CSS placeholders with images, use an `img` clip with a unique id, `class="clip"`, `data-start`, `data-duration`, and `data-track-index`, plus `object-fit: cover` and fixed dimensions.
