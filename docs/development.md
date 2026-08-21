# Development Guide

Target prototype date: 22 August 2026.

## Team Member 1 - ML

- Prepare datasets in `text,label` CSV format.
- Fine-tune DeBERTa-v3-base.
- Train RoBERTa-base baseline.
- Run evaluation and confusion matrix reporting.
- Improve `ml/inference/predict.py`.
- Replace the development AI contribution approximation with a trained estimator when available.

## Team Member 2 - NLP/Explainability

- Improve linguistic features in `backend/app/features/linguistic.py`.
- Add spaCy POS tagging and passive voice detection.
- Add real perplexity using a language model.
- Add SHAP and Captum/Integrated Gradients for trained models.
- Improve highlighted sentence and token evidence.

## Team Member 3 - Full Stack

- Maintain the React dashboard.
- Maintain FastAPI endpoints and schemas.
- Improve charts and visualization polish.
- Add integration tests.
- Package local development and Docker workflows.

## Local Workflow

Run the backend and frontend separately. Keep `LEXITRACE_MODE=development` until a fine-tuned model is available.
