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
