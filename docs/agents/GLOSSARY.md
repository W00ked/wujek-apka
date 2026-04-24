# Glossary

## LOGI

Aplikacja / produkt analizujący posiłek i generujący treść wideo.

## UI segment

Część finalnego wideo pokazująca interfejs aplikacji, renderowana przez HyperFrames.

## HyperFrames

Narzędzie do deterministycznego renderowania HTML/kompozycji do wideo.

## Composition

Scena lub fragment sceny w HyperFrames, identyfikowany przez `data-composition-id`.

## Clip

Widoczny element na timeline HyperFrames. Powinien mieć `class="clip"` oraz metadane czasu.

## Timeline

GSAP timeline sterujący animacją kompozycji. Musi być `paused: true`.

## `window.__timelines`

Globalny registry timeline’ów HyperFrames.

## `window.LOGI_AD_DATA`

Globalny payload danych dynamicznych generowany przez Python pipeline.

## `static_project`

Tryb, w którym pipeline używa gotowego projektu HyperFrames i tylko dopina dane/assety.

## `jinja_dynamic`

Starszy tryb, w którym pipeline generuje `index.html` z `tamplate.html`.