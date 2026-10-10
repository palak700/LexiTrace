export type Token = {token:string; start:number; end:number; score:number};
export type Sentence = {sentence:string; start:number; end:number; prediction:string; score:number; tokens:Token[]; convergence_delta?:number};
export type AnalysisResponse = {text:string; prediction:string; confidence:number; class_probabilities:Record<string,number>;
 sentences:Sentence[]; model_mode:string; model_name:string; explanation_method:string; disclaimer:string; logging_status:string;
 linguistic_features:Record<string,unknown>};
