import type { AnalysisResponse } from '../types/analysis';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export async function analyzeText(text: string): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? 'Analysis failed.');
  }

  return response.json();
}
