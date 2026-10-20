from pathlib import Path
from datasets import load_dataset
from ml.preprocessing.prepare import validate_splits
from backend.app.services.pipeline import normalize_text


def load_text_classification_dataset(path):
    validate_splits(path)
    root=Path(path)
    return load_dataset('csv',data_files={split:str(root/f'{split}.csv') for split in ('train','validation','test')})


def tokenize_dataset(dataset,tokenizer,max_length=512):
    columns=[column for column in dataset['train'].column_names if column!='label']
    return dataset.map(lambda batch:tokenizer([normalize_text(text) for text in batch['text']],truncation=True,max_length=max_length),batched=True,remove_columns=columns)
