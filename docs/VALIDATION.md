# Delivery validation

Passed on Python 3.12 / Node 24:
- Backend pytest: 8 tests (health aliases, validation, three-class sentence pipeline, missing checkpoints return 503; password hashing, account routes, session revocation and protected access with a database test double).
- Frontend TypeScript and production Vite build.
- Live frontend page and text analysis through Vite proxy to the deliverable backend.
- Synthetic CSV fixture: 48/6/6 document split with no exact duplicate overlap. Fixtures were not used to train a detector.
- Backend dependency consistency check.

Not executed: full ML dependency installation, DeBERTa training/inference, Captum attribution on a real checkpoint, model evaluation on OpAI/LLMTrace, PostgreSQL inserts. No real datasets, trained weights or database were available. These capabilities require integration validation; no accuracy claim is made.

Sentence dataset exports require sentence annotations. Related sentence/source-document grouping is the user's responsibility with the current normalized CSV adapter.

The uploaded ZIP could not be extracted because it exceeded the file-transfer limit. This delivery is based on the GitHub checkout and your complete project-idea document.

Authentication PostgreSQL tables and queries are implemented but were not exercised against a live PostgreSQL service in this environment. No claim of live database integration validation is made.
