import type { EvidenceSentence } from '../types/analysis';

type Props = {
  text: string;
  sentences: EvidenceSentence[];
};

export function HighlightedText({ text, sentences }: Props) {
  const important = new Set(sentences.map((item) => item.sentence.trim()));
  const chunks = text.match(/[^.!?]+[.!?]?/g) ?? [text];

  return (
    <div className="rounded-lg border border-ink/10 bg-white p-4 leading-8 shadow-sm">
      {chunks.map((chunk, index) => {
        const trimmed = chunk.trim();
        const isImportant = important.has(trimmed);
        return (
          <span
            key={`${trimmed}-${index}`}
            className={isImportant ? 'rounded bg-gold/30 px-1 py-0.5' : ''}
          >
            {chunk}{' '}
          </span>
        );
      })}
    </div>
  );
}
