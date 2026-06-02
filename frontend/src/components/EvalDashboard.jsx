import { useState, useEffect } from 'react';
import { runEvaluation, listEvalRuns } from '../utils/api';

/**
 * EvalDashboard — Rerendered with the light-theme Stitch design.
 * Visualizes RAGAS evaluation metrics (Faithfulness, Relevancy, Precision, Recall)
 * using harmonic card colors, and logs run history in a structured table.
 */
export default function EvalDashboard({ onToast }) {
  const [runs, setRuns] = useState([]);
  const [latestMetrics, setLatestMetrics] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [testQuestions, setTestQuestions] = useState('');

  useEffect(() => {
    loadRuns();
  }, []);

  const loadRuns = async () => {
    try {
      const data = await listEvalRuns();
      setRuns(data.runs || []);
      if (data.runs && data.runs.length > 0) {
        setLatestMetrics(data.runs[0].metrics);
      }
    } catch (e) {
      console.error('Failed to load eval runs:', e);
    }
  };

  const handleRunEval = async () => {
    const lines = testQuestions.trim().split('\n').filter(Boolean);
    if (lines.length === 0) {
      onToast?.({ type: 'error', message: 'Enter at least one question.' });
      return;
    }

    const questions = lines.map((line) => {
      const parts = line.split('|');
      return {
        question: parts[0].trim(),
        ground_truth: parts[1]?.trim() || '',
      };
    });

    setIsRunning(true);
    onToast?.({ type: 'info', message: `Running evaluation on ${questions.length} questions…` });

    try {
      const result = await runEvaluation(questions);
      setLatestMetrics(result.metrics);
      onToast?.({ type: 'success', message: 'Evaluation complete!' });
      await loadRuns();
    } catch (e) {
      onToast?.({ type: 'error', message: `Evaluation failed: ${e.message}` });
    } finally {
      setIsRunning(false);
    }
  };

  const formatScore = (score) => (score * 100).toFixed(0);

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-10 py-4 select-none">
      {/* Dashboard Header */}
      <div className="flex items-center justify-between border-b border-outline-variant/60 dark:border-slate-800/80 pb-5 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-primary flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">query_stats</span>
            RAGAS Evaluation
          </h2>
          <p className="text-xs text-secondary dark:text-slate-400 mt-1">
            Analyze RAG pipeline performance (faithfulness, relevancy, and context retrieval precision/recall)
          </p>
        </div>
        <button
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold shadow-md transition-all outline-none ${
            isRunning || !testQuestions.trim()
              ? 'bg-surface-container-low dark:bg-slate-900 text-secondary dark:text-slate-500 cursor-not-allowed border border-outline-variant/30 dark:border-slate-800'
              : 'bg-primary hover:bg-primary/95 text-white shadow-sm hover:scale-[1.01]'
          }`}
          onClick={handleRunEval}
          disabled={isRunning || !testQuestions.trim()}
        >
          {isRunning ? (
            <>
              <span className="animate-spin text-sm select-none">⏳</span>
              Running Eval...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined text-base">play_arrow</span>
              Run Evaluation
            </>
          )}
        </button>
      </div>

      {/* Score Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 animate-fade-up">
        {/* Card: Faithfulness */}
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-5 hover:shadow-sm transition-shadow">
          <div className="flex justify-between items-start mb-4">
            <span className="text-[10px] font-bold text-primary dark:text-primary-container bg-primary-container/20 dark:bg-primary-container/10 px-2 py-0.5 rounded-md uppercase border border-primary/10">
              Grounding
            </span>
            <span className="material-symbols-outlined text-secondary dark:text-slate-400 text-lg">verified_user</span>
          </div>
          <div className="text-2xl font-bold text-primary dark:text-white">
            {latestMetrics ? `${formatScore(latestMetrics.faithfulness)}%` : '—'}
          </div>
          <div className="text-[11px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider mt-1.5 mb-3">
            Faithfulness
          </div>
          <div className="w-full bg-primary-container/20 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-primary h-full rounded-full transition-all duration-300"
              style={{ width: `${latestMetrics ? latestMetrics.faithfulness * 100 : 0}%` }}
            />
          </div>
        </div>

        {/* Card: Answer Relevancy */}
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-5 hover:shadow-sm transition-shadow">
          <div className="flex justify-between items-start mb-4">
            <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/20 px-2 py-0.5 rounded-md uppercase border border-emerald-500/10">
              Response
            </span>
            <span className="material-symbols-outlined text-secondary dark:text-slate-400 text-lg">question_answer</span>
          </div>
          <div className="text-2xl font-bold text-primary dark:text-white">
            {latestMetrics ? `${formatScore(latestMetrics.answer_relevancy)}%` : '—'}
          </div>
          <div className="text-[11px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider mt-1.5 mb-3">
            Answer Relevancy
          </div>
          <div className="w-full bg-emerald-50/30 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-emerald-500 h-full rounded-full transition-all duration-300"
              style={{ width: `${latestMetrics ? latestMetrics.answer_relevancy * 100 : 0}%` }}
            />
          </div>
        </div>

        {/* Card: Context Precision */}
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-5 hover:shadow-sm transition-shadow">
          <div className="flex justify-between items-start mb-4">
            <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 px-2 py-0.5 rounded-md uppercase border border-amber-500/10">
              Search Accuracy
            </span>
            <span className="material-symbols-outlined text-secondary dark:text-slate-400 text-lg">gps_fixed</span>
          </div>
          <div className="text-2xl font-bold text-primary dark:text-white">
            {latestMetrics ? `${formatScore(latestMetrics.context_precision)}%` : '—'}
          </div>
          <div className="text-[11px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider mt-1.5 mb-3">
            Context Precision
          </div>
          <div className="w-full bg-amber-50/30 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-amber-500 h-full rounded-full transition-all duration-300"
              style={{ width: `${latestMetrics ? latestMetrics.context_precision * 100 : 0}%` }}
            />
          </div>
        </div>

        {/* Card: Context Recall */}
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-5 hover:shadow-sm transition-shadow">
          <div className="flex justify-between items-start mb-4">
            <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/20 px-2 py-0.5 rounded-md uppercase border border-rose-500/10">
              Search Coverage
            </span>
            <span className="material-symbols-outlined text-secondary dark:text-slate-400 text-lg">troubleshoot</span>
          </div>
          <div className="text-2xl font-bold text-primary dark:text-white">
            {latestMetrics ? `${formatScore(latestMetrics.context_recall)}%` : '—'}
          </div>
          <div className="text-[11px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider mt-1.5 mb-3">
            Context Recall
          </div>
          <div className="w-full bg-rose-50/30 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-rose-500 h-full rounded-full transition-all duration-300"
              style={{ width: `${latestMetrics ? latestMetrics.context_recall * 100 : 0}%` }}
            />
          </div>
        </div>
      </div>

      {/* Test Questions Area */}
      <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-6 shadow-sm">
        <h3 className="text-sm font-bold text-primary dark:text-white mb-1">Test Questions Dataset</h3>
        <p className="text-xs text-secondary dark:text-slate-400 mb-4 leading-relaxed">
          Provide questions to run evaluation. Optionally include ground truths after a pipe character (|) to calibrate retrieval recall.
        </p>
        <textarea
          value={testQuestions}
          onChange={(e) => setTestQuestions(e.target.value)}
          placeholder={`What is the BLEU score of the Transformer?\nWhat attention mechanism does the paper describe? | Multi-head self-attention\nHow does the model handle sequence transduction?`}
          className="w-full min-h-[140px] p-4 bg-surface-container-low dark:bg-slate-950 border border-outline-variant/60 dark:border-slate-800 rounded-xl text-xs focus:ring-1 focus:ring-primary/30 focus:border-primary/30 outline-none transition-all resize-none font-mono leading-relaxed text-primary dark:text-slate-200"
        />
      </div>

      {/* History logs table */}
      {runs.length > 0 && (
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-6 shadow-sm overflow-hidden">
          <h3 className="text-sm font-bold text-primary dark:text-white mb-4">Historical Evaluations</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-outline-variant/60 dark:border-slate-800/80 text-secondary dark:text-slate-400 uppercase tracking-wider font-semibold">
                  <th className="pb-3.5 pl-2">Run Timestamp</th>
                  <th className="pb-3.5">Faithfulness</th>
                  <th className="pb-3.5">Answer Relevancy</th>
                  <th className="pb-3.5">Context Precision</th>
                  <th className="pb-3.5">Context Recall</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20 dark:divide-slate-800/40">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-[#f9f9fb]/50 dark:hover:bg-slate-850/50 transition-colors">
                    <td className="py-4 pl-2 font-semibold text-primary dark:text-slate-200">{formatDate(run.timestamp)}</td>
                    <td className="py-4 font-bold text-primary dark:text-primary-container">{formatScore(run.metrics.faithfulness)}%</td>
                    <td className="py-4 font-bold text-emerald-600 dark:text-emerald-400">{formatScore(run.metrics.answer_relevancy)}%</td>
                    <td className="py-4 font-bold text-amber-600 dark:text-amber-400">{formatScore(run.metrics.context_precision)}%</td>
                    <td className="py-4 font-bold text-rose-600 dark:text-rose-400">{formatScore(run.metrics.context_recall)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {runs.length === 0 && (
        <div className="text-center text-xs text-secondary dark:text-slate-400 py-16 border border-dashed border-outline-variant/60 dark:border-slate-800/85 rounded-2xl bg-white dark:bg-slate-900 select-none">
          <span className="material-symbols-outlined text-3xl opacity-35 mb-2 block text-primary">
            assignment_turned_in
          </span>
          No evaluation runs recorded. Enter test questions above and run evaluation to save logs.
        </div>
      )}
    </div>
  );
}
