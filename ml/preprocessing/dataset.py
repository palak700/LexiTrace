from pathlib import Path
from datasets import DatasetDict, load_dataset

def load_text_classification_dataset(path):
    root=Path(path)
    return load_dataset('csv', data_files={s:str(root/(s+'.csv')) for s in ('train','validation','test')})
def tokenize_dataset(dataset, tokenizer, max_length=512):
    return dataset.map(lambda batch:tokenizer(batch['text'],truncation=True,max_length=max_length),
                       batched=True,remove_columns=['text','source'])
