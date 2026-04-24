# Meal Scan Commercial HyperFrames Template

A 30-second vertical HyperFrames ad composition showing the app workflow from food-photo hook to add-meal sheet, scanning, journal result, nutrition label, ingredients, insights, and CTA.

## Creative concept

**Dish name:** Bun Bomb Burger  
**Hook:** Looks delicious. The scan says otherwise.

The first scene uses a cropped, moving food photo rather than a static image. The later scenes use supplied app screenshots as source plates, with HyperFrames/GSAP overlays for taps, scan beams, result pops, risk chips, screen transitions, and CTA movement.

## Timeline

| Time | Scene | Purpose |
|---:|---|---|
| 0.0–3.6s | Hook | Dynamic food image, creative dish name, strong risk-based hook |
| 3.1–8.0s | Add meal | User adds photo/description in the app |
| 7.8–11.8s | Scanning | AI scan visual, soft scan sweep, ingredient/nutrition chips |
| 11.4–15.7s | Results | Loading journal state transitions to the completed result |
| 15.2–19.3s | Nutrition | Detail page and nutrition label callouts |
| 18.9–22.7s | Ingredients | Full ingredient breakdown and GI/GL chips |
| 22.4–26.7s | Insights | Meal insights and risk warnings |
| 26.2–30.0s | CTA | Product summary and end card |

## HyperFrames commands

```bash
npx hyperframes lint
npx hyperframes preview
npx hyperframes render --quality draft --output preview.mp4
npx hyperframes render --output output.mp4
```

## Notes

- Main composition id is `dashboard` to stay compatible with the prior package convention.
- All animation is deterministic GSAP. No video/audio playback is controlled in script.
- SFX are generated placeholder WAV files and are intentionally subtle.
- Replace screenshot plates with real app export assets or screen recordings when ready.
