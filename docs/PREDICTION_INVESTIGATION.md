# Prediction investigation: high AI-Edited Human score for known generated text

## Conclusion

The reported 0.988146 score cannot yet be reproduced because the exact input, the intended `editlens_document_best` files, and the original held-out data/results were not supplied. This investigation does **not** claim the model-quality problem is fixed.

Confirmed facts in this checkout:

- Branch: `feature/updated-lexitrace-project`.
- The live backend reports real model mode and configures a directory named `document`. The resolved default is `ml/models/document`; there is no backend `.env` and no `editlens_document_best` folder or suitable data/results under the project. Targeted checks of the named Downloads folder/files did not find the intended checkpoint or evaluation dataset.
- `document` might be a renamed copy of `editlens_document_best`, but folder names and matching label metadata do not prove identity. Compare hashes below against the intended saved checkpoint.
- Config/runtime mapping is 0=Human, 1=AI-Generated, 2=AI-Edited Human. The loader validates config labels and reorders scores by their actual IDs; it does not override them or merge classes. No frontend label swap was found.
- The supplied checkpoint architecture has `max_position_embeddings=512`. Current production uses all-document 512-token windows with a 64-token overlap, softmax per window, then an arithmetic average of probabilities.
- Local training code uses the same label contract and tokenizer associated with its selected base checkpoint, but trains on first-512-token passages. The user-supplied Colab notes use first-256-token inference. Neither establishes the original saved model's actual training sequence length; the training notebook/run metadata is needed. `training_args.bin` was not unpickled.

## Concrete bugs fixed

Evaluation previously passed raw CSV text into the classifier, while `/predict` collapses Unicode whitespace and strips it. Training tokenization also accepted raw whitespace from externally prepared CSVs. Both now call the same `normalize_text` as the API. Existing prepared data is usually already normalized, so this bug may have no effect on that data. It has **not** been shown to cause the reported 98.8% error.

Evaluation reports also lacked checkpoint identity. New reports record SHA-256 fingerprints, normalization policy, the targeted AI-Generated-to-AI-Edited-Human count, and an optional text-free misclassification CSV. This allows evaluation/app checkpoint comparisons without inventing or relabeling results. Existing output files are not overwritten.

Normal prediction policy, thresholds, class labels, checkpoint weights, tokenizer exports, account data and database data were not changed. No retraining was run.

## Reproduced integration checks

Authenticated `/predict` and `/diagnose` were called with real weights and a temporary admin account database. These controls are diagnostic inputs, not a held-out accuracy benchmark.

| Control | Tokens | Production result | First 256 tokens | Finding |
|---|---:|---|---|---|
| Fully generated programming-style paragraph | 58 | AI-Edited Human, 86.430633% | Identical probabilities | A genuine checkpoint misclassification on this control; no truncation or normalization effect |
| Repeated word control | 652 | AI-Edited Human, 40.159222% | Human, 38.144150% | Long-input policies can change the decision; this control has no meaningful authorship ground truth |

For the long control, production created two windows, each no longer than 512 tokens. The 256 and 512 single-window comparisons correctly reported truncation. Production and diagnostic probabilities matched exactly for both controls. No missing-token, score-index or frontend transport error was found in these checks. Neither control reproduces the user's exact 98.8% case.

The model runs in eval/inference mode. Scores come directly from softmax logits; high softmax scores are not calibrated accuracy estimates.

## Loaded local file fingerprints

```text
config.json           2cf7710f0581cffb2ae2effbd206d17371c0822d0577b0fed6a959c92a0f0155
model.safetensors     96ade988d4240cbd0d98264d6b80df04aa61e641e5d53ddd96ce41957b890c01
tokenizer.json        40b244adff13af033491ed93e56c53ecfc9c652cde898ac62c09eebcad940f34
tokenizer_config.json 0dbe41323167ba5f2e1e876ccd05068318dd2378b922bdfd924a389dba3bcc7a
```

If `editlens_document_best` has different hashes, the application and reported evaluation are using different artifacts. If the hashes match, the different directory name is only a renamed copy. Tokenizer hashes matter as well as the weights.

## Evidence still needed

1. Exact text that produced Human=.008984, AI-Generated=.002870, AI-Edited Human=.988146 and its known provenance; include extracted text if the input came from PDF.
2. Full local path or hashes of the intended `editlens_document_best` export.
3. Original saved evaluation JSON/CSV, row-level predictions, training/validation/test CSVs, original-document/source IDs and the training notebook's preprocessing/sequence-length settings.

Without these, incorrect dataset labels, train/test leakage, checkpoint identity and the claimed EditLens/Llama confusion counts cannot be independently verified. No suitable held-out data or measured result files exist in this checkout.

## Safe exact next steps

From the project root, first identify your actual checkpoint (the prompt requests your existing folder; it does not download, copy or change weights):

```powershell
$checkpoint = (Resolve-Path (Read-Host 'Full path to editlens_document_best')).Path
Get-FileHash (Join-Path $checkpoint 'model.safetensors') -Algorithm SHA256
Get-FileHash (Join-Path $checkpoint 'tokenizer.json') -Algorithm SHA256
```

Compare all four hashes via the admin Research panel's **Diagnose current text** output. Stop the existing backend with Ctrl+C, then explicitly select the intended folder before restarting:

```powershell
$env:LEXITRACE_MODE='model'
$env:LEXITRACE_DOCUMENT_MODEL=$checkpoint
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Paste the exact failing input in the admin dashboard and use **Diagnose current text**. Compare production, first-256, first-512 and original-vs-normalized scores. Do not select a policy merely because it changes this one answer.

Prepare trustworthy grouped `train.csv`, `validation.csv`, `test.csv` files, with all three labels and a `group_id`. Use real original-document/source IDs; do not assign fabricated independent IDs to variants. The evaluation CLI rejects known group/text leakage and invalid data.

Run a fresh baseline evaluation, without modifying weights:

```powershell
$data = (Resolve-Path (Read-Host 'Folder containing grouped train.csv, validation.csv and test.csv')).Path
$runId = [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -m ml.evaluation.evaluate --data $data --model-dir $checkpoint --output "ml/research-reports/baseline-$runId.json" --errors-output "ml/research-reports/errors-$runId.csv"
```

The JSON contains measured metrics, 3x3 confusion matrix, checkpoint hashes and the targeted confusion count. The optional CSV contains misclassified example hashes/group IDs, true/predicted labels and class scores, with **no full text**. Match hashes back to the private source dataset for label/provenance review.

If mapping/checkpoint/preprocessing agree but errors persist, compare first-256 and windowed settings on an independent validation set, using the original training notebook to identify its actual settings. Choose settings using validation data, then evaluate once on the untouched test set. Do not tune on the test set or the single reported paragraph.

Only after auditing labels, duplicates/grouping and class balance should you consider a new training run. Include well-provenanced fully generated vs edited-human examples from multiple generators/topics. If measured imbalance warrants it, assess class weighting or balanced sampling using validation macro-F1 and class recalls. Keep the existing checkpoint intact and write any approved new run to a new folder:

```powershell
# Optional manual step only AFTER dataset audit and a training decision; not executed here.
.\.venv\Scripts\python.exe -m ml.training.train --data $data --output-dir "ml/models/retrained-$runId"
```

The training command refuses to overwrite a nonempty checkpoint folder. Preserve the baseline and compare both models on the same unchanged held-out test set. Consider calibration only using validation data; do not reinterpret a 98.8% score as 98.8% accuracy.

## Files changed in this investigation

- `backend/app/services/pipeline.py`: safe checkpoint directory name in health/readiness status.
- `ml/preprocessing/dataset.py`: training tokenization uses production whitespace normalization.
- `ml/evaluation/evaluate.py`: matching preprocessing, checkpoint provenance, targeted error counts and optional no-text error CSV.
- `backend/tests/test_integrity.py`: focused normalization/provenance/error-audit regression tests.
- README, validation record and this investigation report: current findings and reproducible commands.

The diagnostic API/panel and model-score wording already existed at the start of this investigation; no additional frontend logic change was needed.

## Verification

- Backend with `LEXITRACE_TEST_REAL_MODEL=1`: **68 tests passed**, one dependency deprecation warning.
- Frontend `npm.cmd run build`: TypeScript/Vite production build passed.
- Real API controls: production scores exactly matched diagnostic production scores.
- No actual held-out model evaluation was possible without data. Test-fixture accuracy values verify metric code only and are not project benchmark results.
