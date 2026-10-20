"""Read-only diagnostics for the real checkpoint used by the prediction pipeline."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path


def checkpoint_signature(path):
    root=Path(path).resolve()
    names={'config.json','tokenizer.json','tokenizer_config.json'}
    names.update(file.name for file in root.glob('*.safetensors'))
    names.update(file.name for file in root.glob('pytorch_model*.bin'))
    names.update(file.name for file in root.glob('*.index.json'))
    return tuple((name,(root/name).stat().st_size,(root/name).stat().st_mtime_ns) for name in sorted(names))


@lru_cache(maxsize=2)
def file_fingerprints(path,signature):
    output={}
    for name,_,_ in signature:
        digest=hashlib.sha256()
        with (Path(path)/name).open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):
                digest.update(chunk)
        output[name]=digest.hexdigest()
    return output


def prediction_summary(scores,labels):
    index=max(range(len(scores)),key=scores.__getitem__)
    return {'label':labels[index],'confidence':scores[index],'confidences':dict(zip(labels,scores))}


def diagnose_prediction(text):
    from app.core.config import document_model_path
    from app.core.labels import LABELS
    from app.services.pipeline import ModelUnavailable,current_mode,document_model,load_lock,normalize_text
    if current_mode()!='model':
        raise ModelUnavailable('Prediction diagnostics require the real trained model to be enabled.')
    with load_lock:
        classifier=document_model(document_model_path())
    root=classifier.checkpoint_directory
    if checkpoint_signature(root)!=classifier.checkpoint_signature:
        raise ModelUnavailable('Checkpoint files changed after loading. Restart the backend before diagnosing predictions.')
    normalized=normalize_text(text)
    tokenizer=classifier.tokenizer
    original_tokens=len(tokenizer(text,truncation=False,add_special_tokens=True)['input_ids'])
    normalized_tokens=len(tokenizer(normalized,truncation=False,add_special_tokens=True)['input_ids'])
    windows=tokenizer(normalized,truncation=True,max_length=512,stride=64,return_overflowing_tokens=True,padding=False)['input_ids']
    production=prediction_summary(classifier.predict(normalized),LABELS)
    production.update({'strategy':'All-document overlapping windows','max_length':512,'stride':64,'window_count':len(windows),
                       'total_tokens_with_overlap':sum(map(len,windows)),'max_window_tokens':max(map(len,windows)),
                       'document_truncated':False})
    def single_pass(content,length):
        encoded=tokenizer(content,return_tensors='pt',truncation=True,max_length=length)
        with classifier.torch.inference_mode():
            logits=classifier.model(**encoded).logits[0]
            raw_logits=logits.tolist()
            scores=logits.softmax(-1).tolist()
        ordered=[scores[index] for index in classifier.label_indices]
        result=prediction_summary(ordered,LABELS)
        result.update({'max_length':length,'tokens_processed':int(encoded['input_ids'].shape[1]),
                       'truncated':len(tokenizer(content,truncation=False,add_special_tokens=True)['input_ids'])>length,
                       'logits':{label:raw_logits[index] for label,index in zip(LABELS,classifier.label_indices)}})
        return result
    at256=single_pass(normalized,256)
    at512=single_pass(normalized,512)
    original256=single_pass(text,256)
    fingerprints=file_fingerprints(str(root),classifier.checkpoint_signature)
    if checkpoint_signature(root)!=classifier.checkpoint_signature:
        raise ModelUnavailable('Checkpoint files changed during diagnostics. Restart the backend and retry.')
    config=json.loads((root/'config.json').read_text(encoding='utf-8'))
    return {'checkpoint':{'directory_name':root.name,'sha256':fingerprints,
                           'saved_id2label':{str(key):value for key,value in classifier.model.config.id2label.items()},
                           'output_labels':LABELS,'num_labels':classifier.model.config.num_labels,
                           'evaluation_mode':not classifier.model.training,'tokenizer_class':type(tokenizer).__name__,
                           'saved_transformers_version':config.get('transformers_version')},
            'input':{'word_count':len(text.split()),'character_count':len(text),'normalized_character_count':len(normalized),
                     'normalization_changed_text':text!=normalized,'original_token_count':original_tokens,'normalized_token_count':normalized_tokens},
            'production':production,'first_256_normalized':at256,'first_512_normalized':at512,'first_256_original':original256,
            'comparisons':{'production_vs_256_label_changed':production['label']!=at256['label'],
                           'production_vs_256_max_score_difference':max(abs(production['confidences'][label]-at256['confidences'][label]) for label in LABELS),
                           'normalization_256_label_changed':at256['label']!=original256['label'],
                           'normalization_256_max_score_difference':max(abs(at256['confidences'][label]-original256['confidences'][label]) for label in LABELS)},
            'notes':['256 tokens is the comparison setting from the supplied Colab notes; training_args.bin was not unpickled to infer training settings.',
                     'Compare checkpoint SHA-256 values with the Colab files to verify checkpoint identity.',
                     'Softmax scores are not calibrated accuracy estimates; diagnostics do not establish accuracy.',
                     'Input text, token IDs and diagnostic requests are not stored by this endpoint.']}
