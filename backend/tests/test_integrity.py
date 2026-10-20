import csv
import json
from pathlib import Path
import pytest
from ml.preprocessing.prepare import DatasetPreparationService,validate_splits,read_examples
from ml.evaluation.metrics import compute_classification_metrics,confusion_matrix_as_list
from app.services.pipeline import inspect_checkpoint,ModelUnavailable
from app.services import logging_service


def write_rows(path,rows):
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def examples():
    return [{'text':f'Document {group} distinct variant {label} for data preparation testing.', 'label':label,'document_id':str(group)} for group in range(15) for label in (0,1,2)]


def test_grouped_split_and_cross_source_duplicates(tmp_path):
    rows=examples()
    first=tmp_path/'a.csv';second=tmp_path/'b.csv'
    write_rows(first,rows)
    write_rows(second,[{**rows[0],'text':rows[0]['text'].upper(),'document_id':'alias-group'},
                       {'text':'Additional variant belongs to alias group.','label':0,'document_id':'alias-group'}])
    out=tmp_path/'prepared'
    report=DatasetPreparationService().prepare([('OpAI',first),('LLMTrace',second)],out)
    assert report['duplicates_removed']==1
    splits=validate_splits(out)
    group_sets=[{row['group_id'] for row in split} for split in splits.values()]
    assert all(not group_sets[i]&group_sets[j] for i in range(3) for j in range(i))
    with pytest.raises(ValueError,match='already'): DatasetPreparationService().prepare([('OpAI',first)],out)


@pytest.mark.parametrize('change,match', [
    ({'text':'   '},'empty'),({'label':'Unknown'},'Invalid label'),({'document_id':''},'required'),
])
def test_invalid_training_rows(tmp_path,change,match):
    path=tmp_path/'bad.csv';write_rows(path,[{**examples()[0],**change}])
    with pytest.raises(ValueError,match=match): read_examples([('OpAI',path)])


def test_conflicting_duplicate_labels(tmp_path):
    path=tmp_path/'bad.csv';rows=examples()[:1];write_rows(path,[rows[0],{**rows[0],'label':1}])
    with pytest.raises(ValueError,match='Conflicting'): read_examples([('OpAI',path)])


def test_group_leakage_detected_on_import(tmp_path):
    for name in ('train','validation','test'):
        write_rows(tmp_path/f'{name}.csv',[{'text':f'{name} example {label}','label':label,'group_id':'shared'} for label in (0,1,2)])
    with pytest.raises(ValueError,match='leaks'): validate_splits(tmp_path)


def test_three_class_metrics_and_confusion_matrix():
    metrics=compute_classification_metrics([0,0,1,2],[0,1,1,2])
    assert metrics['accuracy']==0.75
    assert set(metrics)=={'accuracy','precision_macro','recall_macro','f1_macro'}
    assert confusion_matrix_as_list([0,0,1,2],[0,1,1,2])==[[1,1,0],[0,1,0],[0,0,1]]
    with pytest.raises(ValueError): compute_classification_metrics([0,3],[0,1])


def test_checkpoint_files_are_validated(tmp_path):
    with pytest.raises(ModelUnavailable,match='config.json'): inspect_checkpoint(tmp_path)
    (tmp_path/'config.json').write_text(json.dumps({'model_type':'deberta-v2','num_labels':3,'id2label':{'0':'Human','1':'AI-Generated','2':'AI-Edited Human'}}))
    with pytest.raises(ModelUnavailable,match='weights'): inspect_checkpoint(tmp_path)
    (tmp_path/'model.safetensors').write_bytes(b'not real weights')
    with pytest.raises(ModelUnavailable,match='tokenizer'): inspect_checkpoint(tmp_path)


def test_database_failure_never_breaks_analysis_or_leaks_credentials(monkeypatch,caplog):
    from app.services.pipeline import analyze
    monkeypatch.setenv('LEXITRACE_MODE','demo')
    def fail(): raise RuntimeError('postgresql://private-user:private-password@host/db')
    monkeypatch.setattr(logging_service,'engine',fail)
    result=analyze('word '*50)
    assert result['logging_status']=='unavailable'
    assert 'private-password' not in caplog.text
    assert 'RuntimeError' in caplog.text


def test_malformed_database_url_is_nonfatal(monkeypatch):
    from app.services.pipeline import analyze
    monkeypatch.setenv('LEXITRACE_MODE','demo')
    monkeypatch.setenv('DATABASE_URL','not-a-valid-database-url')
    assert analyze('word '*50)['logging_status']=='unavailable'


def test_database_insert_excludes_input_text(monkeypatch):
    calls=[]
    class Context:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,statement,params=None): calls.append((str(statement),params))
    class Engine:
        def begin(self): return Context()
    monkeypatch.setattr(logging_service,'engine',lambda:Engine())
    secret='This exact full submitted text must not be stored.'
    status=logging_service.LoggingService().store({'text':secret,'prediction':'Human','confidence':.8,'model_mode':'model','class_probabilities':{'Human':.8,'AI-Generated':.1,'AI-Edited Human':.1}})
    assert status=='stored'
    assert secret not in str(calls)
    assert 'text' not in calls[1][1]


def test_evaluation_uses_exact_api_preprocessing_and_records_checkpoint(tmp_path,monkeypatch):
    from ml.evaluation.evaluate import run_evaluation
    from backend.app.services import pipeline
    from backend.app.services.prediction_diagnostics import checkpoint_signature
    model=tmp_path/'checkpoint'
    model.mkdir()
    for name in ('config.json','tokenizer.json','tokenizer_config.json','model.safetensors'):
        (model/name).write_bytes(b'controlled test artifact')
    for name in ('train','validation','test'):
        write_rows(tmp_path/f'{name}.csv',[{'text':f'  {name}   example\n{label}  ','label':label,'group_id':f'{name}-{label}'} for label in (0,1,2)])
    seen=[]
    class Classifier:
        def __init__(self,path):
            self.checkpoint_directory=model
            self.checkpoint_signature=checkpoint_signature(model)
        def predict(self,text):
            seen.append(text)
            # Deliberately reproduce the confusion under investigation in a controlled fixture.
            predicted=2 if text.endswith('1') else int(text[-1])
            return [.8 if index==predicted else .1 for index in range(3)]
    monkeypatch.setattr(pipeline,'DocumentClassifierService',Classifier)
    errors=tmp_path/'errors.csv'
    report=run_evaluation(tmp_path,'configured-checkpoint',errors_output=errors)
    assert seen==['test example 0','test example 1','test example 2']
    assert report['sample_count']==3
    assert report['metrics']['accuracy']==pytest.approx(2/3)
    assert report['confusion_matrix']==[[1,0,0],[0,0,1],[0,0,1]]
    assert report['ai_generated_as_ai_edited_human_count']==1
    assert report['checkpoint']['directory_name']=='checkpoint'
    assert len(report['checkpoint']['sha256']['model.safetensors'])==64
    assert 'identical to /predict' in report['preprocessing']
    with errors.open(newline='') as handle: rows=list(csv.DictReader(handle))
    assert len(rows)==1
    assert rows[0]['true_label']=='AI-Generated'
    assert rows[0]['predicted_label']=='AI-Edited Human'
    assert 'text' not in rows[0]
    assert 'test example' not in errors.read_text()
    with pytest.raises(ValueError,match='already exists'):
        run_evaluation(tmp_path,'configured-checkpoint',errors_output=errors)



def test_transitive_document_and_source_groups(tmp_path):
    path=tmp_path/'grouped.csv'
    rows=[{'text':'First source original text.','label':0,'document_id':'doc-a','source_id':'original-a'},
          {'text':'First source transformed variant.','label':1,'document_id':'doc-b','source_id':'original-a'},
          {'text':'First source original text.','label':0,'document_id':'doc-c','source_id':'original-b'},
          {'text':'Second source related variant.','label':1,'document_id':'doc-d','source_id':'original-b'},
          {'text':'Third class related variant.','label':2,'document_id':'doc-e','source_id':'original-b'}]
    write_rows(path,rows)
    examples,duplicates=read_examples([('OpAI',path)])
    assert duplicates==1
    assert len({row['group_id'] for row in examples})==1



def test_checkpoint_identity_changes_when_files_change(tmp_path):
    from app.services.prediction_diagnostics import checkpoint_signature,file_fingerprints
    for name in ('config.json','tokenizer.json','tokenizer_config.json','model.safetensors'):
        (tmp_path/name).write_bytes(b'first version')
    signature=checkpoint_signature(tmp_path)
    first=file_fingerprints(str(tmp_path),signature)
    (tmp_path/'model.safetensors').write_bytes(b'updated checkpoint weights')
    changed=checkpoint_signature(tmp_path)
    second=file_fingerprints(str(tmp_path),changed)
    assert signature!=changed
    assert first['model.safetensors']!=second['model.safetensors']
    assert first['tokenizer.json']==second['tokenizer.json']
    assert 'training_args.bin' not in first



def test_training_tokenization_uses_production_whitespace_normalization():
    from ml.preprocessing.dataset import tokenize_dataset
    seen=[]
    class Split:
        column_names=['text','label','source','group_id']
    class Dataset:
        def __getitem__(self,name): return Split()
        def map(self,callback,**kwargs):
            assert kwargs['batched'] is True
            assert 'label' not in kwargs['remove_columns']
            return callback({'text':['  original\n   passage  ','Second\tpassage']})
    def tokenizer(texts,**kwargs):
        seen.append((texts,kwargs));return {'input_ids':[[1],[2]]}
    tokenize_dataset(Dataset(),tokenizer)
    assert seen==[(['original passage','Second passage'],{'truncation':True,'max_length':512})]
