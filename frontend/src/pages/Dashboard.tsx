import {EvidencePanel} from '../components/EvidencePanel';
import {ResearchPanel} from '../components/ResearchPanel';
import {useEffect, useRef, useState, type ChangeEvent} from 'react';
import {ArrowRight, FileText, LayoutDashboard, LogOut, ShieldCheck, Upload, Info} from 'lucide-react';
import {analyzeText, ApiError, extractDocument, request, type Capabilities, type User} from '../services/api';
import type {AnalysisResponse} from '../types/analysis';

export function Dashboard({user,onSignedOut}:{user:User;onSignedOut:()=>void}) {
  const [text,setText] = useState('');
  const [filename,setFilename] = useState('');
  const [result,setResult] = useState<AnalysisResponse|null>(null);
  const [busy,setBusy] = useState(false);
  const [uploading,setUploading] = useState(false);
  const [error,setError] = useState('');
  const [limits,setLimits] = useState<Capabilities|null>(null);
  const [limitsError,setLimitsError] = useState(false);
  const [signingOut,setSigningOut] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const words = text.trim() ? text.trim().split(/\s+/u).length : 0;
  const chars = Array.from(text).length;
  const tooShort = !!limits && words<limits.min_words;
  const tooLong = !!limits && chars>limits.max_text_chars;
  async function loadLimits() {
    setLimitsError(false);
    try { setLimits(await request<Capabilities>('/capabilities')); }
    catch { setLimitsError(true); }
  }
  useEffect(()=>{void loadLimits();},[]);
  async function run() {
    setBusy(true);setError('');setResult(null);
    try { setResult(await analyzeText(text)); }
    catch(e) { if(e instanceof ApiError && e.status===401) onSignedOut(); else setError(e instanceof Error?e.message:'Analysis failed.'); }
    finally { setBusy(false); }
  }
  async function upload(event:ChangeEvent<HTMLInputElement>) {
    const file=event.target.files?.[0]; event.target.value='';
    if (!file || !limits) return;
    setError('');
    if (!/\.(pdf|txt)$/i.test(file.name)) {setError('Please upload a PDF or UTF-8 .txt document.');return;}
    if (file.size>limits.max_upload_bytes) {setError('File is too large. Maximum upload size is 5 MB.');return;}
    setUploading(true);
    try {
      const document=await extractDocument(file);
      setText(document.text);setFilename(document.filename);setResult(null);
    } catch(e) {
      if(e instanceof ApiError&&e.status===401) onSignedOut();
      else setError(e instanceof Error?e.message:'Unable to read this document.');
    }
    finally {setUploading(false);}
  }
  async function logout() {
    setSigningOut(true); setError('');
    try {await request('/auth/logout',{method:'POST'});onSignedOut();}
    catch(e) {setError(e instanceof Error?e.message:'Unable to sign out.');}
    finally {setSigningOut(false);}
  }
  return <div className="workspace">
    <aside className="sidebar"><a className="brand" href="/"><span className="brand-mark"><FileText size={23}/></span>LexiTrace</a><p className="nav-label">Workspace</p><div className="nav-current"><LayoutDashboard size={19}/>Dashboard</div><div className="sidebar-bottom"><span className="avatar">{user.name.charAt(0).toUpperCase()}</span><div><strong>{user.name}</strong><small>{user.role==='admin'?'Administrator':'User account'}</small></div></div></aside>
    <div className="workspace-main">
      <header className="topbar"><span>Workspace <span className="breadcrumb">/ Dashboard</span></span><button className="text-button" onClick={logout} disabled={signingOut||busy||uploading}><LogOut size={16}/>{signingOut?'Signing out...':'Sign out'}</button></header>
      <main className="dashboard">
        <div className="page-heading"><div><p className="eyebrow">Document intelligence</p><h1>{user.role==='admin'?'Admin dashboard':'Your dashboard'}</h1><p className="muted">Welcome, {user.name}. Take a closer look at your document.</p></div><span className="status-pill"><span/>Document-level analysis</span></div>
        <section className="overview-grid" aria-label="Analysis information">
          <div className="info-card"><FileText size={21}/><span>Minimum input</span><strong>{limits?`${limits.min_words} words`:"Loading minimum..."}</strong><small>Paste at least 50 words to analyze</small></div>
          <div className="info-card"><FileText size={21}/><span>Analysis scope</span><strong>Whole document</strong><small>One prediction for the complete input</small></div>
          <div className="info-card"><Upload size={21}/><span>Document limit</span><strong>{limits?`${limits.max_text_chars.toLocaleString()} characters`:'Loading limit...'}</strong><small>{limits?`About ${Math.round(limits.max_text_chars/6).toLocaleString()}-${Math.round(limits.max_text_chars/5).toLocaleString()} English words`:'Fetching the server upload limit'}</small></div>
          <div className="info-card"><ShieldCheck size={21}/><span>Supported format</span><strong>PDF or plain text</strong><small>Upload a file or paste its contents</small></div>
        </section>
        <div className="notice"><Info size={20}/><p><strong>How analysis works</strong><br/>This dashboard reports document-level AI authorship signals. Optional sentence evidence uses the document classifier on sentence fragments and is shown only when available. It is a model signal, not proof. The exact upload limit is measured in characters, including spaces and punctuation; word capacity varies with word length.</p></div>
        {limitsError&&<p className="error" role="alert">Unable to load upload limits. <button className="text-button" onClick={loadLimits}>Try again</button></p>}
        <section className="panel document-panel"><div className="panel-heading"><div><h2>Analyze a document</h2><p className="muted">Add your document to see its overall authorship assessment.</p></div><span className="step-label">01 / Input</span></div>
          <input ref={fileInput} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="sr-only" aria-label="Upload PDF or text document" onChange={upload} disabled={busy||uploading||!limits}/>
          <button className="upload-zone" disabled={busy||uploading||!limits} onClick={()=>fileInput.current?.click()}><span className="upload-icon"><Upload size={23}/></span><strong>{uploading?'Reading document...':filename||'Choose a document to upload'}</strong><span>PDF or UTF-8 .txt / maximum 5 MB {limits?` / up to ${limits.max_text_chars.toLocaleString()} characters`:''}</span></button>
          <label className="input-label" htmlFor="document-text">Or paste your document</label>
          <textarea id="document-text" value={text} disabled={busy||uploading} onChange={e=>{setText(e.target.value);setFilename('');setResult(null);setError('');}} placeholder="Paste the complete document you want to analyze..." aria-describedby="document-count word-minimum" aria-invalid={tooLong||(!!text.trim()&&tooShort)}/>
          <div className="input-footer"><p id="document-count" className={tooLong?'over-limit':'muted'}>{words.toLocaleString()} words <span>/</span> {chars.toLocaleString()}{limits?` / ${limits.max_text_chars.toLocaleString()}`:''} characters</p><button className="text-button" disabled={busy||uploading||!text} onClick={()=>{setText('');setFilename('');setResult(null);setError('');}}>Clear</button></div>
          <p id="word-minimum" className={text.trim()&&tooShort?"over-limit muted":"muted"}>{limits?`Minimum input: ${limits.min_words} words.`:"Loading minimum input length..."} </p>
          {!!text.trim()&&tooShort&&<p className="error" role="alert">text too short</p>}
          {tooLong&&<p className="error" role="alert">Shorten your document to {limits?.max_text_chars.toLocaleString()} characters before analyzing.</p>}
          {error&&<p className="error" role="alert">{error}</p>}
          <div className="analysis-actions"><p className="muted">Results apply to the complete document.</p><button className="primary" disabled={busy||uploading||!text.trim()||tooLong||tooShort||!limits} onClick={run}>{busy?'Analyzing document...':'Analyze document'}<ArrowRight size={18}/></button></div>
        </section>
        {result&&<section className="panel results" aria-live="polite"><div className="panel-heading"><div><p className="eyebrow">Document assessment</p><h2>{result.prediction}</h2><p className="muted">{(result.confidence*100).toFixed(1)}% model score for the whole document</p></div><span className="status-pill">LexiTrace analysis</span></div>
          <div className="probabilities">{Object.entries(result.class_probabilities).map(([label,score])=><div key={label}><div className="probability-label"><span>{label}</span><strong>{(score*100).toFixed(1)}%</strong></div><div className="probability-track"><div style={{width:`${score*100}%`}}/></div></div>)}</div>
          <p className="muted">{result.disclaimer}</p>
          <p className="muted">A high class score can still be wrong; it is not a measured accuracy percentage.</p>
          <EvidencePanel sentences={result.sentences} method={result.explanation_method}/>
          {user.role==='admin'&&<details className="admin-details"><summary>Administrator diagnostics</summary><p>Model: {result.model_name} / Logging: {result.logging_status}</p><p>Linguistic estimates describe the document and do not identify AI-written words.</p><pre>{JSON.stringify(result.linguistic_features,null,2)}</pre></details>}
        </section>}
        <ResearchPanel text={text}/>
        <footer className="dashboard-footer">LexiTrace <span>AI detection is probabilistic, not proof of authorship.</span></footer>
      </main>
    </div>
  </div>;
}
