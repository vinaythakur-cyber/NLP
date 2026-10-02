# Evaluation results

**No results yet.** This file is overwritten by `eval/run_eval.py`; it never contains hand-typed
numbers. To generate real scores:

```bash
python eval/fetch_data.py                 # one-time, ~25 MB, FLORES-200
python eval/run_eval.py --limit 100       # quick check of all 12 pairs (minutes on a GPU)
python eval/run_eval.py --compare         # also try alternative models/routes per pair
python eval/run_eval.py                   # full 1,012-sentence devtest
```

IndicTrans2 runs require Hugging Face access to the gated IndicTrans2 repos (see README); the
evaluation is strict and will stop with a clear message instead of silently using another model.
