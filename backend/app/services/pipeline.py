"""Three-class document/sentence pipeline. Demo scores are not model explanations."""
import os
import re
from functools import lru_cache
from pathlib import Path
import numpy as np

LABELS = ['Human-Written', 'AI-Generated', 'AI-Transformed']
ROOT = Path(__file__).resolve().parents[3]

class PreprocessingService:
    def clean(self, text):
        return re.sub(r'\s+', ' ', text).strip()
    def sentences(self, text):
        return [m for m in re.finditer(r'[^.!?]+(?:[.!?]+|$)', text) if m.group().strip()]

class ModelUnavailable(RuntimeError):
    pass

class ClassifierService:
    def __init__(self, component):
        self.component = component
        path = Path(os.getenv(f'LEXITRACE_{component.upper()}_MODEL', str(ROOT / 'ml/models' / component)))
        if not path.is_dir():
            raise ModelUnavailable(f'Missing {component} model. Train it or configure LEXITRACE_{component.upper()}_MODEL.')
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, use_fast=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True).eval()
        if self.model.config.model_type != 'deberta-v2' or self.model.config.num_labels != 3:
            raise ModelUnavailable(f'{component} must be a three-class DeBERTa-v3 checkpoint.')
        if [self.model.config.id2label[i] for i in range(3)] != LABELS:
            raise ModelUnavailable(f'{component} checkpoint label mapping must match {LABELS}.')
    def predict(self, text):
        # Chunk long documents instead of silently dropping text beyond the context window.
        batches = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512,
                                 stride=64, return_overflowing_tokens=True, padding=True)
        batches.pop('overflow_to_sample_mapping', None)
        with self.torch.no_grad():
            probs = []
            for start in range(0, len(batches['input_ids']), 8):
                logits = self.model(**{k:v[start:start+8] for k,v in batches.items()}).logits
                probs.append(logits.softmax(-1))
            return self.torch.cat(probs).mean(0).tolist()

class DocumentClassifierService(ClassifierService):
    def __init__(self): super().__init__('document')
class SentenceClassifierService(ClassifierService):
    def __init__(self): super().__init__('sentence')

class ExplainabilityService:
    def tokens(self, classifier, text, target):
        from captum.attr import LayerIntegratedGradients
        torch = classifier.torch
        encoded = classifier.tokenizer(text, return_tensors='pt', truncation=True,
                                       max_length=512, return_offsets_mapping=True)
        offsets = encoded.pop('offset_mapping')[0].tolist()
        ids = encoded['input_ids']
        baseline = torch.full_like(ids, classifier.tokenizer.pad_token_id)
        special = classifier.tokenizer.get_special_tokens_mask(ids[0].tolist(), already_has_special_tokens=True)
        for i, flag in enumerate(special):
            if flag: baseline[0,i] = ids[0,i]
        def forward(input_ids):
            return classifier.model(input_ids=input_ids, attention_mask=encoded['attention_mask']).logits
        ig = LayerIntegratedGradients(forward, classifier.model.get_input_embeddings())
        attrs, delta = ig.attribute(ids, baselines=baseline, target=target, n_steps=32,
                                    internal_batch_size=4, return_convergence_delta=True)
        scores = attrs.sum(-1)[0].detach().cpu().numpy()
        scale = max(float(np.abs(scores).max()), 1e-9)
        return ([{'token':text[a:b], 'start':a, 'end':b, 'score':float(scores[i]/scale)}
                 for i,(a,b) in enumerate(offsets) if b>a], float(delta.detach().abs().max()))

@lru_cache(maxsize=1)
def models():
    return DocumentClassifierService(), SentenceClassifierService()

def demo_predict(text):
    terms = len(re.findall(r'\b(comprehensive|furthermore|moreover|optimize|streamline|efficiency)\b', text.lower()))
    raw = np.array([1.5, 0.7+terms*.25, .8+terms*.15])
    return (raw/raw.sum()).tolist()

def analyze(text):
    from app.features.linguistic import analyze_linguistic_features
    from app.services.logging_service import LoggingService
    text = PreprocessingService().clean(text)
    mode = os.getenv('LEXITRACE_MODE', 'demo')
    if mode not in ('demo','model'): raise ModelUnavailable('LEXITRACE_MODE must be demo or model.')
    doc, sentence_model = models() if mode == 'model' else (None,None)
    probabilities = doc.predict(text) if doc else demo_predict(text)
    target = int(np.argmax(probabilities))
    evidence = []
    for match in PreprocessingService().sentences(text):
        raw = match.group(); content = raw.strip(); start = match.start()+len(raw)-len(raw.lstrip())
        probs = sentence_model.predict(content) if sentence_model else demo_predict(content)
        evidence.append({'sentence':content,'start':start,'end':start+len(content),
                         'prediction':LABELS[int(np.argmax(probs))], 'score':probs[target],
                         'class_probabilities':dict(zip(LABELS,probs)), 'tokens':[]})
    important = sorted(range(len(evidence)), key=lambda i:evidence[i]['score'], reverse=True)[:3]
    for i in important:
        if sentence_model:
            tokens, delta = ExplainabilityService().tokens(sentence_model,evidence[i]['sentence'],target)
            evidence[i]['tokens'] = tokens
            evidence[i]['convergence_delta'] = delta
    result = {'text':text,'prediction':LABELS[target],'confidence':probabilities[target],
              'class_probabilities':dict(zip(LABELS,probabilities)), 'sentences':evidence,
              'model_mode':mode,'model_name':'Two DeBERTa-v3 classifiers' if doc else 'Demo heuristics',
              'explanation_method':'Captum Layer Integrated Gradients' if doc else 'Demo sentence scores; no token attributions',
              'linguistic_features':analyze_linguistic_features(text),
              'disclaimer':'AI detection is probabilistic, not proof of authorship. Demo mode is untrained and not validated.'}
    result['logging_status'] = LoggingService().store(result)
    return result
