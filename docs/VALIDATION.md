# Current validation: existing three-class document model

The user approved restoring the installed checkpoint and its labels: Human, AI-Generated, AI-Edited Human. This supersedes the previous binary-product validation record.

- Full backend suite with `LEXITRACE_TEST_REAL_MODEL=1`: **63 passed**, one dependency deprecation warning.
- The real-checkpoint test loaded existing local weights through `/api/ready`, verified `loaded=true`, then successfully called authenticated `POST /predict` using a temporary account database.
- The response contained three correctly named probabilities summing to approximately one, the selected class confidence, and `model_mode=model`.
- Frontend TypeScript/Vite production build: passed.
- Grouped splitting, transitive source grouping, empty/invalid/duplicate checks, 3x3 metrics, research access/report validation, PDF extraction and PostgreSQL failure/privacy tests passed.
- No model weights, existing account data or PostgreSQL data were overwritten. No sentence checkpoint is required. The frontend still displays trained-model results only.

Reproduce from the project root:

```powershell
$env:LEXITRACE_TEST_REAL_MODEL="1"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd frontend
npm.cmd run build
```

This verifies integration, not model accuracy. No suitable held-out labeled dataset or measured project benchmarks were supplied. Corrected-SRS details and Transformation Fingerprint remain pending; no evidence or scores are fabricated.


Latest prediction investigation: 68 backend tests passed with real-checkpoint tests enabled, and the TypeScript/Vite build passed. New regression tests cover matching training/evaluation/API whitespace preprocessing, evaluation checkpoint fingerprints, targeted confusion counts and text-free error CSV output. The exact reported 98.8% case and a real held-out evaluation remain unverified because the original text, intended checkpoint identity and data/results were not supplied. See PREDICTION_INVESTIGATION.md.
