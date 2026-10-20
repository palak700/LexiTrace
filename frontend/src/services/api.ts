import type { AnalysisResponse, ProductLabel, SentenceEvidence } from '../types/analysis';
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
  return response.json();
}
function trainedModelResult<T extends {model_mode:string}>(result:T):T {
  if(result.model_mode!=='model') {
    throw new ApiError('Trained-model predictions are unavailable. Enable model mode and configure a compatible Human / AI-Generated / AI-Edited Human checkpoint.',503);
  }
  return result;
}
export async function analyzeText(text:string) {
  return trainedModelResult(await request<AnalysisResponse>('/analyze', {method:'POST', body:JSON.stringify({text})}));
}

export type PredictionResponse = {
  label: ProductLabel;
  confidence:number;
  confidences:Record<ProductLabel,number>;
  model_mode:string;
  disclaimer:string;
  sentences?:SentenceEvidence[];
  explanation_method?:string;
};
export async function predictText(text:string) {
  return trainedModelResult(await request<PredictionResponse>('/predict', {method:'POST',body:JSON.stringify({text})}, ''));
}

export function extractDocument(file:File) {
  const body=new FormData();
  body.append('file',file);
  return request<{text:string;filename:string;word_count:number;character_count:number}>('/documents/extract',{method:'POST',body});
}
