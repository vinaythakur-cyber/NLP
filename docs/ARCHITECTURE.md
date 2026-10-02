# Architecture

One rule runs through the design: **the library does the work; everything else is a thin shell.**
The CLI, the API and the web page only translate between a user and `LinguaBridge`, so a fix made
once applies everywhere, and tests can skip the web server entirely.

```
            web/ (static UI)         cli.py (Typer)          api.py (FastAPI)
                  \                       |                       /
                   \______________________|______________________/
                                          v
                               engine.py  LinguaBridge
              ________________________/   |   \_______________________
             v                            v                           v
        detect.py                  convert/*                  translate/router.py
   (script + language)   (devanagari, hinglish, chinese)      /       |        \
                                                       indic.py     zh.py    nllb.py   opus.py
                                                    (IndicTrans2)  (NLLB,    (NLLB,   (Marian,
                                                                    zh only)  any)     en<->zh)
   foundation: languages.py · config.py · errors.py · schemas.py
```

Dependencies point downward only. A lower layer never imports an upper one.

## Modules

| Path | Responsibility |
|---|---|
| `languages.py` | One registry: user code `sa/hi/en/zh` to FLORES code, name, script. Aliases (`hin_Deva`, `Mandarin`). |
| `config.py` | Settings from `LB_*` environment variables or `.env`. Model ids per profile (`small`, `base`). |
| `errors.py` | Typed errors. The API maps them to HTTP statuses, the CLI to exit code 2 with a readable message. |
| `schemas.py` | pydantic contracts: `DetectionResult`, `ConversionResult`, `TranslationResult` (with the route), request bodies. |
| `detect.py` | Layer 1: script from Unicode ranges. Layer 2: language within the script (see below). Offline, deterministic. |
| `convert/devanagari.py` | Devanagari, IAST, Harvard-Kyoto, ITRANS (lossless among themselves) and casual Roman (one-way, lossy). |
| `convert/hinglish.py` | Roman Hindi to Devanagari behind a `HinglishBackend` protocol: rule-based (default) or ai4bharat (optional). |
| `convert/chinese.py` | Pinyin (pypinyin), Simplified and Traditional (OpenCC, with Taiwan and Hong Kong variants). |
| `translate/base.py` | `Translator` protocol, `ModelCache` (LRU, one lock), device/dtype resolution, `safe_generate`, load-error messages. |
| `translate/indic.py` | IndicTrans2 wrapper: lazy load, language tags and normalization via the processor, batching by length. |
| `translate/_indic_processor.py` | Pure-Python port of IndicTransToolkit's `IndicProcessor` (original is Cython with no Windows wheels). |
| `translate/nllb.py`, `zh.py`, `opus.py` | NLLB-200 (all pairs), NLLB restricted to Chinese pairs, Helsinki opus-mt for en/zh. |
| `translate/router.py` | Chooses direct or pivot per pair, applies overrides, falls back when a gated model is unavailable, logs the route. |
| `translate/_text.py` | Sentence splitting and rejoining (models are trained on sentences, not paragraphs). |
| `engine.py` | `LinguaBridge`: normalizes input, calls the router, post-processes output (Traditional Chinese on request). |
| `api.py`, `cli.py`, `doctor.py` | Shells: HTTP, command line, environment diagnosis. |

## Request flow: translate Sanskrit to Chinese

1. `POST /translate {"text": "...", "src": "sa", "tgt": "zh"}` is validated by `TranslateRequest`.
2. `engine.translate` checks the input length, resolves codes through `languages.py`, and runs detection (to learn the Latin scheme, or for `src=auto`).
3. `_normalize_source`: Latin-script Sanskrit (IAST, Harvard-Kyoto, else ITRANS) becomes Devanagari; romanized Hindi goes through the Hinglish engine; Traditional Chinese input becomes Simplified.
4. `split_text` breaks the text into sentences.
5. `Router.plan("sa", "zh")` returns two hops, `sa->en` (IndicTrans2) then `en->zh` (NLLB), because Sanskrit to Chinese is routed through English by default.
6. Each hop runs under the model cache lock. If an IndicTrans2 model is gated and unavailable, that hop falls back to NLLB and a warning is attached.
7. The route is logged (`route sa->zh via=pivot (PIVOT through English: errors can compound) hops=[...]`) and returned in `TranslationResult.route`.
8. Sentences are rejoined (no spaces for Chinese); Traditional output is produced with OpenCC if requested.

## Routing

| Pair | Default |
|---|---|
| sa/hi/en among themselves (6 pairs) | direct, IndicTrans2 (en-indic, indic-en or indic-indic model) |
| en to/from zh, hi to/from zh | direct, NLLB |
| sa to/from zh | **pivot through English**: IndicTrans2 for the Sanskrit hop, NLLB for the Chinese hop |

The Sanskrit-Chinese pivot is a hypothesis (NLLB's Sanskrit data is thin), not a measurement. Override per pair with
`LB_ROUTE_OVERRIDES`, for example `{"sa>zh": "direct", "en>zh": "opus"}`, and let `eval/run_eval.py --compare`
decide with real scores. `LB_TRANSLATION_ENGINE=nllb` sends everything to NLLB.

## Detection

* **Script**: share of characters per Unicode block (Devanagari U+0900-097F, Han, Kana, Latin). Under 70% for the top script means "mixed".
* **Chinese**: Simplified versus Traditional by counting characters that OpenCC would change in each direction.
* **Latin**: IAST diacritics, or Harvard-Kyoto mid-word capitals, mean romanized Sanskrit (then scored as Devanagari). Otherwise Hinglish versus English by common-word lists.
* **Devanagari, Hindi versus Sanskrit**: they share the script, so this is a scored guess. Evidence: Hindi function words, chandrabindu and nukta (Hindi); visarga, final `म्`, verb endings, Sanskrit particles (Sanskrit). The result carries both scores and `ambiguous=true` when they are close.

## Conversion fidelity

| Conversion | Reversible? |
|---|---|
| Devanagari, IAST, Harvard-Kyoto, ITRANS (any pair) | Yes for well-formed text; tests assert it on a corpus. Not for ill-formed input (a vowel sign with no consonant) or hiatus sequences like `कइ` (IAST `kai` reads as `कै`). |
| Devanagari to casual Roman | No: long vowels and retroflex letters collapse |
| Hinglish to Devanagari | No: spelling is not standardized, so the output is a prediction |
| Chinese to pinyin | No: homophones, context-dependent readings, optional tones |
| Simplified and Traditional | Not exactly: several traditional characters merged when simplified |

## Memory and concurrency

`ModelCache` keeps at most `LB_MAX_LOADED_MODELS` models in memory and evicts the least recently used one, because a 4 GB GPU cannot hold every model. A single lock serializes model loading and generation: one GPU does not serve concurrent requests faster, and it makes the code easy to reason about. `safe_generate` retries once without the KV cache (known cache-API mismatches in remote-code models) and once in float32 (half-precision overflow).

## Testing strategy

* **Fakes at the `Translator` boundary.** Router, engine, API and CLI tests inject `FakeTranslator`s that tag text with the hop that handled it, so no test downloads weights.
* **Golden tests** pin the processor port to outputs produced by the compiled original (`tests/data/make_golden.py` regenerates them).
* **Round-trip tests** state the lossless boundary of each conversion, including its known exceptions.
* **Tiny-model tests** (need torch) build a randomly initialised NLLB-shaped model and tokenizer on the fly to check batching, language tags and order restoration.
* **`@slow` real-model tests** run only with `LB_RUN_SLOW=1`.

## Extending

Add a model backend by implementing `Translator` (`supports`, `model_id`, `translate`), registering it in `LinguaBridge.__init__`, and naming it in `BACKEND_PREFERENCE` or an override. Add a language by extending `languages.py`, the backends' `supports` sets, and the detection rules.
