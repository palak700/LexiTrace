import {useEffect, useState} from 'react';
import {Download, History, Trash2} from 'lucide-react';
import {ApiError, downloadReport, request, type HistoryRecord} from '../services/api';
import {UNCERTAIN_CONFIDENCE} from './AnalysisGuidance';
import {EvidencePanel} from './EvidencePanel';
import type {HistoryMetadata} from '../types/analysis';

export function HistoryConsent({checked,onChange,disabled}:{checked:boolean;onChange:(value:boolean)=>void;disabled:boolean}) {
  return <div className="history-consent"><label><input type="checkbox" checked={checked} disabled={disabled} onChange={event=>onChange(event.target.checked)}/>Save document text with this analysis</label><p className="muted">Results are saved to your private history. Document text and sentence excerpts are saved only when checked. You can delete records at any time.</p></div>;
}

export function ReportButton({id,onSignedOut}:{id:string;onSignedOut:()=>void}) {
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  async function download() {
    setBusy(true);setError('');
    try {await downloadReport(id);}
    catch(e) {if(e instanceof ApiError&&e.status===401) onSignedOut();else setError(e instanceof Error?e.message:'Download failed.');}
    finally {setBusy(false);}
  }
  return <div><button type="button" className="text-button" disabled={busy} onClick={download}><Download size={16}/>{busy?'Preparing PDF...':'Download PDF report'}</button>{error&&<p className="error" role="alert">{error}</p>}</div>;
}

export function SavedResultActions({result,onSignedOut}:{result:HistoryMetadata;onSignedOut:()=>void}) {
  return <div className="saved-result-actions">{result.history_id&&<><p className="muted">Saved to your history {result.text_saved?'with document text.':'without document text.'}</p><ReportButton id={result.history_id} onSignedOut={onSignedOut}/></>}{result.history_saved===false&&<p className="error" role="alert">This result could not be saved to history. PDF export is unavailable for this analysis. Please try a new analysis later.</p>}</div>;
}

export function AnalysisHistory({refreshKey,onSignedOut}:{refreshKey?:string;onSignedOut:()=>void}) {
  const [items,setItems]=useState<HistoryRecord[]>([]);
  const [total,setTotal]=useState(0);
  const [start,setStart]=useState('');
  const [end,setEnd]=useState('');
  const [offset,setOffset]=useState(0);
  const [revision,setRevision]=useState(0);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [selected,setSelected]=useState<HistoryRecord|null>(null);
  const [pendingDelete,setPendingDelete]=useState<string|null>(null);
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);setError('');setItems([]);
    const params=new URLSearchParams({offset:String(offset),limit:'10'});
    if(start) params.set('start_date',start);
    if(end) params.set('end_date',end);
    if(start&&end&&start>end) {setError('Start date must be on or before end date.');setLoading(false);return;}
    request<{items:HistoryRecord[];total:number}>(`/history?${params}`,{signal:controller.signal})
      .then(data=>{if(!controller.signal.aborted) {setItems(data.items);setTotal(data.total);}})
      .catch(e=>{if(!controller.signal.aborted) {if(e instanceof ApiError&&e.status===401) onSignedOut();else setError(e instanceof Error?e.message:'Unable to load history.');}})
      .finally(()=>{if(!controller.signal.aborted) setLoading(false);});
    return ()=>controller.abort();
  },[start,end,offset,revision,refreshKey]);
  async function view(id:string) {
    setBusy(true);setError('');
    try {setSelected(await request<HistoryRecord>(`/history/${id}`));}
    catch(e) {if(e instanceof ApiError&&e.status===401) onSignedOut();else setError(e instanceof Error?e.message:'Unable to open analysis.');}
    finally {setBusy(false);}
  }
  async function remove(id:string) {
    setBusy(true);setError('');
    try {
      await request<void>(`/history/${id}`,{method:'DELETE'});
      if(selected?.id===id) setSelected(null);
      setPendingDelete(null);
      if(items.length===1&&offset>0) setOffset(Math.max(0,offset-10));
      else setRevision(value=>value+1);
    } catch(e) {if(e instanceof ApiError&&e.status===401) onSignedOut();else setError(e instanceof Error?e.message:'Unable to delete analysis.');}
    finally {setBusy(false);}
  }
  return <section className="panel history-panel" aria-label="Analysis history">
    <div className="panel-heading"><div><h2><History size={20}/> Analysis history</h2><p className="muted">Your previous assessments. Date filters use UTC calendar dates.</p></div><button className="text-button" disabled={loading||busy} onClick={()=>setRevision(value=>value+1)}>Refresh</button></div>
    <div className="history-filters"><label>From date (UTC)<input type="date" value={start} max={end||undefined} disabled={busy} onChange={e=>{setStart(e.target.value);setOffset(0);}}/></label><label>To date (UTC)<input type="date" value={end} min={start||undefined} disabled={busy} onChange={e=>{setEnd(e.target.value);setOffset(0);}}/></label><button className="text-button" disabled={busy} onClick={()=>{setStart('');setEnd('');setOffset(0);}}>Clear dates</button></div>
    {error&&<p className="error" role="alert">{error}</p>}
    {loading?<p className="muted" role="status">Loading history...</p>:!error&&<>
      {!items.length?<p className="muted">No analyses found{start||end?' for these dates':''}.</p>:<ul className="history-list">{items.map(item=><li key={item.id}>
        <div><strong>{item.result.confidence<UNCERTAIN_CONFIDENCE?'Uncertain':item.result.prediction}</strong><p className="muted"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time> · {item.result.word_count} words · {item.text_saved?'Text saved':'Results only'}</p></div>
        <div className="history-item-actions"><button className="text-button" disabled={busy} onClick={()=>void view(item.id)}>View result</button><ReportButton id={item.id} onSignedOut={onSignedOut}/>{pendingDelete===item.id?<><button className="text-button delete-button" disabled={busy} onClick={()=>void remove(item.id)}>Confirm delete</button><button className="text-button" disabled={busy} onClick={()=>setPendingDelete(null)}>Cancel</button></>:<button className="text-button delete-button" disabled={busy} onClick={()=>setPendingDelete(item.id)}><Trash2 size={15}/>Delete</button>}</div>
      </li>)}</ul>}
      {total>10&&<div className="history-pagination"><button className="text-button" disabled={busy||offset===0} onClick={()=>setOffset(Math.max(0,offset-10))}>Previous</button><span className="muted">{offset+1}-{Math.min(offset+10,total)} of {total}</span><button className="text-button" disabled={busy||offset+10>=total} onClick={()=>setOffset(offset+10)}>Next</button></div>}
    </>}
    {selected&&<article className="history-detail" aria-label="Saved analysis result"><div className="panel-heading"><h3>Saved assessment</h3><button className="text-button" disabled={busy} onClick={()=>setSelected(null)}>Close</button></div>
      <p><strong>{selected.result.confidence<UNCERTAIN_CONFIDENCE?'Uncertain':selected.result.prediction}</strong> · {(selected.result.confidence*100).toFixed(1)}% highest model score</p>
      <p className="muted">{new Date(selected.created_at).toLocaleString()} · {selected.result.model_name}</p><p className="muted model-version">Model version: {selected.result.model_version??'Unavailable'}</p>
      <div className="probabilities">{Object.entries(selected.result.class_probabilities).map(([label,score])=><div key={label}><div className="probability-label"><span>{label}</span><strong>{(score*100).toFixed(1)}%</strong></div><div className="probability-track"><div style={{width:`${score*100}%`}}/></div></div>)}</div>
      <p className="muted">{selected.result.disclaimer}</p><p className="muted">{selected.result.explanation_method}</p>
      {selected.result.explanation&&<div><h4>Saved explanation</h4><p className="muted">{selected.result.explanation.method} · {selected.result.explanation.target_label}</p><p className="muted">{selected.result.explanation.scope}</p>{selected.result.explanation.approximation_warning&&<p className="analysis-warning">Low explanation reliability: numerical approximation error is high.</p>}<p className="muted">{selected.result.explanation.disclaimer}</p></div>}
      <EvidencePanel sentences={selected.result.sentences} method={selected.result.explanation_method}/>
      {selected.text_saved?<details><summary>Saved document text</summary><pre className="history-text">{selected.text}</pre></details>:<p className="muted">Document text was not saved for this analysis.</p>}
      <ReportButton id={selected.id} onSignedOut={onSignedOut}/>
    </article>}
  </section>;
}
