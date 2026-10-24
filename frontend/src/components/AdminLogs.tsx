import {useEffect, useState} from 'react';
import {ScrollText} from 'lucide-react';
import {ApiError, request} from '../services/api';

type Logs = {
  status:'available'|'disabled'|'unavailable';message:string;total:number;
  items:{id:number;created_at:string;character_count:number;prediction:string;confidence:number;model_mode:string}[];
};

export function AdminLogs({refreshKey,onSignedOut}:{refreshKey?:string;onSignedOut:()=>void}) {
  const [data,setData]=useState<Logs|null>(null);
  const [start,setStart]=useState('');
  const [end,setEnd]=useState('');
  const [offset,setOffset]=useState(0);
  const [revision,setRevision]=useState(0);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);setError('');setData(null);
    const params=new URLSearchParams({offset:String(offset),limit:'20'});
    if(start) params.set('start_date',start);
    if(end) params.set('end_date',end);
    if(start&&end&&start>end) {setError('Start date must be on or before end date.');setLoading(false);return;}
    request<Logs>(`/admin/logs?${params}`,{signal:controller.signal})
      .then(value=>{if(!controller.signal.aborted) setData(value);})
      .catch(e=>{if(!controller.signal.aborted) {if(e instanceof ApiError&&e.status===401) onSignedOut();else setError(e instanceof Error?e.message:'Unable to load logs.');}})
      .finally(()=>{if(!controller.signal.aborted) setLoading(false);});
    return ()=>controller.abort();
  },[start,end,offset,revision,refreshKey]);
  return <section className="panel history-panel admin-logs" aria-label="Administrator analysis logs">
    <div className="panel-heading"><div><h2><ScrollText size={20}/> Analysis logs</h2><p className="muted">Analysis activity across all accounts and guest sessions. Document text is never shown here.</p></div><button className="text-button" disabled={loading} onClick={()=>setRevision(value=>value+1)}>Refresh logs</button></div>
    <div className="history-filters"><label>From date (UTC)<input type="date" value={start} max={end||undefined} onChange={e=>{setStart(e.target.value);setOffset(0);}}/></label><label>To date (UTC)<input type="date" value={end} min={start||undefined} onChange={e=>{setEnd(e.target.value);setOffset(0);}}/></label><button className="text-button" onClick={()=>{setStart('');setEnd('');setOffset(0);}}>Clear dates</button></div>
    {loading&&<p className="muted" role="status">Loading logs...</p>}
    {error&&<p className="error" role="alert">{error}</p>}
    {data&&<><p className={data.status==='unavailable'?'analysis-warning':'muted'} role="status">{data.message}</p>
      {data.status==='available'&&<>{data.items.length?<div className="research-table"><table><caption className="sr-only">Recent analysis logs</caption><thead><tr><th scope="col">ID</th><th scope="col">Date and time</th><th scope="col">Prediction</th><th scope="col">Model score</th><th scope="col">Characters</th><th scope="col">Mode</th></tr></thead><tbody>{data.items.map(item=><tr key={item.id}><td>#{item.id}</td><td><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></td><td>{item.prediction}{item.confidence<0.6?' (uncertain)':''}</td><td>{(item.confidence*100).toFixed(1)}%</td><td>{item.character_count.toLocaleString()}</td><td>{item.model_mode}</td></tr>)}</tbody></table></div>:<p className="muted">No logged analyses found{start||end?' for these dates':''}.</p>}
      {data.total>20&&<div className="history-pagination"><button className="text-button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous</button><span className="muted">{offset+1}-{Math.min(offset+20,data.total)} of {data.total}</span><button className="text-button" disabled={offset+20>=data.total} onClick={()=>setOffset(offset+20)}>Next</button></div>}</>}
      <p className="muted">Logs contain successful analyses recorded by PostgreSQL. Login events and server error traces are not included. Model scores are not measured accuracy.</p>
    </>}
  </section>;
}
