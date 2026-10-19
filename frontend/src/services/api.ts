import type { AnalysisResponse } from '../types/analysis';
export type User = {id:number; name:string; email:string; role:'admin'|'user'};
export type Capabilities = {max_text_chars:number; min_words:number; max_upload_bytes:number; upload_formats:string[]; analysis_level:string};
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
export function analyzeText(text:string) {
  return request<AnalysisResponse>('/analyze', {method:'POST', body:JSON.stringify({text})});
}

export type PredictionResponse = {
  label: 'Human'|'AI-Generated'|'AI-Edited Human';
  confidence:number;
  confidences:Record<'Human'|'AI-Generated'|'AI-Edited Human',number>;
  model_mode:string;
  disclaimer:string;
};
export function predictText(text:string) {
  return request<PredictionResponse>('/predict', {method:'POST',body:JSON.stringify({text})}, '');
}

export function extractDocument(file:File) {
  const body=new FormData();
  body.append('file',file);
  return request<{text:string;filename:string;word_count:number;character_count:number}>('/documents/extract',{method:'POST',body});
}
