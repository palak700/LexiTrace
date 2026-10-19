import {useEffect, useRef, useState, type ChangeEvent} from 'react';
import {FileText, LogOut, Upload} from 'lucide-react';
import {ApiError, extractDocument, predictText, request, type Capabilities, type PredictionResponse, type User} from '../services/api';

const LABELS = ['Human','AI-Generated','AI-Edited Human'] as const;
export function UserDashboard({user,onSignedOut}:{user:User;onSignedOut:()=>void}) {
  const [text,setText]=useState('');
  const [result,setResult]=useState<PredictionResponse|null>(null);
  const [busy,setBusy]=useState(false);
  const [uploading,setUploading]=useState(false);
  const [filename,setFilename]=useState('');
  const fileInput=useRef<HTMLInputElement>(null);
  const [signingOut,setSigningOut]=useState(false);
  const [error,setError]=useState('');
  const [limits,setLimits]=useState<Capabilities|null>(null);
  const [limitsError,setLimitsError]=useState(false);
  const [attempted,setAttempted]=useState(false);
  const words=text.trim()?text.trim().split(/\s+/u).length:0;
  const chars=Array.from(text).length;
  const tooShort=words<(limits?.min_words??50);
  const tooLong=!!limits&&chars>limits.max_text_chars;
  async function loadLimits() {
    setLimitsError(false);
    try {setLimits(await request<Capabilities>('/capabilities'));}
    catch {setLimitsError(true);}
  }
  useEffect(()=>{void loadLimits();},[]);
  async function analyze() {
    setAttempted(true);setError('');setResult(null);
    if(tooShort||tooLong||!limits) return;
    setBusy(true);
    try {setResult(await predictText(text));}
    catch(e) {if(e instanceof ApiError&&e.status===401) onSignedOut(); else setError(e instanceof Error?e.message:'Analysis failed. Please try again.');}
    finally {setBusy(false);}
  }
  async function upload(event:ChangeEvent<HTMLInputElement>) {
    const file=event.target.files?.[0];event.target.value='';
    if(!file||!limits) return;
    setError('');setResult(null);
    if(!/\.(pdf|txt)$/i.test(file.name)) {setError('Please upload a PDF or UTF-8 .txt file.');return;}
    if(file.size>limits.max_upload_bytes) {setError('File is too large. Maximum upload size is 5 MB.');return;}
    setUploading(true);
    try {
      const document=await extractDocument(file);
      setText(document.text);setFilename(document.filename);setAttempted(false);
    } catch(e) {
      if(e instanceof ApiError&&e.status===401) onSignedOut();
      else setError(e instanceof Error?e.message:'Unable to read this document.');
    } finally {setUploading(false);}
  }
  async function logout() {
    setSigningOut(true);setError('');
    try {await request('/auth/logout',{method:'POST'});onSignedOut();}
    catch(e) {setError(e instanceof Error?e.message:'Unable to log out.');}
    finally {setSigningOut(false);}
  }
  return <div className="user-workspace">
    <nav className="user-navbar" aria-label="User navigation"><a className="brand" href="/"><span className="brand-mark"><FileText size={22}/></span>LexiTrace</a><div className="user-navbar-actions"><span className="navbar-username">{user.name}</span><button className="text-button" disabled={busy||uploading||signingOut} onClick={logout}><LogOut size={17}/>{signingOut?'Logging out...':'Logout'}</button></div></nav>
    <main className="user-dashboard">
      <div className="user-heading"><p className="eyebrow">Your workspace</p><h1>Analyze your text</h1><p className="muted">Upload a PDF or paste at least {limits?.min_words??50} words to get an authorship assessment of the complete text.</p></div>
      <section className="panel" aria-labelledby="text-heading"><div className="panel-heading"><h2 id="text-heading">Text to analyze</h2><span className="status-pill">Minimum {limits?.min_words??50} words</span></div>
        <input ref={fileInput} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="sr-only" aria-label="Upload PDF or text document" disabled={busy||uploading||signingOut||!limits} onChange={upload}/>
        <button className="upload-zone" onClick={()=>fileInput.current?.click()} disabled={busy||uploading||signingOut||!limits}><span className="upload-icon"><Upload size={23}/></span><strong>{uploading?'Extracting document text...':filename||'Upload a PDF or text document'}</strong><span>PDF or UTF-8 .txt / maximum 5 MB</span></button>
        <p className="muted upload-help">Text-based PDFs, up to 100 pages. Scanned PDFs need OCR first. Review the extracted text below before analyzing.</p>
        <label htmlFor="user-text" className="input-label">Or paste your text</label>
        <textarea id="user-text" value={text} disabled={busy||uploading||signingOut} placeholder="Paste your text here..." aria-describedby="user-text-count user-text-validation" aria-invalid={((!!text.trim()||attempted)&&tooShort)||tooLong} onChange={event=>{setText(event.target.value);setFilename('');setResult(null);setError('');setAttempted(false);}}/>
        <div className="input-footer"><p id="user-text-count" className="muted">{words.toLocaleString()} words <span>/</span> {chars.toLocaleString()}{limits?` / ${limits.max_text_chars.toLocaleString()}`:''} characters</p></div>
        <div id="user-text-validation" aria-live="polite">{(!!text.trim()||attempted)&&tooShort&&<p className="error">text too short</p>}{tooLong&&<p className="error">Text exceeds the {limits?.max_text_chars.toLocaleString()} character limit.</p>}</div>
        {limitsError&&<p className="error" role="alert">Unable to load input limits. <button className="text-button" onClick={loadLimits}>Try again</button></p>}
        {error&&<p className="error" role="alert">{error}</p>}
        <div className="analysis-actions"><p className="muted">{limits?`Maximum ${limits.max_text_chars.toLocaleString()} characters, including spaces.`:'Loading input limits...'}</p><button className="primary" disabled={busy||uploading||signingOut||!limits||tooLong} onClick={analyze}>{busy?'Analyzing...':'Analyze'}</button></div>
      </section>
      {result&&<section className="panel results" aria-label="Analysis result" aria-live="polite"><div className="panel-heading"><div><p className="eyebrow">Prediction</p><h2>{result.label}</h2><p className="muted">{(result.confidence*100).toFixed(1)}% confidence</p></div><span className="status-pill">{result.model_mode==='demo'?'Demo mode':'Model mode'}</span></div>
        <div className="probabilities">{LABELS.map((label,index)=>{const percent=result.confidences[label]*100;return <div key={label}><div className="probability-label"><span>{label}</span><strong>{percent.toFixed(1)}%</strong></div><div className={`probability-track confidence-${index}`} role="progressbar" aria-label={`${label} confidence`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(percent.toFixed(1))}><div style={{width:`${percent}%`}}/></div></div>;})}</div>
        {result.model_mode==='demo'&&<p className="demo-warning">Demo mode uses untrained heuristics. These scores are not validated AI detection.</p>}
        <p className="muted result-disclaimer">{result.disclaimer}</p>
      </section>}
    </main>
  </div>;
}
