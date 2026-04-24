# LOGI API — dokumentacja w kontekście projektu **vieo**

Ten dokument opisuje, jak projekt **vieo** komunikuje się z API LOGI (skan posiłku / analiza żywieniowa): endpoint, autoryzację, treść żądania i odpowiedzi, obsługę błędów, miejsca w kodzie oraz artefakty zapisane na dysku.

Oficjalna dokumentacja usługi LOGI (poza tym repozytorium) może się różnić — tutaj opisano **konkretną integrację** zaimplementowaną w `src/logi_client.py` i modele w `src/models/scan.py`.

---

## 1. Cel integracji

LOGI zwraca ustrukturyzowany wynik analizy posiłku (tekst z `prompt` lub obraz z `image_url`). Pipeline **vieo** używa tego jako wejścia do dalszych kroków: plan skryptu (OpenAI), TTS, render UI itd.

---

## 2. Konfiguracja

| Źródło | Opis |
|--------|------|
| **`config.yaml`** → sekcja `logi` | `base_url`, `timeout_sec`, `language` |
| **`.env`** | `LOGI_API_KEY` (mapowane w `Settings` jako `secrets.logi_api_key`) |

Domyślne wartości w repozytorium (fragment `config.yaml`):

```yaml
logi:
  base_url: https://apilogi.com/demo/scan
  timeout_sec: 60
  language: en
```

Klucz nie jest commitowany — wzór zmiennych znajduje się w `.env.example` (`LOGI_API_KEY=`).

---

## 3. Żądanie HTTP

- **Metoda:** `POST`
- **URL:** wartość `logi.base_url` z konfiguracji (domyślnie `https://apilogi.com/demo/scan`)
- **Nagłówki:**
  - `x-api-key`: klucz API
  - `Content-Type`: `application/json`
- **Ciało (JSON):** zawsze pole `lang` (np. `en`) oraz **dokładnie jedno** z:
  - `prompt` — opis tekstowy posiłku, **lub**
  - `image_url` — adres obrazu do analizy

Logika „albo prompt, albo image_url” jest w `build_scan_payload()` w `src/logi_client.py`. Naruszenie tej reguły kończy się `ValidationError` przed wysłaniem żądania.

Klient HTTP w pipeline: **`httpx`** (`src/logi_client.py`).

---

## 4. Odpowiedź JSON — warstwa nadrzędna

Po stronie **vieo** odpowiedź jest walidowana modelem **`ScanResponse`** (`src/models/scan.py`):

| Pole (JSON z API) | Typ w modelu | Uwagi |
|-------------------|--------------|--------|
| `success` | `bool` | Wymagane; przy `false` pipeline rzuca `PipelineError` z treścią `raw` |
| `scanId` | `str` | Wymagane w modelu |
| `duration` | `int \| null` | Opcjonalne |
| `processing_mode` | `str \| null` | Opcjonalne (snake_case w modelu) |
| `data` | `object` | Słownik z polami posiłku — z niego budowany jest `MealScan` |

Pełna surowa odpowiedź jest zapisywana do pliku **`scan.json`** w katalogu danego uruchomienia pipeline (patrz sekcja 7).

---

## 5. Pole `data` → model `MealScan`

Z `ScanResponse.data` funkcja `MealScan.from_api_data()` odczytuje m.in.:

| Klucz w JSON (`data`) | Znaczenie w **vieo** |
|------------------------|----------------------|
| `mealName` | Nazwa posiłku (fallback: `"Meal"`) |
| `mealDescription` | Opcjonalny opis |
| `ingredients` | Lista obiektów składników |
| `potentialHealthRisks` | Lista ryzyk (API może zwrócić string, listę lub `null` — normalizacja w kodzie) |
| `nutritionistsOpinion` | Opinie dietetyczne — ta sama elastyczność typów |

### Składnik (`Ingredient`)

Oczekiwane pola w każdym elemencie `ingredients[]` (m.in.): `name`, `description`, `weight`, `category`, `nutritional_reference`, `nutritional_actual`, `match_confidence`, `thumbnail_url`.  
Wartości odżywcze są mapowane do **`NutritionValues`**: m.in. `calories`, `protein`, `fat`, `carbohydrates`, `saturated_fat`, `fiber`, `glycemic_index`, `glycemic_load`, `sugars` — przy czym **`sugars_total`** z API jest traktowane jak **`sugars`** (normalizacja w walidatorze).

Jeśli walidacja Pydantic dla wiersza się nie powiedzie, kod próbuje **uproszczonego fallbacku** (`_ingredient_fallback`); w skrajnych przypadkach wiersz może zostać pominięty (log ostrzeżenia, krok `logi`).

Po zbudowaniu listy składników **vieo** wymaga, aby była **niepusta** — w przeciwnym razie `PipelineError`.

---

## 6. Kody HTTP i zachowanie

Implementacja w `create_logi_scanner()` (`src/logi_client.py`):

| Sytuacja | Zachowanie |
|----------|-------------|
| Timeout `httpx` | Ostrzeżenie w logu, jeden retry (`LogiRetryableError`, tenacity) |
| Inny błąd transportu (`HTTPError`) | `PipelineError` (krok `logi`, kod 10) |
| **429** | `PipelineError` — limit zapytań (kod 11) |
| **400**, **401** | `PipelineError` (kod 10) |
| **502** | Ostrzeżenie, retry |
| Inne **5xx** (oprócz 502 bez retry sukcesu) | `PipelineError` |
| Inny status ≠ 200 | `PipelineError` |
| **200**, ale nie-JSON | `PipelineError` |
| **200**, `success: false` | `PipelineError` z surowym `raw` w komunikacie |

Maksymalnie **2 próby** skanera przy błędach uznanych za retryable (konfiguracja `@retry` w `logi_client.py`).

---

## 7. Gdzie w kodzie jest wywołanie

1. **`src/pipeline.py`** — `_load_or_scan()` buduje payload (`build_scan_payload`), tworzy skaner (`create_logi_scanner`) i zapisuje wynik pod `run_dir / "scan.json"`.
2. **`src/logi_client.py`** — faktyczne `POST`, parsowanie JSON, zapis `write_json`, walidacja `ScanResponse`, `to_meal_scan()`.
3. **`src/models/scan.py`** — `ScanResponse`, `MealScan`, `Ingredient`, `NutritionValues`, `NutritionTotals`.
4. **`test.py`** — uproszczony skrypt testowy z **`requests`** na ten sam domyślny URL demo; służy do ręcznego sprawdzenia klucza i odpowiedzi (nie jest główną ścieżką CLI pipeline).

---

## 8. Logowanie

- **Tekst:** logger z krokiem `logi` — m.in. `INFO` przed requestem (`"requesting LOGI scan"`), `WARNING` przy timeoucie i przy 502 przed retryem.
- **Pełna odpowiedź API:** nie jest domyślnie kopiowana do `run.log` w całości; **źródłem prawdy** jest plik **`artifacts/<timestamp>/scan.json`** (oraz ewentualnie komunikat wyjątku przy `success: false`).
- **Sekrety:** przy starcie pipeline lista wrażliwych stringów (w tym klucz LOGI) jest przekazywana do `configure_logging`, żeby ograniczyć ryzyko wycieku do pliku logów.

---

## 9. Cache / ponowne użycie skanu

Jeśli pipeline zostanie uruchomiony z opcją użycia zapisanego wcześniej `scan.json` (ścieżka przekazana jako cache), dane są wczytywane przez `load_cached_scan()` zamiast nowego `POST` — szczegóły w `src/logi_client.py` i `_load_or_scan()` w `src/pipeline.py`.

---

## 10. JSON Schema

Formalny opis ciała żądania (`POST` JSON) oraz odpowiedzi (sukces HTTP 200) leży w katalogu **`schemas/`**:

| Plik | Zawartość |
|------|-----------|
| [`schemas/logi-scan-request.schema.json`](schemas/logi-scan-request.schema.json) | `prompt` **xor** `image_url`, opcjonalnie `lang`; `additionalProperties: false`. |
| [`schemas/logi-scan-response.schema.json`](schemas/logi-scan-response.schema.json) | Korzeń: `success`, `scanId`, `duration`, `processing_mode`, `data` + definicje składnika i pól `data`. |
| [`schemas/logi-nutrition-values.schema.json`](schemas/logi-nutrition-values.schema.json) | Bloki `nutritional_reference` / `nutritional_actual` (w tym alias `sugars_total` jak w vieo). |

Walidacja: dowolny walidator **JSON Schema draft-07** (np. `check-jsonschema`, rozszerzenia w IDE). Schemat odpowiedzi opisuje typowy kształt sukcesu; przy `success: false` obiekt `data` może być ubogi — nadal może przejść część asercji, jeśli pola wymagane na korzeniu są obecne.

**Kluczy API nie umieszczaj w repozytorium** — tylko w `.env` / menedżerze sekretów. Jeśli klucz trafił do czatu lub commita, **unieważnij go u dostawcy** i wystaw nowy.

---

## 11. HTTP — kody odpowiedzi (endpoint demo)

| Status | Znaczenie |
|--------|-----------|
| **200** | Sukces — pełny JSON (analiza); przy błędzie biznesowym możliwe `success: false` w body. |
| **400** | Brak `prompt` i `image_url` (lub inny błąd walidacji żądania). |
| **401** | Brak lub nieprawidłowy nagłówek `x-api-key`. |
| **429** | Rate limit (np. **100 żądań / 15 min / IP** — wartość z dokumentacji wewnętrznej; zweryfikuj u dostawcy). |
| **502** | Pipeline AI nie zwrócił wyniku w oczekiwanym czasie / błąd bramy (vieo robi jeden retry). |

Inne **5xx** traktuj jako błąd serwera; szczegóły w `src/logi_client.py`.

---

## 12. Zastrzeżenie

URL `https://apilogi.com/demo/scan` i kształt pól JSON pochodzą z integracji w tym repozytorium. Limity, cennik, SLA i ewentualne inne endpointy **należy weryfikować u dostawcy LOGI**, jeśli używasz środowiska produkcyjnego lub innej wersji API niż ta zaszyta w `config.yaml`.
