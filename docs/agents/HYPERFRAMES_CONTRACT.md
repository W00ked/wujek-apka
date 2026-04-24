# HyperFrames contract

Ten plik jest źródłem prawdy dla struktury HyperFrames w tym projekcie.

## Root composition

Główna kompozycja powinna mieć:

- `id="main"` albo projektowo ustalony root id,
- `data-composition-id`,
- `data-start="0"`,
- `data-width="1080"`,
- `data-height="1920"`.

W tym projekcie format domyślny to pionowe wideo 1080x1920, 30 fps.

## Nested compositions

Zewnętrzne pliki kompozycji mają być zawinięte w:

```html
<template>
  ...
</template>

Każdy nested root musi mieć:

data-composition-id
data-width
data-height

Slot kompozycji powinien mieć:

id
class="clip"
data-composition-id
data-composition-src
data-start
data-track-index

Sloty kompozycji nie powinny mieć data-duration.

Primitive visible clips

Każdy widoczny clip powinien mieć:

id
class="clip"
data-start
data-duration
data-track-index

Każdy id musi być unikalny.

Timeline

Każda kompozycja musi tworzyć timeline:

const tl = gsap.timeline({ paused: true });

Każda kompozycja musi zarejestrować timeline:

window.__timelines = window.__timelines || {};
window.__timelines["exact-composition-id"] = tl;

Klucz w window.__timelines musi być dokładnie taki sam jak data-composition-id.

Zakazane

Nie używaj:

data-layer
data-end
setTimeout
setInterval
Date.now
Math.random
requestAnimationFrame
interakcji użytkownika jako warunku animacji
ręcznego sterowania audio/video w JS
losowych opóźnień
wall-clock APIs
Rendering deterministyczny

Render musi być powtarzalny. Ten sam input powinien dawać ten sam output.
Animacje mają wynikać z timeline GSAP, a nie z zegara przeglądarki.

Assety

Preferuj lokalne assety w assets/.
Nie polegaj na CDN w produkcyjnym renderze.
Obrazy powinny mieć stałe wymiary i object-fit: cover.


---

## `docs/agent/HYPERFRAMES_TEMPLATE_PATTERNS.md`

```md
# HyperFrames template patterns

## Cel

Template HyperFrames ma być składany jak scena wideo, nie jak zwykła aplikacja React.

Priorytety:

1. deterministyczny layout,
2. absolutne pozycjonowanie,
3. stałe wymiary,
4. czytelna hierarchia clipów,
5. timeline GSAP zarejestrowany w `window.__timelines`,
6. brak zależności od interakcji użytkownika.

## Preferowany styl layoutu

Dla renderów wideo preferuj:

```css
position: absolute;
width: ...px;
height: ...px;
left: ...px;
top: ...px;
overflow: hidden;

Unikaj layoutów zależnych od dynamicznego flow, jeśli mogą zmienić wysokość sceny i rozjechać timing.

Clip pattern
<div
  id="hero-card"
  class="clip"
  data-start="0"
  data-duration="6"
  data-track-index="1"
>
  ...
</div>
Composition slot pattern
<div
  id="slot-header"
  class="clip"
  data-composition-id="header"
  data-composition-src="./compositions/header.html"
  data-start="0"
  data-track-index="1"
></div>

Nie dodawaj data-duration do slotu kompozycji, jeśli projektowy kontrakt tego zabrania.

Nested file pattern
<template>
  <section
    id="header-root"
    data-composition-id="header"
    data-width="1080"
    data-height="260"
  >
    ...
  </section>

  <script src="../assets/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {};
    const tl = gsap.timeline({ paused: true });

    // animations

    window.__timelines["header"] = tl;
  </script>
</template>
Dane dynamiczne

Dane runtime są wystawiane przez:

window.LOGI_AD_DATA

Nie zakładaj, że dane są dostępne synchronicznie z API. W template używaj danych z payloadu przygotowanego przez pipeline.

GSAP

Używaj tylko timeline paused:

const tl = gsap.timeline({ paused: true });

Dobre animacje:

tl.fromTo("#card", { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0);

Nie używaj animacji opartych o eventy, hover, scroll użytkownika lub czas systemowy.


---

## `docs/agent/ANIMATION_RULES.md`

```md
# Animation rules

## Rola animacji

Animacje w tym projekcie mają tworzyć gotowy segment wideo, nie interaktywny UI.

Animacja powinna być:
- przewidywalna,
- powtarzalna,
- zsynchronizowana z voiceoverem,
- bez zależności od użytkownika,
- łatwa do renderu przez HyperFrames.

## Podstawowy pattern

```js
window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused: true });

tl.fromTo(
  "#main-card",
  { autoAlpha: 0, y: 48 },
  { autoAlpha: 1, y: 0, duration: 0.7, ease: "power2.out" },
  0
);

window.__timelines["composition-id"] = tl;
Timing

Preferuj jawne offsety:

tl.to("#item-1", { autoAlpha: 1, duration: 0.4 }, 0.2);
tl.to("#item-2", { autoAlpha: 1, duration: 0.4 }, 0.5);
tl.to("#item-3", { autoAlpha: 1, duration: 0.4 }, 0.8);

Nie opieraj się na naturalnym czasie przeglądarki.

Scroll simulation

Jeśli scena przewija długą zawartość, używaj transformacji root/canvas:

const canvas = document.querySelector('[data-motion-root="canvas"]');
const viewport = 1920;
const maxY = Math.max(0, (canvas ? canvas.scrollHeight : 0) - viewport);

if (canvas) {
  tl.to(canvas, { y: -maxY, duration: 20, ease: "none", force3D: true }, 0);
}
Wydajność

Dla elementów animowanych preferuj:

will-change: transform, opacity;
backface-visibility: hidden;
transform-origin: center center;

Dla obrazów:

object-fit: cover;
transform: translateZ(0);
backface-visibility: hidden;
Zakazane

Nie używaj:

setTimeout(...)
setInterval(...)
Date.now()
Math.random()
requestAnimationFrame(...)
element.play()
video.pause()
audio.currentTime = ...
Błędy typowe
timeline nie jest paused: true,
timeline nie jest dodany do window.__timelines,
composition id w HTML i JS się różnią,
element animowany nie ma stabilnego selektora,
asset jest z CDN i nie działa w renderze,
layout zależy od dynamicznej wysokości i ucina elementy w 1080x1920.

---

## `docs/agent/RENDER_PIPELINE.md`

```md
# Render pipeline

## Główna idea

Projekt generuje finalny plik MP4 przez pipeline Pythonowy.
HyperFrames odpowiada tylko za segment UI.

## Tryby

W `config.yaml`:

```yaml
render:
  ui_backend: hyperframes

oznacza, że UI renderuje HyperFrames.

hyperframes:
  render_mode: static_project

oznacza, że pipeline używa statycznego projektu HyperFrames i synchronizuje dane/assety.

Przygotowanie projektu HyperFrames

Pipeline:

bierze katalog z hyperframes.project_template_dir,
kopiuje go do artifacts/<run>/hf_project,
kopiuje assety do hf_project/assets,
zapisuje dynamiczne dane do assets/logi_ad_data.js,
dołącza dynamic-ad.js,
odpala render przez CLI.
Ważne assety
assets/vendor/gsap.min.js
assets/hyperframes/dynamic-ad.js
assets/logi_ad_data.js
placeholder image z render.placeholder_asset
Render CLI

Debug ręczny:

cd path/to/hf_project
npx hyperframes render . --output out.mp4 --fps 30 --quiet

W projekcie używana jest wersja:

hyperframes@0.4.17

Na Windows preferowany jest pełny path do npx.cmd, jeśli środowisko go nie widzi.

Testy po zmianach template

Po zmianie template HyperFrames zaproponuj:

npx hyperframes lint
npx hyperframes preview
npx hyperframes render --quality draft --output preview.mp4

Jeśli render idzie przez pipeline, sprawdź też końcowy output w output/.


---

## `docs/agent/COMMON_MISTAKES.md`

```md
# Common mistakes

## HyperFrames

1. Mylenie zwykłego React/HTML z HyperFrames composition contract.
2. Brak `window.__timelines["composition-id"]`.
3. Inny `composition-id` w HTML i JS.
4. Użycie `data-end` albo `data-layer`.
5. Dodawanie `data-duration` do slotu nested composition, gdy projektowy kontrakt tego zabrania.
6. Brak unikalnych `id` dla clipów.
7. Brak `class="clip"` na widocznych elementach.
8. Używanie timerów i losowości.
9. Assety z CDN zamiast lokalnych plików.
10. Zależność od interakcji użytkownika.
11. Layout bez stałych wymiarów.
12. Dynamiczne treści bez ograniczeń wysokości.
13. Brak `object-fit: cover` na obrazach.
14. Manualne sterowanie audio/video w template.

## Projekt

1. Zmiana pipeline’u, kiedy wystarczy zmienić template.
2. Zmiana `config.yaml` bez potrzeby.
3. Mieszanie trybu `jinja_dynamic` i `static_project`.
4. Usunięcie synchronizacji `dynamic-ad.js`.
5. Usunięcie lokalnego GSAP.
6. Założenie, że Playwright nadal jest głównym backendem UI.
7. Ignorowanie Windows paths dla `npx`, FFmpeg i Chrome.
8. Tworzenie nowych abstrakcji bez sprawdzenia istniejących plików.