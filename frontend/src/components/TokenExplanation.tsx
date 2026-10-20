import {useState} from 'react';
import {ApiError, request} from '../services/api';
import type {ProductLabel} from '../types/analysis';

type Explanation = {
  method:string; target_label:ProductLabel; scope:string; partial:boolean; text:string;
  window_probability:number; convergence_delta:number; disclaimer:string; approximation_warning:boolean;
  tokens:{text:string;start:number;end:number;attribution:number;normalized_attribution:number}[];
};

export function TokenExplanation({text,onSignedOut}:{text:string;onSignedOut:()=>void}) {
  const [result,setResult] = useState<Explanation|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  async function explain() {
    setBusy(true);setError('');
    try {setResult(await request<Explanation>('/explain',{method:'POST',body:JSON.stringify({text})}));}
    catch(e) {
      if(e instanceof ApiError&&e.status===401) onSignedOut();
      else setError(e instanceof Error?e.message:'Unable to explain this prediction.');
    } finally {setBusy(false);}
  }
  let cursor=0;
  const characters=Array.from(result?.text??'');
  return <section className="token-explanation" aria-label="Explain prediction">
    <h3>What influenced this prediction?</h3>
    <p className="muted">Generate token highlights showing how the model responds to your text. This can take longer than analysis.</p>
    <button className="text-button" onClick={explain} disabled={busy||!!result}>{busy?'Computing explanation...':result?'Explanation generated':'Explain with Captum'}</button>
    {error&&<p className="error" role="alert">{error}</p>}
    {result&&<div aria-live="polite">
      {result.approximation_warning&&<p className="analysis-warning">Low explanation reliability: the numerical approximation error is high. Token highlights may be unstable.</p>}
      <p className="muted">Target class: <strong>{result.target_label}</strong>. {result.scope} {result.partial&&'The rest of this document is not highlighted.'}</p>
      <p className="muted">Green: supports this class. Orange: opposes it. Stronger color means greater relative influence; uncolored tokens have little influence.</p>
      <div className="token-highlights">{result.tokens.map((token,index)=>{
        // Some subword offsets overlap; show each source character only once.
        if(token.end<=cursor) return null;
        const gap=characters.slice(cursor,token.start).join('');
        const content=characters.slice(Math.max(cursor,token.start),token.end).join('');
        cursor=token.end;
        const score=token.normalized_attribution;
        const background=score>0?`rgba(42,145,91,${Math.abs(score)*0.5})`:score<0?`rgba(221,132,40,${Math.abs(score)*0.5})`:'transparent';
        return <span key={index}>{gap}<mark style={{background,color:'inherit'}} title={`${score>0?'Supports':score<0?'Opposes':'Neutral toward'} ${result.target_label}; attribution ${token.attribution.toPrecision(3)}`}>{content}</mark></span>;
      })}{characters.slice(cursor).join('')}</div>
      <p className="muted">{result.disclaimer}</p>
      <details><summary>Explanation details</summary><p className="muted">{result.method}. Target score in this window: {(result.window_probability*100).toFixed(1)}%. Convergence delta: {result.convergence_delta.toPrecision(3)}.</p></details>
    </div>}
  </section>;
}
