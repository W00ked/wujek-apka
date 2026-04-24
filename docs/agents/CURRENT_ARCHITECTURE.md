# Current architecture

Aktualna architektura:

- UI video backend: HyperFrames.
- Legacy backend: Playwright, tylko jako fallback.
- Format wideo: 1080x1920.
- FPS: 30.
- Aktualny HyperFrames project template: `hyperframes-commercial-app-ad`.
- Aktualny render mode: `static_project`.
- HyperFrames CLI: `hyperframes@0.4.17`.
- Dane dynamiczne dla template: `window.LOGI_AD_DATA`.
- Runtime template: lokalny GSAP + `dynamic-ad.js`.
- Finalne MP4 składane przez Python pipeline z audio, napisami i opcjonalnym HeyGen intro.

Nie zmieniaj tej architektury bez wyraźnej decyzji.