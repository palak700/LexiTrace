import type { AnalysisResponse, ProductLabel, SentenceEvidence, HistoryMetadata } from '../types/analysis';
export type User = {id:number; name:string; email:string; role:'admin'|'user'};
export type Capabilities = {max_text_chars:number; min_words:number; max_upload_bytes:number; upload_formats:string[]; analysis_level:string;labels:ProductLabel[];allow_anonymous:boolean;model_mode:string};
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
export class ApiError extends Error {
  constructor(message:string, public status:number) { super(message); }
}
export async function request<T>(path:string, options:RequestInit = {}, prefix='/api'):Promise<T> {
  const response = await fetch(`${API_BASE_URL}${prefix}${path}`, {
    ...options, credentials:'include', headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}), ...options.headers}
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = typeof payload.detail === 'string' ? payload.detail :
      Array.isArray(payload.detail) ? payload.detail.map((item:{msg:string})=>item.msg).join('. ') : 'Request failed. Please try again.';
    throw new ApiError(detail, response.status);
  }
  return response.status===204?undefined as T:response.json();
}
function trainedModelResult<T extends {model_mode:string}>(result:T):T {
  if(result.model_mode!=='model') {
    throw new ApiError('Trained-model predictions are unavailable. Enable model mode and configure a compatible Human / AI-Generated / AI-Edited Human checkpoint.',503);
  }
  return result;
}
export async function analyzeText(text:string, save_text=false) {
  return trainedModelResult(await request<AnalysisResponse>('/analyze', {method:'POST', body:JSON.stringify({text,save_text})}));
}

export type PredictionResponse = HistoryMetadata & {
  label: ProductLabel;
  confidence:number;
  confidences:Record<ProductLabel,number>;
  model_mode:string;
  disclaimer:string;
  sentences?:SentenceEvidence[];
  explanation_method?:string;
};
export async function predictText(text:string, save_text=false) {
  return trainedModelResult(await request<PredictionResponse>('/predict', {method:'POST',body:JSON.stringify({text,save_text})}, ''));
}

export type HistoryRecord = {
  id:string;created_at:string;text_saved:boolean;text?:string|null;
  result:{prediction:ProductLabel;confidence:number;class_probabilities:Record<ProductLabel,number>;
    model_name:string;model_version?:string;model_mode:string;word_count:number;character_count:number;
    disclaimer:string;explanation_method?:string;sentences?:SentenceEvidence[];
    explanation?:{method?:string;target_label?:string;scope?:string;disclaimer?:string;approximation_warning?:boolean}};
};

export async function downloadReport(id:string) {
  const response=await fetch(`${API_BASE_URL}/api/history/${encodeURIComponent(id)}/report.pdf`,{credentials:'include'});
  if(!response.ok) {
    const payload=await response.json().catch(()=>({}));
    throw new ApiError(typeof payload.detail==='string'?payload.detail:'Unable to download the report.',response.status);
  }
  const url=URL.createObjectURL(await response.blob());
  const link=document.createElement('a');link.href=url;link.download=`lexitrace-${id}.pdf`;
  document.body.appendChild(link);link.click();link.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export function extractDocument(file:File) {
  const body=new FormData();
  body.append('file',file);
  return request<{text:string;filename:string;word_count:number;character_count:number}>('/documents/extract',{method:'POST',body});
}
