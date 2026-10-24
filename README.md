# LexiTrace

LexiTrace uses the existing **three-class document checkpoint** with labels **Human**, **AI-Generated**, and **AI-Edited Human**. This restores the trained model with the user's explicit approval and supersedes the earlier two-class configuration. Checkpoint weights and metadata have not been rewritten or merged.

The React/Vite frontend, FastAPI backend, SQLite accounts, optional PostgreSQL analysis logging, grouped data validation and protected research area are retained. There is no separate sentence-model requirement. The frontend displays trained-model predictions only and has no demo branding.

## Windows setup

From the extracted project root, using Python 3.12 and Node 20+:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
if (-not (Test-Path frontend/.env.local)) { Copy-Item frontend/.env.example frontend/.env.local }
cd frontend
npm.cmd ci
cd ..
```

Preserve existing private environment files. `backend/.env` loads automatically; shell environment variables take precedence. Set `LEXITRACE_DOCUMENT_MODEL=../ml/models/document` for the supplied checkpoint. Relative server-configured model, evaluation and report paths resolve from the backend directory. Model weights, credentials, datasets and account databases stay out of Git.

Backend terminal, from the project root:

```powershell
cd backend
$env:LEXITRACE_MODE="model"
$env:LEXITRACE_DOCUMENT_MODEL="../ml/models/document"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend terminal, from the project root:

```powershell
cd frontend
$env:LEXITRACE_API_TARGET="http://127.0.0.1:8000"
npm.cmd run dev
```

Open the Local URL printed by Vite. Keep both terminals running. The same-site proxy supports HttpOnly session cookies. Leave `VITE_API_BASE_URL` empty for local development. The proxy reads `LEXITRACE_API_TARGET`, or `LEXITRACE_BACKEND_PORT` when no explicit target exists.

Check health and actual weight loading:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/ready
```

Health reports liveness, active mode and checkpoint metadata. Readiness loads the real model and returns 503 with a useful message if files/dependencies are missing or incompatible. The first inference loads large weights and can take longer; the model is cached afterwards. Always use the project's `.venv` Python.

## Model contract

Expected checkpoint folder:

```text
ml/models/document/
  config.json
  model.safetensors (or pytorch_model.bin / standard shard index)
  tokenizer.json
  tokenizer_config.json
```

The config must declare DeBERTa-v3 (`model_type=deberta-v2`) with three output classes and exact label names Human, AI-Generated, AI-Edited Human. Any class-index order is supported by explicitly reordering probabilities from metadata. Incorrect labels, dimensions, incomplete weights or files are rejected; no untrained head is silently initialized. See `ml/model-config.example.json` for the label contract, not a replacement for trained weights.

Inference uses overlapping 512-token windows and averages their probabilities, so complete documents are processed. Backend-only heuristic mode remains for controlled automated tests; the frontend rejects non-model prediction responses. No real accuracy claim follows merely from a successful inference request.

## Accounts and dashboards

Sign up before logging in; no default accounts exist. Login verifies email, password and account type. Administrator login and signup additionally require a single-use six-digit email code before issuing a session. Codes expire after 10 minutes, allow five incorrect attempts, and can be replaced by signing in again after 60 seconds. Configure the `LEXITRACE_SMTP_*` settings in `backend/.env` using [backend/.env.example](backend/.env.example), then restart the backend; administrator sign-in is blocked if email delivery is unavailable. See [backend/README.md](backend/README.md) for the verification API. Passwords are PBKDF2-SHA256 hashes; opaque sessions last 24 hours with HttpOnly/SameSite=Strict cookies and logout revocation.

Administrator signup requires a privately configured `LEXITRACE_ADMIN_SIGNUP_CODE`. For HTTPS hosting, set `LEXITRACE_COOKIE_SECURE=true` and serve frontend/API from the same site. Accounts/sessions remain in SQLite at `backend/accounts.sqlite3`, configurable with `LEXITRACE_AUTH_DB`. Existing user data is not migrated or deleted.

The user dashboard contains the user's name, Logout, a text area, PDF/text upload, Analyze, and three confidence bars. The admin dashboard adds model/logging diagnostics and protected research tools. Login-required analysis is the default. `LEXITRACE_ALLOW_ANONYMOUS=true` enables guest prediction/extraction only; research routes always require an administrator.

The corrected SRS was not supplied. The latest user approval explicitly restores the existing three-class model. Other SRS-dependent policies and research definitions remain pending confirmation; seminar materials were not changed.

## Uploads and validation

At least **50 whitespace-separated words** are required. Shorter input returns **text too short**. Maximum default length is **20,000 characters**, including spaces and punctuation (roughly 3,000-4,000 English words). `LEXITRACE_MAX_TEXT_CHARS` controls the shared API/dashboard limit.

Upload PDFs or UTF-8 `.txt` files up to 5 MB. PDFs must be unlocked, at most 100 pages, and contain extractable text. Scanned PDFs require OCR outside this app. Extracted text fills the editable text area for review; short files can be loaded, but prediction still needs 50 words. Source files are not retained as application artifacts.

## PostgreSQL logging

Authentication remains SQLite. PostgreSQL is separate, optional analysis logging. Use your existing service/database, or create a new database/user without changing existing data:

```sql
CREATE USER lexitrace WITH PASSWORD '<choose-your-own-password>';
CREATE DATABASE lexitrace OWNER lexitrace;
```

Configure privately in `backend/.env`, with URL-encoded credentials:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:URL_ENCODED_PASSWORD@127.0.0.1:5432/lexitrace
```

On first successful logged analysis, `lexitrace_analysis` is created if absent. The existing schema is preserved. Stored fields include text hash, length, prediction, confidence, probabilities, mode and timestamp; the legacy evidence column stays empty. Full submitted text and sentence content are never stored. Unset or unavailable PostgreSQL disables logging without preventing predictions; errors report safe operation/exception context without credentials. Live connectivity requires an actual configured server and is separate from model readiness.

## Data preparation, training and evaluation

CSV inputs require `text,label` and `document_id` or `source_id`. Use exactly Human, AI-Generated, AI-Edited Human or numeric 0/1/2, respectively. Related variants must share globally consistent identifiers. Duplicate normalized text joins groups across files. Empty examples, invalid labels and conflicting duplicates are rejected; identical same-label examples are removed.

Preparation keeps entire connected original-document/source groups together, with approximate 80/10/10 splits containing all three classes. It fails if independent groups are insufficient. Import, training and evaluation recheck duplicate/group disjointness. Correct original identifiers and checkpoint training provenance remain the data provider's responsibility.

```powershell
.\.venv\Scripts\python.exe -m ml.preprocessing.prepare --opai C:/data/opai.csv --llmtrace C:/data/llmtrace.csv --output ml/data/processed/document
.\.venv\Scripts\python.exe -m ml.training.train --data ml/data/processed/document --output-dir ml/models/document-new
.\.venv\Scripts\python.exe -m ml.evaluation.evaluate --data ml/data/processed/document --model-dir ml/models/document --output ml/research-reports/v0.json
```

Use new empty output directories/files to preserve existing data and weights. Training downloads the base model. Evaluation uses the same complete-document windowing as the API and only predicts the held-out test split after validating all splits. It reports accuracy, macro precision/recall/F1 and a **3x3 confusion matrix** (rows=true, columns=predicted; order Human, AI-Generated, AI-Edited Human), sample count and test hash. No suitable real held-out dataset has been supplied, so no measured project accuracy or benchmark scores are claimed.

## API and explanations

- `GET /api/health` (also `/health`): process liveness and model metadata.
- `GET /api/ready` (also `/ready`): actual compatible model load; 503 if unavailable.
- `GET /api/capabilities`: labels, limits, formats and access policy.
- Auth endpoints: `/api/auth/signup`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`.
- `POST /api/documents/extract`: multipart `file`, returning extracted text/counts.
- `POST /predict` (also `/api/predict`): JSON `{"text":"at least 50 words..."}`; returns label, confidence, three confidences, model_mode, disclaimer, sentences and explanation_method.
- `POST /api/analyze` (also `/analyze`): document metadata, class probabilities, linguistic estimates, optional evidence and logging status.

Optional `LEXITRACE_SENTENCE_EVIDENCE=true` applies the document classifier to the first 20 sentence fragments and displays the returned evidence. This is a model signal, not proof or a separately validated sentence detector; no sentence checkpoint is needed. Captum token attribution is available separately on demand through `/api/explain`. No explanations are fabricated in backend test mode.

Administrator-only research:

- `GET /api/research/status`: model/database status, v0-v8 report availability and outstanding prerequisites.
- `POST /evaluate` (also `/api/evaluate`): evaluates server-configured `LEXITRACE_EVALUATION_DATA` using the current model. No caller-supplied filesystem paths are accepted; no report overwrites or text storage occur.
- `LEXITRACE_RESEARCH_DIR`: optional `v0.json` through `v8.json` measured reports from the evaluation CLI. Only reports with the current three-label/3x3 schema are accepted. Fair comparisons require matching test-data hashes. Older binary reports are intentionally invalid for this model.
- Transformation Fingerprint remains explicitly unavailable pending its corrected-SRS definition and suitable paired data. No benchmark or fingerprint results are invented.

## Verification and branch

```powershell
$env:LEXITRACE_TEST_REAL_MODEL="1"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd frontend
npm.cmd run build
```

The opt-in real-model test loads the existing weights, checks readiness, signs in against a temporary account database and exercises `POST /predict`. Ordinary tests default to explicit backend test mode or controlled model substitutes. Tests verify software behavior; measured model accuracy requires held-out labeled data.

Work remains on `feature/updated-lexitrace-project`. No merge or push to main was performed. This extracted directory had no local project history; a project-local feature repository was initialized without changing the unrelated home-directory main repository. Model weights, private environment files, account databases, processed data and local reports remain Git-ignored.


## Investigating high-score AI-Generated / AI-Edited Human confusion

See `docs/PREDICTION_INVESTIGATION.md` for the latest evidence, local checkpoint SHA-256 values, missing assets, and safe reproduction/evaluation commands. A short generated control was misclassified even when 256-token, 512-token and production scores matched; integration success does not establish accuracy.

Training tokenization and held-out evaluation now apply the same whitespace normalization as `/predict`. Evaluation JSON includes checkpoint fingerprints and `ai_generated_as_ai_edited_human_count`. Add `--errors-output NEW_FILE.csv` to record misclassified example hashes, group IDs, labels and scores without saving full text. Existing files and model weights are not overwritten.


## Captum token explanations

After a trained-model prediction, click **Explain with Captum** in either dashboard.
`POST /api/explain` (also `/explain`) accepts the same JSON `{"text":"..."}` and
uses the same account/guest access policy and input limits as prediction. It does not
store text or attributions. Install `ml/requirements.txt` in the project environment;
it includes Captum 0.8.0. Restart the backend after updating code/dependencies.

The endpoint uses Captum Integrated Gradients on word embeddings, targeting the
whole-document winning class with the checkpoint's actual class-index mapping.
It compares the first production-sized window (up to 512 tokens including special
tokens) against mask-token word embeddings, keeping special tokens and the
attention mask fixed. It uses 16 integration steps and one gradient sample per
internal batch to limit memory. Explanations run on demand and can be substantially
slower than predictions; one explanation runs at a time per server process.

The response includes signed raw token attributions, relative scores in [-1, 1],
character offsets into the returned normalized excerpt, the target label, document
confidence, first-window and baseline probabilities, convergence delta, scope and a
`partial` flag. Positive scores support the target class relative to the baseline;
negative scores oppose it. They are not probabilities or proof of authorship.
For a multi-window document, this explains only the first window, not the full
averaged prediction. The UI states this scope and highlights the excerpt. A numerical approximation warning is shown when the absolute convergence delta exceeds the larger of 0.05 and 10% of the input-to-baseline probability difference.
The convergence delta measures numerical approximation error; a small delta does
not establish explanation quality or classifier accuracy. Test mode never returns
fabricated attributions, and attribution failures do not affect normal predictions.
