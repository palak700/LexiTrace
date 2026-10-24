export type ProductLabel='Human'|'AI-Generated'|'AI-Edited Human';
export type SentenceEvidence={sentence:string;start:number;end:number;prediction:ProductLabel;score:number;class_probabilities:Record<ProductLabel,number>;tokens:unknown[]};
export type HistoryMetadata={history_id?:string;created_at?:string;text_saved?:boolean;history_saved?:boolean;model_version?:string};
export type AnalysisResponse=HistoryMetadata & {text:string;prediction:ProductLabel;confidence:number;class_probabilities:Record<ProductLabel,number>;
 analysis_level:'document';model_mode:string;model_name:string;disclaimer:string;logging_status:string;
 sentences?:SentenceEvidence[];explanation_method?:string;linguistic_features:Record<string,unknown>};
