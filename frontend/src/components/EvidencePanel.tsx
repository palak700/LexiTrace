import type {SentenceEvidence} from '../types/analysis';
export function EvidencePanel({sentences,method}:{sentences?:SentenceEvidence[];method?:string}) {
  if(!sentences?.length) return null;
  return <section className="evidence-panel" aria-label="Sentence evidence"><h3>Sentence evidence</h3><p className="muted">{method} Scores are model signals, not proof of authorship. A document model is not a separately validated sentence detector.</p><ol>{sentences.map((sentence,index)=><li key={`${sentence.start}-${index}`}><p>{sentence.sentence}</p><small>{sentence.prediction}: {(sentence.score*100).toFixed(1)}% model confidence</small></li>)}</ol><p className="muted">Token attribution is not available for this configuration.</p></section>;
}
