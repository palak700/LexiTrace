# Current update: restored existing trained model

The user approved restoring the installed three-class document model. This supersedes the prior binary-label implementation described in the historical report below. Current labels: Human, AI-Generated, AI-Edited Human. Backend/ frontend/training/preprocessing/evaluation and report validation now use three classes and 3x3 confusion matrices. Existing model files were not changed. Sentence-model dependencies remain removed and the frontend continues to reject backend test-mode scores.

Current run commands and contracts are in README.md. Existing grouped-split, database privacy/failure, authentication, upload and protected research behavior is retained. A compatible binary checkpoint is no longer required to use the installed model. Held-out accuracy remains unmeasured.

---

# Historical binary-alignment report (superseded by the latest user approval)

# Implementation report

## Branch and baseline

Active branch: `feature/updated-lexitrace-project`. The extracted project had no local `.git` directory or development history. The only parent Git root was the home folder, on an unborn `main` with no local branches. A project-local repository was initialized directly on the requested feature branch. No parent-branch change, source commit, merge or push was performed. Existing model files, SQLite data and private environment files were preserved.

## Files changed

- `.gitignore`: exclude private CSV datasets and local research reports alongside existing weights/databases/environment rules.
- `README.md`: current labels, limitations, safe Windows setup, PostgreSQL, model contract, grouped preparation, evaluation, API changes and exact run commands.
- `backend/.env.example`: safe binary-model, backend port, access-policy, explanation, evaluation and report configuration.
- `backend/app/core/labels.py` (new): shared Human/AI-transformed label contract.
- `backend/app/core/config.py`: private dotenv loading, environment precedence and portable configured paths.
- `backend/app/services/pipeline.py`: binary checkpoint validation, explicit rejection of incompatible output classes/dimensions, readiness status, local weights, optional sentence-fragment signals, no fake demo explanations.
- `backend/app/services/logging_service.py`: nonfatal PostgreSQL engine/connection/insert failures, credential-safe context logging, no text persistence, existing schema preserved.
- `backend/app/api/auth.py`: conditional anonymous-analysis dependency and explicit administrator-only dependency; existing accounts/sessions retained.
- `backend/app/api/routes.py`: binary responses, explanation fields, richer health, real readiness endpoint, configurable access for prediction and extraction, safe analysis errors.
- `backend/app/api/research.py` (new): protected research status and evaluation, validated v0-v8 reports, explicit missing prerequisites.
- `backend/app/main.py`: protected research routes and shared ML-module imports.
- `backend/tests/test_api.py`: updated binary/API tests, incompatible original-checkpoint check, access boundaries, demo/explanation behavior, research evaluation/report checks.
- `backend/tests/test_integrity.py` (new): grouped preparation, transitive source links, empty/label/duplicate validation, leakage detection, metrics, checkpoint files, PostgreSQL failure/privacy checks and held-out inference behavior.
- `frontend/.env.example`, `frontend/vite.config.ts`: same-site cookies and environment-configured proxy target/port.
- `frontend/src/types/analysis.ts`, `frontend/src/services/api.ts`: binary labels, optional evidence and configurable anonymous-access capability.
- `frontend/src/App.tsx`: optional guest analysis with protected sign-in/admin flows.
- `frontend/src/pages/AuthPage.tsx`, `UserDashboard.tsx`, `Dashboard.tsx`: consistent labels, evidence rendering, guest controls and admin research panel; document upload workflow retained.
- `frontend/src/components/EvidencePanel.tsx` (new): honest optional sentence model signals without fabricated token attribution.
- `frontend/src/components/ResearchPanel.tsx` (new): protected model/database status, actual held-out evaluation, version reports and explicit unavailable fingerprint.
- `frontend/src/styles.css`: small supporting styles for evidence/research/guest views.
- `ml/model-config.example.json` (new): binary output-label contract only; not trained weights.
- `ml/preprocessing/prepare.py`, `dataset.py`: original-document/source connected-group splits, duplicate checks and import validation; preserve existing output files.
- `ml/training/train.py`: shared binary label head, group-validated input, refuse existing checkpoint overwrite.
- `ml/evaluation/metrics.py`, `evaluate.py`: binary metrics and 2x2 confusion matrix, held-out document-window inference, optional reproducible JSON report, no overwrite.
- `backend/README.md`, `frontend/README.md`, `ml/README.md`, `ml/data/README.md`, `docs/architecture.md`, `docs/development.md`, `docs/api.md`: remove stale three-class setup pointers.
- `docs/SRS_ALIGNMENT.md`, `docs/VALIDATION.md`, this report: requirement gaps and verification record.

Separate seminar materials and the historical `docs/AUDIT.md` were not modified.

## Intentional API changes

Both `/predict` and `/api/predict` now return only Human/AI-transformed confidence keys. `/analyze` aliases use the same binary keys. Responses additionally include an empty `sentences` array when evidence is unavailable, plus an explanation-method message. All frontend callers were updated. `/health` retains `status=ok` for process liveness and adds real/demo configuration metadata; `/ready` performs model loading and returns 503 if not ready.

Login remains required by default pending the corrected SRS. Optional anonymous mode affects prediction and extraction only. `/research/status` and `/evaluate` remain administrator-only regardless of anonymous mode. Existing auth endpoints, PDF/text uploads and size/word validation remain.

## Verification commands and results

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Result: 61 passed, with one pre-existing dependency deprecation warning. Tests use explicit demo mode and controlled model substitutes, plus real metadata checks rejecting the supplied incompatible checkpoint. They do not measure real prediction accuracy.

From `frontend`:

```powershell
npm.cmd run build
```

Result: TypeScript and Vite production build passed. There is no separate lint command configured in package.json.

From the project root:

```powershell
.\.venv\Scripts\python.exe -m ml.preprocessing.prepare --help
.\.venv\Scripts\python.exe -m ml.evaluation.evaluate --help
.\.venv\Scripts\python.exe -m pip check
```

Results: both CLI entry points passed; no broken installed requirements.

Git checks confirmed the active feature branch and exclusion of account databases, private environment files, checkpoint weights/config and processed data. No PostgreSQL table deletion, migration, user-data overwrite or model-weight modification occurred.

## Missing assets and limits

- Corrected SRS was requested but not supplied. Its access policy, v0-v8 definitions and fingerprint behavior cannot be asserted.
- Existing checkpoint: `ml/models/document/config.json` defines three classes, not two. It remains unchanged and is intentionally rejected. A compatible trained binary checkpoint is required for real product predictions.
- No suitable grouped held-out dataset was supplied. Evaluation code is tested, but no real accuracy/precision/recall/F1 results exist for this binary product.
- No measured v0-v8 reports or paired Transformation Fingerprint data/definition were supplied. The research UI reports unavailable rather than inventing values.
- Actual PostgreSQL connectivity was not verified with a configured server in this change. Failure handling and data privacy were tested with controlled substitutes.
- Sentence signals are optional document-classifier probes, not a separately validated sentence detector. Token attribution is not implemented for this unverified checkpoint/dependency combination.

## Run with compatible trained weights

From the project root, backend terminal:

```powershell
cd backend
$env:LEXITRACE_MODE="model"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

From the project root, frontend terminal:

```powershell
cd frontend
$env:LEXITRACE_BACKEND_PORT="8000"
npm.cmd run dev
```

Open the Local URL printed by Vite. An explicit existing LEXITRACE_API_TARGET overrides the port; adjust your private frontend environment if it points elsewhere. The frontend now accepts only trained-model predictions and has no demo banners or badges. Provide compatible binary weights through backend/.env, restart in model mode and check `/api/ready`; the existing incompatible checkpoint produces a clear unavailable-model error. Complete dependency/configuration/PostgreSQL commands are in README.md.

Frontend presentation update: removed demo badges, notices and CSS; both frontend prediction callers now reject non-model responses. TypeScript/Vite production build passed after this change. Backend test-only heuristics remain available to automated tests.
