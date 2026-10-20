# User sample investigation — 20 October 2026

The supplied seminar/explanation text has expected provenance label **AI-Generated**, as stated by the user. Direct inference using the project's current checkpoint reproduces a wrong classification. The source text is not saved in this report. Blank-line layout was simplified before the same whitespace normalization used by the API; Unicode punctuation was preserved through verified UTF-8 transfer. The final instruction stating the expected answer was excluded.

## Measured results

The sample contains 2,013 whitespace-separated words and 2,860 tokenizer tokens. It is within the API's 20,000-character limit. Production creates seven overlapping windows.

| Inference | Human | AI-Generated | AI-Edited Human | Prediction |
|---|---:|---:|---:|---|
| Production: mean of overlapping 512-token window probabilities | 54.70% | 0.13% | 45.17% | Human |
| First 256 tokens | 27.08% | 0.20% | 72.73% | AI-Edited Human |
| First 512 tokens | 38.75% | 0.19% | 61.05% | AI-Edited Human |

Raw measurements and checkpoint fingerprints are in `sample-diagnostic-2026-10-20.json`. An initial ASCII-transfer run was discarded; percentages above use the subsequent Unicode-preserving run.

## What this establishes

- The error reproduces by invoking the model service directly, bypassing the frontend, authentication and response display.
- Runtime and saved configuration map 0=Human, 1=AI-Generated, 2=AI-Edited Human. Canonical output indices are [0, 1, 2]. This checks implementation and metadata, not the original training dataset's numeric-label meanings.
- The model is in evaluation mode. The same checkpoint SHA-256 values match the earlier investigation.
- Window averaging changes the winning label on this input. However, truncating to either 256 or 512 tokens still fails to select the expected class. Changing sequence length alone does not fix this example.
- The first-256 scores are unchanged by production whitespace normalization for this copied sample. Other preprocessing and original training settings remain unverified.

## Original training provenance is incomplete

Static `pickletools` inspection of `training_args.bin` (without unpickling/executing it) found an output directory ending in `LexiTrace/models/editlens_checkpointed`, learning rate 1e-5, training batch size 2, three epochs, evaluation batch size 4, and best-model metric `eval_macro_f1`.

The checked-in `ml/training/train.py` instead defaults to learning rate 2e-5 and batch size 8. It cannot be assumed to reproduce the original checkpoint's training run. Training arguments do not supply its original tokenization length, actual evaluation scores, or dataset labels.

The checkpoint config records Transformers 5.18.0, while the installed environment has Transformers 4.55.0, tokenizers 0.21.4 and Torch 2.8.0. This environment difference is a reproduction variable, not a demonstrated cause; no dependency changes were made.

All files under the current `ml` directory were inventoried, including ignored/hidden files. No original notebook, test CSV, `trainer_state.json`, classification report or saved measured 85% evaluation was found. The adjacent `LexiTrace-github/ml` copy also has no such records. The 75% confusion matrix in the submitted text explicitly describes an illustrative example and is not a model evaluation.

## Remaining explanation and next diagnostic step

This is confirmed misclassification by the current checkpoint/inference combination. It does not identify whether the deeper cause is mismatched exported weights/tokenizer, original dataset-label meaning, a difference from original evaluation preprocessing/environment, or poor generalization to this type of text. One example cannot determine overall accuracy or distinguish these causes.

Obtain the original training notebook, exported checkpoint identity and evaluation data/results. Run this same text in that original environment, then evaluate the same held-out examples in both environments. Matching wrong results implicate checkpoint generalization; different results require comparing export identity, tokenizer/preprocessing and runtime. Audit actual labels, class recalls and related-document overlap before deciding on retraining.

No source code, weights, label mapping, thresholds, dependencies or account data were changed. Only this report and the text-free diagnostic JSON were added.
