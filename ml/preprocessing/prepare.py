"""Explicit CSV adapters: only user-supplied OpAI and LLMTrace exports."""
import argparse, csv, random, json, re
from pathlib import Path
LABELS = ['Human-Written','AI-Generated','AI-Transformed']
class DatasetPreparationService:
    def prepare(self, sources, output, component):
        rows = {}; conflicting = set()
        aliases = {'0':0,'1':1,'2':2,'human-written':0,'human':0,'ai-generated':1,
                   'ai-transformed':2,'ai-polished human':2}
        for source,path in sources:
            if source not in ('OpAI','LLMTrace'): raise ValueError('Unsupported source')
            with open(path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                if not {'text','label'} <= set(reader.fieldnames or []):
                    raise ValueError('Export must contain text,label columns. Map source labels explicitly before import.')
                for row in reader:
                    text = re.sub(r'\s+',' ',row['text']).strip()
                    label = aliases.get(row['label'].strip().lower())
                    if label is None: raise ValueError('Unknown label: '+row['label'])
                    if len(text)<10: continue
                    key=text.casefold()
                    if key in rows and rows[key]['label'] != label: conflicting.add(key)
                    rows[key]={'text':text,'label':label,'source':source}
        for key in conflicting: rows.pop(key,None)
        # Split at document level first to prevent cross-split sentence leakage.
        splits={'train':[],'validation':[],'test':[]}
        for label in range(3):
            group=[r for r in rows.values() if r['label']==label]
            random.Random(42).shuffle(group)
            if len(group)<10: raise ValueError('Need at least 10 unique, nonconflicting documents per class.')
            n=max(1,round(len(group)*.1))
            for name,part in [('test',group[:n]),('validation',group[n:2*n]),('train',group[2*n:])]:
                splits[name].extend(part)
        out=Path(output); out.mkdir(parents=True,exist_ok=True)
        for name,part in splits.items():
            if component=='sentence':
                # Sentence labels must be genuine sentence annotations, not inherited document labels.
                # Each input row must already be a labeled sentence for this component.
                if any(len(re.findall(r'[.!?]+(?:\s|$)',r['text']))>1 for r in part):
                    raise ValueError('Sentence training requires sentence-annotated rows, not document labels.')
            with (out/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=['text','label','source']); w.writeheader(); w.writerows(part)
        (out/'manifest.json').write_text(json.dumps({'sources':['OpAI','LLMTrace'],'component':component,
             'counts':{k:len(v) for k,v in splits.items()},'conflicts_removed':len(conflicting)},indent=2))
def main():
    p=argparse.ArgumentParser(); p.add_argument('--opai',required=True); p.add_argument('--llmtrace',required=True)
    p.add_argument('--output',required=True); p.add_argument('--component',choices=['document','sentence'],required=True)
    a=p.parse_args(); DatasetPreparationService().prepare([('OpAI',a.opai),('LLMTrace',a.llmtrace)],a.output,a.component)
if __name__=='__main__': main()
