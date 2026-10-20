# Requirements alignment and latest model decision

The user explicitly approved restoring the existing three-class checkpoint after the earlier requested binary-label alignment proved incompatible with its actual output head. The current product labels are **Human**, **AI-Generated**, and **AI-Edited Human**. This latest approval supersedes the earlier two-label code requirement. The weights/config are preserved and probabilities are not merged or relabeled.

The corrected SRS itself was not supplied, so full SRS compliance cannot be asserted. Anonymous-access policy, experiment-version definitions and Transformation Fingerprint still need its text. Login remains required by default, optional guest analysis is configurable, and research/evaluation is administrator-only.

The existing document model is connected without a separate sentence checkpoint. UI labels, shared preprocessing/training labels, API responses, evaluation metrics and research report schemas all use the same three classes. Group-disjoint data preparation, privacy-preserving optional PostgreSQL logging, PDF/text upload and the trained-model-only frontend remain.

Real inference verification confirms integration only. No suitable held-out labeled dataset or measured v0-v8 reports were provided, so project accuracy and benchmark claims remain unverified. Token attribution and Transformation Fingerprint are unavailable rather than fabricated. Seminar materials and existing user/database data were not changed.
