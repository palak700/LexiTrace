import { AlertTriangle, BrainCircuit, Loader2, ScanText } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';

import { HighlightedText } from '../components/HighlightedText';
import { MetricCard } from '../components/MetricCard';
import { analyzeText } from '../services/api';
import type { AnalysisResponse } from '../types/analysis';

const sampleText =
  'This proposal provides a comprehensive framework for improving academic writing. It keeps the student voice intact while streamlining grammar, structure, and clarity. The result is polished, consistent, and easier to evaluate.';

const probabilityLabels: Record<string, string> = {
  human: 'Human',
  ai_generated: 'AI-generated',
  ai_polished_human: 'AI-polished',
  humanized_ai: 'Humanized AI'
};

const colors = ['#607466', '#c66b54', '#5e7c8a', '#c49a45', '#8c6d62', '#3f6f77'];

function percent(value: number | null | undefined) {
  if (value === null || value === undefined) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

function numeric(value: number | null | undefined) {
  if (value === null || value === undefined) return 'N/A';
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

export function Dashboard() {
  const [text, setText] = useState(sampleText);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const words = useMemo(() => text.trim().split(/\s+/).filter(Boolean), [text]);

  const probabilityData = result
    ? Object.entries(result.class_probabilities).map(([key, value]) => ({
        name: probabilityLabels[key],
        value: Math.round(value * 100)
      }))
    : [];

  const posData = result
    ? Object.entries(result.linguistic_features.pos_distribution).map(([name, value]) => ({
        name,
        value: Math.round(value * 100)
      }))
    : [];

  const punctuationData = result
    ? Object.entries(result.linguistic_features.punctuation).map(([name, value]) => ({ name, value }))
    : [];

  async function handleAnalyze() {
    setError('');
    setLoading(true);
    try {
      setResult(await analyzeText(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen">
      <section className="border-b border-ink/10 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-ink text-paper">
                <ScanText size={22} />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-normal">LexiTrace</h1>
                <p className="text-sm font-medium text-moss">Explainable AI Text Detection</p>
              </div>
            </div>
          </div>
          <div className="inline-flex items-center gap-2 rounded-lg border border-coral/30 bg-coral/10 px-3 py-2 text-sm font-semibold text-coral">
            <BrainCircuit size={16} />
            Development model
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className="space-y-4">
          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
            <textarea
              className="min-h-80 w-full resize-y rounded-lg border border-ink/15 bg-paper p-4 text-base outline-none focus:border-bluegray focus:ring-2 focus:ring-bluegray/20"
              placeholder="Paste your text here"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex gap-4 text-sm font-medium text-moss">
                <span>{words.length} words</span>
                <span>{text.length} characters</span>
              </div>
              <button
                className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-ink px-5 font-semibold text-paper transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
                disabled={loading || text.trim().length === 0}
                onClick={handleAnalyze}
              >
                {loading ? <Loader2 className="animate-spin" size={18} /> : <ScanText size={18} />}
                Analyze Text
              </button>
            </div>
            {error ? (
              <div className="mt-4 flex items-center gap-2 rounded-lg border border-coral/30 bg-coral/10 px-3 py-2 text-sm font-medium text-coral">
                <AlertTriangle size={16} />
                {error}
              </div>
            ) : null}
          </div>

          {result ? (
            <div className="rounded-lg border border-ink/10 bg-white p-4 text-sm text-ink/75 shadow-sm">
              {result.disclaimer}
            </div>
          ) : null}
        </section>

        <section className="space-y-5">
          {result ? (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <MetricCard label="Classification" value={result.prediction} />
                <MetricCard label="Confidence" value={percent(result.confidence)} />
                <MetricCard label="AI Contribution" value={`${result.ai_contribution}%`} />
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                  <h2 className="text-base font-semibold">Class probabilities</h2>
                  <div className="mt-3 h-64">
                    <ResponsiveContainer>
                      <BarChart data={probabilityData}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                        <YAxis domain={[0, 100]} />
                        <Tooltip />
                        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                          {probabilityData.map((_, index) => (
                            <Cell key={index} fill={colors[index % colors.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                  <h2 className="text-base font-semibold">POS distribution</h2>
                  <div className="mt-3 h-64">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={posData} dataKey="value" nameKey="name" outerRadius={88} label>
                          {posData.map((_, index) => (
                            <Cell key={index} fill={colors[index % colors.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="mb-3 text-lg font-semibold">Linguistic Analysis</h2>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  <MetricCard label="Perplexity" value={numeric(result.linguistic_features.perplexity)} />
                  <MetricCard label="Vocabulary Diversity" value={numeric(result.linguistic_features.vocabulary_diversity)} />
                  <MetricCard label="Average Sentence Length" value={numeric(result.linguistic_features.average_sentence_length)} />
                  <MetricCard label="Burstiness" value={numeric(result.linguistic_features.burstiness)} />
                  <MetricCard label="Readability" value={numeric(result.linguistic_features.readability)} />
                  <MetricCard label="Passive Voice" value={percent(result.linguistic_features.passive_voice)} />
                </div>
              </div>

              <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                <h2 className="text-base font-semibold">Punctuation analysis</h2>
                <div className="mt-3 h-48">
                  <ResponsiveContainer>
                    <BarChart data={punctuationData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#c49a45" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                <h2 className="text-base font-semibold">Why was this text classified as {result.prediction}?</h2>
                <ul className="mt-3 space-y-2 text-sm text-ink/80">
                  {result.explanation.important_sentences.map((item) => (
                    <li key={item.sentence}>- {item.sentence}</li>
                  ))}
                  {result.explanation.important_sentences.length === 0 ? <li>- Text is too short for sentence evidence.</li> : null}
                </ul>
                <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-moss">{result.explanation.method}</div>
              </div>

              <div>
                <h2 className="mb-3 text-lg font-semibold">Highlighted text</h2>
                <HighlightedText text={text} sentences={result.explanation.important_sentences} />
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-ink/10 bg-white p-8 text-center shadow-sm">
              <h2 className="text-xl font-semibold">Analysis results will appear here</h2>
              <p className="mt-2 text-sm text-ink/65">Paste text, run analysis, and review the classification evidence.</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
