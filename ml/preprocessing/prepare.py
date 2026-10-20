"""Document/source-grouped preparation with duplicate and label validation."""
import argparse
import csv
import hashlib
import json
import random
import re
from pathlib import Path
from backend.app.core.labels import LABELS, encode_label


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def read_examples(sources):
    rows = []
    parents = {}
    def find(key):
        parents.setdefault(key, key)
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]
    def union(left, right):
        parents[find(right)] = find(left)
    seen = {}
    duplicates = 0
    for source, path in sources:
        with Path(path).open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if not {'text','label'} <= set(reader.fieldnames or []):
                raise ValueError('CSV must contain text,label and document_id or source_id columns.')
            for number, row in enumerate(reader, 2):
                content = normalized(row.get('text', ''))
                if not content:
                    raise ValueError(f'{source} row {number}: empty text.')
                label = encode_label(row['label'])
                identifiers = [f'{field}:{row[field].strip()}' for field in ('document_id','source_id') if row.get(field, '').strip()]
                if not identifiers:
                    raise ValueError(f'{source} row {number}: document_id or source_id is required to prevent leakage.')
                for identifier in identifiers:
                    union(identifiers[0], identifier)
                digest = hashlib.sha256(content.casefold().encode()).hexdigest()
                if digest in seen:
                    previous = rows[seen[digest]]
                    if previous['label'] != label:
                        raise ValueError('Conflicting labels found for duplicate normalized text.')
                    union(previous['_group'], identifiers[0])
                    duplicates += 1
                    continue
                seen[digest] = len(rows)
                rows.append({'text':content, 'label':label, 'source':source, '_group':identifiers[0], 'text_sha256':digest})
    for row in rows:
        row['group_id'] = hashlib.sha256(find(row.pop('_group')).encode()).hexdigest()
    if {row['label'] for row in rows} != set(range(len(LABELS))):
        raise ValueError('Human, AI-Generated, and AI-Edited Human examples are all required.')
    return rows, duplicates


def split_groups(rows):
    groups = sorted({row['group_id'] for row in rows})
    if len(groups) < 3:
        raise ValueError('At least three independent original-document/source groups are required.')
    best = None
    best_score = float('inf')
    rng = random.Random(42)
    # Search deterministic group assignments; never split a connected source/document group.
    for _ in range(600):
        rng.shuffle(groups)
        for held_out in {max(1,round(len(groups)*.1)), max(len(LABELS),round(len(groups)*.1))}:
            if held_out*2 >= len(groups):
                continue
            assignment = {group: ('test' if i<held_out else 'validation' if i<2*held_out else 'train') for i,group in enumerate(groups)}
            splits = {name:[row for row in rows if assignment[row['group_id']]==name] for name in ('train','validation','test')}
            if any({row['label'] for row in part} != set(range(len(LABELS))) for part in splits.values()):
                continue
            score = sum(abs(len(splits[name])/len(rows)-target) for name,target in [('train',.8),('validation',.1),('test',.1)])
            if score < best_score:
                best, best_score = splits, score
    if best is None:
        raise ValueError('Cannot create three group-disjoint splits containing all three classes. Supply more independent groups for each class.')
    return best


def validate_splits(root):
    result = {}
    known_text, known_groups = {}, {}
    for split in ('train','validation','test'):
        with (Path(root)/f'{split}.csv').open(newline='',encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError(f'{split} is empty.')
        local_text = set()
        for row in rows:
            content = normalized(row.get('text',''))
            if not content or not row.get('group_id'):
                raise ValueError('Prepared data requires nonempty text and group_id.')
            label = encode_label(row['label'])
            row['label'] = label
            digest = hashlib.sha256(content.casefold().encode()).hexdigest()
            group = row['group_id']
            if digest in local_text:
                raise ValueError(f'Duplicate example in {split}.')
            local_text.add(digest)
            if digest in known_text and known_text[digest] != split:
                raise ValueError('Duplicate text leaks across dataset splits.')
            if group in known_groups and known_groups[group] != split:
                raise ValueError('Original-document/source group leaks across dataset splits.')
            known_text[digest], known_groups[group] = split, split
        if {row['label'] for row in rows} != set(range(len(LABELS))):
            raise ValueError(f'{split} must contain all three product classes.')
        result[split] = rows
    return result


class DatasetPreparationService:
    def prepare(self, sources, output, component='document'):
        if component != 'document':
            raise ValueError('Only document preparation is supported.')
        rows, duplicates = read_examples(sources)
        splits = split_groups(rows)
        out = Path(output)
        if any((out/f'{split}.csv').exists() for split in splits):
            raise ValueError('Output already contains prepared splits; choose a new directory to preserve existing data.')
        out.mkdir(parents=True,exist_ok=True)
        for split, part in splits.items():
            with (out/f'{split}.csv').open('w',newline='',encoding='utf-8') as handle:
                writer=csv.DictWriter(handle,fieldnames=['text','label','source','group_id','text_sha256'])
                writer.writeheader();writer.writerows(part)
        manifest={'labels':LABELS,'component':'document','split_method':'connected original-document/source groups; approximate 80/10/10',
                  'counts':{key:len(value) for key,value in splits.items()},'duplicates_removed':duplicates}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        validate_splits(out)
        return manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--opai',required=True);parser.add_argument('--llmtrace',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--component',choices=['document'],default='document')
    args=parser.parse_args()
    print(json.dumps(DatasetPreparationService().prepare([('OpAI',args.opai),('LLMTrace',args.llmtrace)],args.output,args.component),indent=2))
if __name__=='__main__': main()
