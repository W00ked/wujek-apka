# Task routing for agent

## Jeśli zadanie dotyczy wyglądu sceny

Czytaj:

- `HYPERFRAMES_TEMPLATE_PATTERNS.md`
- `ANIMATION_RULES.md`
- istniejący template w `hyperframes-commercial-app-ad/`

Nie zmieniaj pipeline’u Pythonowego.

## Jeśli zadanie dotyczy animacji

Czytaj:

- `ANIMATION_RULES.md`
- `HYPERFRAMES_CONTRACT.md`

Sprawdź:
- czy timeline jest paused,
- czy jest zarejestrowany,
- czy composition id się zgadza.

## Jeśli zadanie dotyczy błędu renderu

Czytaj:

- `RENDER_PIPELINE.md`
- `HYPERFRAMES.md`
- `config.yaml`
- `src/hyperframes_runner.py`
- `src/render_hyperframes.py`

Sprawdź:
- Node,
- FFmpeg,
- Chrome,
- `npx_command`,
- `hyperframes.cli_package`,
- ścieżki assetów.

## Jeśli zadanie dotyczy danych w template

Czytaj:

- `src/render_hyperframes.py`
- `assets/hyperframes/dynamic-ad.js`
- `PROJECT_OVERVIEW.md`

Nie zakładaj, że dane przychodzą z fetch/API w przeglądarce.
Szukaj `window.LOGI_AD_DATA`.

## Jeśli zadanie dotyczy React

Ustal najpierw, czy projekt faktycznie używa React w tej części.
Nie przepisuj HyperFrames template na React bez wyraźnego polecenia.