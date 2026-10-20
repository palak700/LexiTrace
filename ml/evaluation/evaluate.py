"""Evaluate the app's exact document preprocessing and windowed inference on held-out data."""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from ml.preprocessing.prepare import validate_splits
from ml.evaluation.metrics import compute_classification_metrics, confusion_matrix_as_list
from backend.app.core.labels import LABELS


def run_evaluation(data,model_dir,errors_output=None):
    from backend.app.services.pipeline import DocumentClassifierService,ModelUnavailable,normalize_text
    from backend.app.services.prediction_diagnostics import checkpoint_signature,file_fingerprints
    if errors_output and Path(errors_output).exists():
        raise ValueError('Error report already exists; choose a new path.')
    splits=validate_splits(data)
    classifier=DocumentClassifierService(str(model_dir))
    labels=[row['label'] for row in splits['test']]
    predictions=[]
    errors=[]
    for row in splits['test']:
        # Production /predict applies this before calling the same classifier.
        content=normalize_text(row['text'])
        scores=classifier.predict(content)
        predicted=max(range(len(scores)),key=scores.__getitem__)
        predictions.append(predicted)
        if predicted!=row['label']:
            errors.append({'text_sha256':hashlib.sha256(content.encode()).hexdigest(),'group_id':row['group_id'],
                           'true_label':LABELS[row['label']],'predicted_label':LABELS[predicted],
                           **{f'score_{index}':score for index,score in enumerate(scores)}})
    if checkpoint_signature(classifier.checkpoint_directory)!=classifier.checkpoint_signature:
        raise ModelUnavailable('Checkpoint files changed during evaluation. Restart and repeat with unchanged weights.')
    fingerprints=file_fingerprints(str(classifier.checkpoint_directory),classifier.checkpoint_signature)
    if checkpoint_signature(classifier.checkpoint_directory)!=classifier.checkpoint_signature:
        raise ModelUnavailable('Checkpoint files changed while fingerprinting the evaluation model.')
    matrix=confusion_matrix_as_list(labels,predictions)
    report={'labels':LABELS,'sample_count':len(labels),'metrics':compute_classification_metrics(labels,predictions),
            'confusion_matrix':matrix,'split':'test','group_disjoint':True,
            'test_sha256':hashlib.sha256((Path(data)/'test.csv').read_bytes()).hexdigest(),
            'measured_at':datetime.now(timezone.utc).isoformat(),'inference':'overlapping 512-token document windows',
            'preprocessing':'collapse Unicode whitespace and strip; identical to /predict',
            'checkpoint':{'directory_name':classifier.checkpoint_directory.name,'sha256':fingerprints},
            'error_count':len(errors),'ai_generated_as_ai_edited_human_count':matrix[LABELS.index('AI-Generated')][LABELS.index('AI-Edited Human')]}
    if errors_output:
        path=Path(errors_output)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',newline='',encoding='utf-8') as handle:
            fields=['text_sha256','group_id','true_label','predicted_label']+[f'score_{index}' for index in range(len(LABELS))]
            writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(errors)
    return report


def main():
    parser=argparse.ArgumentParser(description='Evaluate the app pipeline on held-out grouped documents without altering weights.')
    parser.add_argument('--data',required=True);parser.add_argument('--model-dir',required=True);parser.add_argument('--output')
    parser.add_argument('--errors-output',help='Optional new CSV of misclassified example hashes, groups, labels and scores; no submitted text.')
    args=parser.parse_args()
    if args.output and Path(args.output).exists():
        raise ValueError('Output already exists; choose a new report path.')
    report=run_evaluation(args.data,args.model_dir,args.errors_output)
    output=json.dumps(report,indent=2)
    if args.output:
        path=Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as handle: handle.write(output)
    print(output)
if __name__=='__main__': main()
