# LexiTrace — Detect → Localize Evidence → Explain

React/TypeScript/Vite/Tailwind frontend; FastAPI backend; independent three-class DeBERTa-v3 document and sentence classifiers; Captum Layer Integrated Gradients; PostgreSQL logging. No Docker required.

## Quick start (Linux/macOS, Python 3.11 or 3.12, Node 20+)
From the extracted LexiTrace directory:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ../backend
LEXITRACE_MODE=demo ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```
In a second terminal:
```bash
cd LexiTrace/frontend
npm run dev
```
Open the frontend on port 5173. Vite forwards /api to port 8000. Do not set VITE_API_BASE_URL unless using a separate API host.

## Windows PowerShell
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ../backend
$env:LEXITRACE_MODE="demo"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
Second terminal: `cd LexiTrace/frontend`, then `npm run dev`.

## PostgreSQL (native installation, no container)
Install PostgreSQL 16+ using your operating system's installer and start its service. In psql as an administrator:
```sql
CREATE USER lexitrace WITH PASSWORD 'choose-your-own-password';
CREATE DATABASE lexitrace OWNER lexitrace;
```
Before starting the backend, export your connection string:
```bash
export DATABASE_URL='postgresql+psycopg://lexitrace:YOUR_URL_ENCODED_PASSWORD@localhost:5432/lexitrace'
```
PowerShell: `$env:DATABASE_URL="postgresql+psycopg://lexitrace:YOUR_URL_ENCODED_PASSWORD@localhost:5432/lexitrace"`.
The table is created on first analysis. Only a text hash, length, class scores, model mode, timestamp and compact sentence evidence are stored; full input text and large attribution arrays are not stored. If unset, logging is visibly disabled. Database failures are reported as unavailable in the response/UI. Do not commit credentials.

## Real models: data preparation, training and evaluation
Only OpAI and LLMTrace are supported sources. Neither data nor trained weights are bundled. Supply CSV exports with `text,label` columns. Labels must be 0/1/2 or Human-Written/AI-Generated/AI-Transformed. Map source-specific labels explicitly before import; the project does not invent source schemas or annotations.

Install ML dependencies from the repository root:
```bash
source .venv/bin/activate
python -m pip install -r ml/requirements.txt
python -m ml.preprocessing.prepare --opai /path/opai_documents.csv --llmtrace /path/llmtrace_documents.csv --component document --output ml/data/processed/document
python -m ml.preprocessing.prepare --opai /path/opai_sentences.csv --llmtrace /path/llmtrace_sentences.csv --component sentence --output ml/data/processed/sentence
python -m ml.training.train --data ml/data/processed/document --output-dir ml/models/document
python -m ml.training.train --data ml/data/processed/sentence --output-dir ml/models/sentence
python -m ml.evaluation.evaluate --data ml/data/processed/document --model-dir ml/models/document
python -m ml.evaluation.evaluate --data ml/data/processed/sentence --model-dir ml/models/sentence
```
Sentence rows need actual sentence annotations: a mixed document's label must not be copied to all its sentences. Each class needs at least 10 unique rows. Exact normalized duplicates are removed, conflicting labels are excluded, and stratified 80/10/10 splits are saved. For sentence exports, keep related source documents in one split before import; the current CSV adapter lacks document IDs and cannot prevent related-sentence leakage. Avoid training/evaluating related documents across the two components if reporting combined performance.

Training downloads microsoft/deberta-v3-base from Hugging Face. A GPU is recommended; CPU training is slow. Two checkpoints are loaded once per backend process, on CPU by default. Long documents use overlapping chunks; class probabilities are averaged over chunks. Sentence attribution is computed for the three strongest evidence sentences, up to 512 tokens per sentence, with 32 integration steps. Inspect convergence delta before relying on explanations. DeBERTa-v3 uses the Transformers `deberta-v2` architecture implementation.

Start the real model backend from backend:
```bash
LEXITRACE_MODE=model ../.venv/bin/python -m uvicorn app.main:app --port 8000
```
Override paths with LEXITRACE_DOCUMENT_MODEL and LEXITRACE_SENTENCE_MODEL. Missing checkpoints return 503 rather than pretending demo scores are model results.

## API and verification
GET /api/health and /health; POST /api/analyze and /analyze with `{"text":"Your document."}`. Returns three-class prediction, confidence, probabilities, sentence evidence, selected token scores, linguistic estimates, mode and logging status. Health is liveness, not proof models/database are ready. There is no /evaluate endpoint: evaluation remains a CLI as in the original project.
```bash
cd backend
../.venv/bin/python -m pytest -q
curl -X POST http://127.0.0.1:8000/api/analyze -H 'Content-Type: application/json' -d '{"text":"This is an example. Another sentence follows."}'
```
Demo mode runs immediately without ML weights or PostgreSQL. It is an untrained demonstration, not validated AI detection, and returns no fabricated Integrated Gradients scores. Linguistic measures are approximate heuristics. Real model accuracy requires evaluation on held-out OpAI/LLMTrace annotations.

See docs/AUDIT.md for the original repository audit and docs/VALIDATION.md for delivery checks and limitations.

## Accounts and document dashboard

The application now opens with User / Administrator login and signup. Passwords are hashed with PBKDF2-SHA256; opaque, revocable sessions are stored server-side and sent in HttpOnly, SameSite=Strict cookies. Sessions last 24 hours. Accounts persist in `backend/accounts.sqlite3` by default, independently of optional PostgreSQL analysis logging. Set `LEXITRACE_AUTH_DB` to change the location; keep this file private and back it up if accounts must survive machine changes.

User registration is open. Administrator registration requires the setup code configured on the backend before startup. In PowerShell:

```powershell
$env:LEXITRACE_ADMIN_SIGNUP_CODE="replace-with-a-long-random-secret"
```

Choose Administrator on the signup page and enter this code. Without the environment variable, administrator signup is disabled. Existing administrators can still log in. Both roles can analyze documents; administrators additionally see model/logging diagnostics. No account-management actions are currently provided. For HTTPS deployments, set `LEXITRACE_COOKIE_SECURE=true`. Serve the frontend and API through the same site for the strict session cookie; the Vite proxy handles local development.

The dashboard provides **document-level results**, with no sentence or word-level classifications displayed. Upload a text-based PDF or UTF-8 `.txt` document, or paste its contents. Text-based PDFs can be uploaded directly; Word files must first be converted to plain text or PDF. The exact default limit is **20,000 characters**, including spaces and punctuation: approximately **3,000-4,000 English words**, depending on word length. There is no separate fixed word limit. A live word/character counter and server-side validation enforce the displayed character limit. Configure it using `LEXITRACE_MAX_TEXT_CHARS`; `GET /api/capabilities` supplies the dashboard with that value.

`POST /api/analyze` and `/analyze` now require a signed-in session. Auth endpoints are `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`. Login accepts `email`, `password`, and `role` (`user` or `admin`); signup additionally accepts `name` and, for admins, `admin_code`. For scripted requests, use a cookie jar to retain the session. The underlying analysis response still includes sentence evidence for API compatibility; the dashboard displays only the document assessment. Demo-mode results are clearly marked as untrained heuristics.


The minimum input is **50 words**, enforced on the frontend and backend. Shorter input shows **text too short**. This is an input requirement, not a validated detection accuracy threshold.


### User dashboard prediction flow

The user dashboard has a navbar with the signed-in user's name and Logout, a paste-text area, and an Analyze button. Analyze calls authenticated `POST /predict` with `{"text":"..."}`. Vite proxies this endpoint to the configured backend alongside `/api`. `/api/predict` is also available. The response includes `label`, `confidence`, `confidences` (Human, AI-Generated, AI-Edited Human), `model_mode`, and `disclaimer`. The result card displays exactly these three confidence bars. Internal model labels remain unchanged; the prediction endpoint maps them to the user-facing names.

Both `/predict` and the existing `/analyze` endpoints require at least 50 whitespace-separated words and at most the configured character limit. Below 50 words, the API returns HTTP 422 with `{"detail":"text too short"}`. The admin dashboard retains its document upload and diagnostics; the user dashboard supports PDF/text uploads as well as pasted text.


PDF uploads are available on both dashboards. `POST /api/documents/extract` accepts an authenticated multipart upload with field `file`. It returns extracted text for review in the text area before analysis. Files must be `.pdf` or UTF-8 `.txt`, at most 5 MB; PDFs must be unlocked and at most 100 pages. Extracted text must fit the configured character limit. Scanned PDFs with no text layer require OCR outside this application. Short documents can be loaded for editing, but Analyze still requires at least 50 words. Uploaded source files are not retained as application artifacts.
