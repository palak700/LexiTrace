export const MIN_ANALYSIS_WORDS = 50;
export const NORMAL_ANALYSIS_WORDS = 150;
export const LONG_DOCUMENT_WORDS = 2000;
export const UNCERTAIN_CONFIDENCE = 0.6;

export function AnalysisLimits() {
  return <p className="muted analysis-limits">Under 50 words: too short to analyze. 50–149 words: low reliability. 150+ words: normal analysis. Over 2,000 words: long documents are analyzed in chunks. Confidence below 60%: uncertain. Results are a probability estimate, not proof.</p>;
}

export function AnalysisWarnings({words, confidence}:{words:number;confidence?:number}) {
  return <div aria-live="polite">
    {words>=MIN_ANALYSIS_WORDS&&words<NORMAL_ANALYSIS_WORDS&&<p className="analysis-warning"><strong>Low reliability.</strong> Short samples provide limited evidence. Use at least 150 words for a more reliable assessment.</p>}
    {words>LONG_DOCUMENT_WORDS&&<p className="analysis-warning"><strong>Long document.</strong> Documents over 2,000 words are analyzed in chunks; the overall estimate may hide differences between sections.</p>}
    {confidence!==undefined&&confidence<UNCERTAIN_CONFIDENCE&&<p className="analysis-warning"><strong>Uncertain.</strong> Confidence is below 60%, so there is not enough evidence for a firm authorship label.</p>}
  </div>;
}
