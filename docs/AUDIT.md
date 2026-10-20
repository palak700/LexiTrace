# Original repository audit
1. Folders: frontend/, backend/, ml/, data/, docs/.
2. Frontend: single React Dashboard, Vite API proxy, charts, metric cards and sentence highlighting.
3. Backend: FastAPI routes -> analysis service -> heuristic predictor, linguistic features and heuristic evidence.
4. ML: preprocessing/dataset.py, training/train.py, evaluation/evaluate.py, inference/predict.py and contribution/estimator.py.
5. Dataset loading: generic CSV, random 80/10/10 split, no source-specific import.
6. OpAI: absent.
7. LLMTrace: absent.
8. Document model: optional single four-label Transformers checkpoint; fallback heuristics.
9. Sentence model: absent.
10. Captum: absent; documentation only mentioned future explanations.
11. PostgreSQL: optional container declaration only, no schema or logging implementation.
12. API: GET /api/health and POST /api/analyze. Evaluation CLI only.
13. Missing: source preparation, three-label consistency, separate sentence model, Integrated Gradients, logging.
14. Outdated references: original README.md:126 and ml/data/README.md:20 mention unsupported dataset additions; README.md:152,157 and docs/development.md:19 mention SHAP. No OpAI-Bench versions were found.
15. Deliverable: retain folder layout and /api compatibility, implement explicit CSV preparation, independent document/sentence checkpoints, sentence-model token explanations and compact PostgreSQL logging. Provide demo mode without misrepresenting trained-model readiness.

The deliverable was built separately; the original Git checkout was left unchanged. Data formats for the actual OpAI and LLMTrace sources were not provided, so adapters accept normalized user exports rather than claiming to support undocumented schemas.
