"""Three-class document classifier. Incompatible checkpoints fail closed."""
import json
import hashlib
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
try:
    from app.core.config import settings, document_model_path
    from app.core.labels import LABELS, checkpoint_indices
except ModuleNotFoundError:
    from backend.app.core.config import settings, document_model_path
    from backend.app.core.labels import LABELS, checkpoint_indices

logger = logging.getLogger(__name__)
load_lock = Lock()
_loaded_path = None

class ModelUnavailable(RuntimeError):
    pass


def canonical_label_indices(labels):
    try:
        return checkpoint_indices(labels)
    except ValueError as exc:
        raise ModelUnavailable(str(exc)) from exc


def inspect_checkpoint(path):
    root = Path(path)
    if not root.is_dir():
        raise ModelUnavailable('Document model folder is missing. Set LEXITRACE_DOCUMENT_MODEL.')
    config_path = root / 'config.json'
    if not config_path.is_file():
        raise ModelUnavailable('Document checkpoint is missing config.json.')
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
        mapping = config.get('id2label', {})
        labels = [mapping[str(i)] for i in range(len(mapping))]
        indices = canonical_label_indices(labels)
        if config.get('num_labels', len(mapping)) != len(LABELS):
            raise ModelUnavailable('Checkpoint output dimension must be 3, matching Human, AI-Generated, and AI-Edited Human.')
        if config.get('model_type') != 'deberta-v2':
            raise ModelUnavailable('Document model must be a three-class DeBERTa-v3 checkpoint.')
    except ModelUnavailable:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ModelUnavailable('Document checkpoint config.json is invalid.') from exc
    if not any((root / name).is_file() for name in ('model.safetensors', 'pytorch_model.bin', 'model.safetensors.index.json', 'pytorch_model.bin.index.json')):
        raise ModelUnavailable('Document checkpoint has no model weights.')
    if not (root / 'tokenizer.json').is_file() or not (root / 'tokenizer_config.json').is_file():
        raise ModelUnavailable('Document checkpoint is missing tokenizer.json or tokenizer_config.json.')
    return labels, indices


class DocumentClassifierService:
    def __init__(self, path):
        labels, self.label_indices = inspect_checkpoint(path)
        try:
            from app.services.prediction_diagnostics import checkpoint_signature
        except ModuleNotFoundError:
            from backend.app.services.prediction_diagnostics import checkpoint_signature
        self.checkpoint_directory=Path(path).resolve()
        self.checkpoint_signature=checkpoint_signature(self.checkpoint_directory)
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            self.torch = torch
            self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, use_fast=True, extra_special_tokens={})
            self.model, info = AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True, output_loading_info=True)
            if self.model.config.num_labels != len(LABELS) or info['missing_keys'] or info.get('mismatched_keys'):
                raise ModelUnavailable('Checkpoint weights do not match the three-class classifier; retrain or export a compatible model.')
            self.model.eval()
            if checkpoint_signature(self.checkpoint_directory)!=self.checkpoint_signature:
                raise ModelUnavailable('Checkpoint files changed during model loading. Restart with a stable checkpoint folder.')
        except ModelUnavailable:
            raise
        except ModuleNotFoundError as exc:
            logger.error('Document model dependency missing (%s). Install ml/requirements.txt.', exc.name)
            raise ModelUnavailable(f'Missing ML dependency {exc.name}; install ml/requirements.txt.') from exc
        except Exception as exc:
            logger.error('Document model loading failed (%s). Check checkpoint files and ML dependencies.', type(exc).__name__)
            raise ModelUnavailable('Unable to load document model. Check local checkpoint files and installed ML dependencies.') from exc

    def predict(self, text):
        batches = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512,
                                 stride=64, return_overflowing_tokens=True, padding=True)
        batches.pop('overflow_to_sample_mapping', None)
        with self.torch.inference_mode():
            scores = []
            for start in range(0, len(batches['input_ids']), 4):
                logits = self.model(**{key: value[start:start+4] for key, value in batches.items()}).logits
                scores.append(logits.softmax(-1))
            probabilities = self.torch.cat(scores).mean(0).tolist()
        return [probabilities[index] for index in self.label_indices]


@lru_cache(maxsize=1)
def document_model(path):
    global _loaded_path
    classifier = DocumentClassifierService(path)
    _loaded_path = str(Path(path).resolve())
    return classifier


def current_mode():
    return os.getenv('LEXITRACE_MODE', settings.mode)


def model_status(load=True):
    mode = current_mode()
    status = {'mode': mode, 'loaded': False, 'ready': False, 'labels': LABELS, 'analysis_level': 'document'}
    if mode == 'demo':
        return {**status, 'ready': True, 'status': 'demo', 'message': 'Untrained demonstration only; no real model is loaded.'}
    if mode != 'model':
        return {**status, 'status': 'unavailable', 'message': 'Set LEXITRACE_MODE to model or demo.'}
    try:
        path = document_model_path()
        status['checkpoint_directory_name'] = Path(path).name
        inspect_checkpoint(path)
        if load:
            with load_lock:
                document_model(path)
        is_loaded = load or _loaded_path == str(Path(path).resolve())
        return {**status, 'loaded': is_loaded, 'ready': is_loaded, 'status': 'ready' if is_loaded else 'not_loaded', 'message': 'Document model loaded.' if is_loaded else 'Checkpoint metadata validated; weights not loaded.'}
    except ModelUnavailable as exc:
        return {**status, 'status': 'unavailable', 'message': str(exc)}


def demo_predict(text):
    terms = len(re.findall(r'\b(comprehensive|furthermore|moreover|optimize|streamline|efficiency)\b', text.lower()))
    raw = np.array([1.5, 0.7+terms*.25, 0.8+terms*.15])
    return (raw/raw.sum()).tolist()


def sentence_evidence(text, classifier):
    # Optional use of the document classifier on sentence fragments, not a separate trained sentence detector.
    evidence = []
    for match in re.finditer(r'[^.!?]+(?:[.!?]+|$)', text):
        content = match.group().strip()
        if not content or not any(char.isalnum() for char in content):
            continue
        leading = len(match.group()) - len(match.group().lstrip())
        probabilities = classifier.predict(content)
        target = int(np.argmax(probabilities))
        start = match.start() + leading
        evidence.append({'sentence': content, 'start': start, 'end': start+len(content), 'prediction': LABELS[target],
                         'score': probabilities[target], 'class_probabilities': dict(zip(LABELS, probabilities)), 'tokens': []})
        if len(evidence) >= 20:
            break
    return evidence


def normalize_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def analyze(text):
    from app.features.linguistic import analyze_linguistic_features
    from app.services.logging_service import LoggingService
    text = normalize_text(text)
    mode = current_mode()
    if mode not in ('demo', 'model'):
        raise ModelUnavailable('LEXITRACE_MODE must be demo or model.')
    classifier = None
    if mode == 'model':
        with load_lock:
            classifier = document_model(document_model_path())
    probabilities = classifier.predict(text) if classifier else demo_predict(text)
    version = 'demo-untrained' if not classifier else 'Unavailable'
    if classifier and hasattr(classifier, 'checkpoint_signature'):
        from app.services.prediction_diagnostics import checkpoint_signature, file_fingerprints
        root = classifier.checkpoint_directory
        if checkpoint_signature(root) != classifier.checkpoint_signature:
            raise ModelUnavailable('Checkpoint files changed. Restart the backend before analyzing.')
        fingerprints = file_fingerprints(str(root), classifier.checkpoint_signature)
        version = 'sha256:' + hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()
        if checkpoint_signature(root) != classifier.checkpoint_signature:
            raise ModelUnavailable('Checkpoint files changed while identifying the model. Restart the backend.')
    target = int(np.argmax(probabilities))
    evidence = sentence_evidence(text, classifier) if classifier and os.getenv('LEXITRACE_SENTENCE_EVIDENCE', 'false').lower() == 'true' else []
    result = {'text': text, 'prediction': LABELS[target], 'confidence': probabilities[target],
              'class_probabilities': dict(zip(LABELS, probabilities)), 'analysis_level': 'document', 'model_mode': mode,
              'model_name': 'DeBERTa-v3 document classifier' if classifier else 'Demo heuristics',
              'model_version': version,
              'sentences': evidence, 'explanation_method': 'Document classifier applied to sentence fragments (first 20); model signals, not proof.' if evidence else 'No sentence or token explanations available.',
              'linguistic_features': analyze_linguistic_features(text),
              'disclaimer': 'AI detection is probabilistic, not proof of authorship. Model scores are not measured accuracy.' + (' Demo mode is untrained and not validated.' if mode == 'demo' else '')}
    result['logging_status'] = LoggingService().store(result)
    return result
