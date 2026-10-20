"""On-demand, signed token attributions for the first production-sized window."""
import math

from app.core.labels import LABELS
from app.services.pipeline import ModelUnavailable


def explain_text(classifier, text):
    try:
        from captum.attr import IntegratedGradients
    except ImportError as exc:
        raise ModelUnavailable('Captum is unavailable. Install ml/requirements.txt to enable explanations.') from exc

    torch = classifier.torch
    probabilities = classifier.predict(text)
    target = max(range(len(probabilities)), key=probabilities.__getitem__)
    model_target = classifier.label_indices[target]
    tokenizer = classifier.tokenizer
    # Use the same 512-token window size as prediction, with offsets into normalized text.
    encoded = tokenizer(text, return_tensors='pt', truncation=True, max_length=512,
                        return_offsets_mapping=True, return_special_tokens_mask=True)
    offsets = encoded.pop('offset_mapping')[0].tolist()
    special = encoded.pop('special_tokens_mask')[0].tolist()
    device = next(classifier.model.parameters()).device
    inputs = {key: value.to(device) for key, value in encoded.items()}
    ids = inputs.pop('input_ids')
    reference_id = tokenizer.mask_token_id
    if reference_id is None:
        raise ModelUnavailable('The tokenizer needs a mask token for the attribution baseline.')
    baseline_ids = ids.clone()
    for index, is_special in enumerate(special):
        if not is_special:
            baseline_ids[0, index] = reference_id
    embedding_layer = classifier.model.get_input_embeddings()

    def forward(embeddings):
        batch_inputs = {key: value.expand(embeddings.shape[0], -1) for key, value in inputs.items()}
        return classifier.model(inputs_embeds=embeddings, **batch_inputs).logits.softmax(-1)

    # Detached word embeddings avoid hooks or any mutation of the shared model.
    with torch.enable_grad():
        embeddings = embedding_layer(ids).detach()
        baseline = embedding_layer(baseline_ids).detach()
        attribution, delta = IntegratedGradients(forward).attribute(
            embeddings, baselines=baseline, target=model_target, n_steps=16,
            internal_batch_size=1, return_convergence_delta=True)
        with torch.no_grad():
            window_probability = forward(embeddings)[0, model_target].item()
            baseline_probability = forward(baseline)[0, model_target].item()
        scores = attribution.sum(dim=-1)[0].detach().cpu().tolist()

    if not all(math.isfinite(value) for value in scores + [delta.item(), window_probability, baseline_probability]):
        raise RuntimeError('Non-finite attribution values.')
    scale = max((abs(value) for value, mask in zip(scores, special) if not mask), default=0.0)
    tokens = []
    for (start, end), is_special, value in zip(offsets, special, scores):
        if not is_special and end > start:
            tokens.append({'text': text[start:end], 'start': start, 'end': end,
                           'attribution': value, 'normalized_attribution': value / scale if scale else 0.0})
    end = max((token['end'] for token in tokens), default=0)
    return {
        'method': 'Captum Integrated Gradients', 'target_label': LABELS[target],
        'document_confidence': probabilities[target],
        'window_probability': window_probability, 'baseline_probability': baseline_probability,
        'convergence_delta': float(delta.item()), 'integration_steps': 16,
        'baseline': 'Mask-token word embeddings; special tokens and attention mask held fixed.',
        'approximation_warning': abs(delta.item()) > max(0.05, 0.1*abs(window_probability-baseline_probability)),
        'scope': 'First model window only (up to 512 tokens including special tokens).',
        'partial': bool(text[end:].strip()), 'text': text[:end], 'tokens': tokens,
        'disclaimer': 'Positive scores support the target class; negative scores oppose it relative to the baseline. '
                      'These explain model behavior, not actual authorship. Scores are not probabilities. '
                      'For long documents this explains only the first window, not the averaged document prediction. '
                      'The convergence delta reports numerical approximation error, not explanation reliability.',
    }
