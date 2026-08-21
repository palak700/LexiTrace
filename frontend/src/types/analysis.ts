export type ClassProbabilities = {
  human: number;
  ai_generated: number;
  ai_polished_human: number;
  humanized_ai: number;
};

export type LinguisticFeatures = {
  perplexity: number | null;
  vocabulary_diversity: number | null;
  average_sentence_length: number | null;
  burstiness: number | null;
  readability: number | null;
  passive_voice: number | null;
  pos_distribution: Record<string, number>;
  punctuation: Record<string, number>;
};

export type EvidenceSentence = {
  sentence: string;
  score: number;
};

export type EvidenceToken = {
  token: string;
  score: number;
};

export type AnalysisResponse = {
  prediction: 'Human' | 'AI-generated' | 'AI-polished human' | 'Humanized AI';
  confidence: number;
  ai_contribution: number;
  class_probabilities: ClassProbabilities;
  linguistic_features: LinguisticFeatures;
  explanation: {
    method: string;
    important_sentences: EvidenceSentence[];
    important_tokens: EvidenceToken[];
  };
  summary: string;
  model_mode: string;
  model_name: string;
  disclaimer: string;
};
