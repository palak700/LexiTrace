from types import SimpleNamespace
import re

import pytest
import torch

from app.services.explanations import explain_text


class Tokenizer:
    mask_token_id = 0

    def __call__(self, text, **kwargs):
        matches = list(re.finditer(r'\S+', text))[:kwargs['max_length']-2]
        ids = [3] + [1 if match.group() == 'support' else 2 for match in matches] + [3]
        return {
            'input_ids': torch.tensor([ids]), 'attention_mask': torch.ones(1, len(ids), dtype=torch.long),
            'offset_mapping': torch.tensor([[(0, 0)] + [match.span() for match in matches] + [(0, 0)]]),
            'special_tokens_mask': torch.tensor([[1] + [0]*len(matches) + [1]]),
        }


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = torch.nn.Embedding(4, 1)
        with torch.no_grad():
            self.embedding.weight.copy_(torch.tensor([[0.0], [0.3], [-0.1], [0.0]]))

    def get_input_embeddings(self):
        return self.embedding

    def forward(self, inputs_embeds, attention_mask):
        score = (inputs_embeds.squeeze(-1)*attention_mask).sum(-1)
        return SimpleNamespace(logits=torch.stack([score*0, score*0, score], dim=-1))


def classifier():
    # Canonical Human is deliberately mapped to raw model output 2.
    return SimpleNamespace(torch=torch, tokenizer=Tokenizer(), model=TinyModel().eval(),
                           label_indices=[2, 0, 1], predict=lambda text: [0.8, 0.1, 0.1])


def test_real_captum_signed_attributions_mapping_offsets_and_completeness():
    model = classifier()
    weights = model.model.embedding.weight.detach().clone()
    result = explain_text(model, 'support oppose')
    assert result['target_label'] == 'Human'
    assert result['partial'] is False
    assert [token['text'] for token in result['tokens']] == ['support', 'oppose']
    assert result['tokens'][0]['attribution'] > 0
    assert result['tokens'][1]['attribution'] < 0
    assert abs(result['convergence_delta']) < 1e-5
    assert sum(token['attribution'] for token in result['tokens']) == pytest.approx(
        result['window_probability']-result['baseline_probability'], abs=1e-5)
    for token in result['tokens']:
        assert result['text'][token['start']:token['end']] == token['text']
        assert -1 <= token['normalized_attribution'] <= 1
    assert torch.equal(weights, model.model.embedding.weight)
    assert model.model.embedding.weight.grad is None


def test_long_document_scope_is_explicit_and_attributions_are_finite():
    result = explain_text(classifier(), 'support '*511)
    assert result['partial'] is True
    assert len(result['tokens']) == 510
    assert 'First model window' in result['scope']
    assert all(torch.isfinite(torch.tensor(token['attribution'])) for token in result['tokens'])
