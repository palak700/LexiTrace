import {useState} from 'react';
import {analyzeText} from '../services/api';
import type {AnalysisResponse} from '../types/analysis';

export function Dashboard(){
 const [text,setText]=useState(''); const [result,setResult]=useState<AnalysisResponse|null>(null);
 const [busy,setBusy]=useState(false); const [error,setError]=useState('');
 async function run(){setBusy(true);setError('');setResult(null);try{setResult(await analyzeText(text));}catch(e){setError(e instanceof Error?e.message:'Analysis failed');}finally{setBusy(false);}}
 return <main className="max-w-7xl mx-auto p-6 space-y-6">
 <header><h1 className="text-3xl font-bold">LexiTrace</h1><p>Detect → Localize Evidence → Explain</p></header>
 <section className="bg-white rounded-lg p-5 shadow-sm"><h2 className="font-semibold">Text input</h2>
 <textarea className="w-full min-h-64 border rounded p-3 mt-3" maxLength={20000} value={text} onChange={e=>{setText(e.target.value);setResult(null);}} placeholder="Paste your document"/>
 <p>{text.trim()?text.trim().split(/\s+/).length:0} words · {text.length}/20000 characters</p>
 <button className="bg-ink text-white px-5 py-2 rounded mt-3 disabled:opacity-50" disabled={busy||!text.trim()} onClick={run}>{busy?'Analyzing…':'Analyze text'}</button>
 {error&&<p role="alert" className="text-red-700 mt-3">{error}</p>}</section>
 {result&&<>
 <section className="bg-white p-5 rounded"><h2 className="text-xl font-semibold">Prediction summary</h2>
 <p>{result.prediction} · {(result.confidence*100).toFixed(1)}% confidence</p><p>{result.model_name}</p>
 {Object.entries(result.class_probabilities).map(([label,score])=><div key={label} className="my-3"><span>{label}: {(score*100).toFixed(1)}%</span><div className="h-3 bg-gray-100 rounded"><div className="h-3 bg-blue-500 rounded" style={{width:`${score*100}%`}}/></div></div>)}
 <p className="text-amber-800">{result.disclaimer}</p></section>
 <section className="bg-white p-5 rounded"><h2 className="text-xl font-semibold">Sentence evidence</h2><p>Color intensity shows sentence support for the document prediction.</p>
 <div className="mt-3 leading-9">{result.sentences.map((s,i)=><span key={i} title={`${s.prediction}; support ${(s.score*100).toFixed(1)}%`} style={{backgroundColor:`rgba(234,179,8,${s.score*.6})`}}>{s.sentence} </span>)}</div></section>
 <section className="bg-white p-5 rounded"><h2 className="text-xl font-semibold">Token attribution</h2><p>{result.explanation_method}</p>
 <p>Blue supports the predicted class; red opposes it. Scores are normalized within each sentence.</p>
 {result.sentences.filter(s=>s.tokens.length).map((s,i)=><div key={i} className="my-4"><p className="text-sm">{s.sentence}</p><div className="flex flex-wrap gap-1 mt-2">{s.tokens.map((t,j)=><span key={j} title={`Attribution: ${t.score.toFixed(3)}`} className="px-1 rounded" style={{backgroundColor:t.score>=0?`rgba(59,130,246,${Math.abs(t.score)*.7})`:`rgba(239,68,68,${Math.abs(t.score)*.7})`}}>{t.token}</span>)}</div><p className="text-xs">Convergence delta: {s.convergence_delta?.toExponential(2)}</p></div>)}
 {!result.sentences.some(s=>s.tokens.length)&&<p className="mt-3">Token explanations require trained sentence-model mode.</p>}</section>
 <section className="bg-white p-5 rounded"><h2 className="text-xl font-semibold">Research panel</h2><p>Mode: {result.model_mode} · PostgreSQL logging: {result.logging_status}</p><p>Use the evaluation CLI for held-out metrics. No measured accuracy is assumed.</p><pre className="overflow-auto mt-3">{JSON.stringify(result.linguistic_features,null,2)}</pre></section>
 </>}
 </main>;
}
