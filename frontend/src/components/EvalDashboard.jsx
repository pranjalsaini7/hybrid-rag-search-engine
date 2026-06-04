import { useState, useEffect } from 'react';
import { runEvaluation, listEvalRuns } from '../utils/api';

/**
 * EvalDashboard — Rerendered with the light-theme Stitch design.
 * Visualizes RAGAS evaluation metrics (Faithfulness, Relevancy, Precision, Recall)
 * using harmonic card colors, and logs run history in a structured table.
 */
const DEFAULT_QUESTIONS = `What is the BLEU score of the Transformer?
What attention mechanism does the paper describe? | Multi-head self-attention
How does the model handle sequence transduction?`;

export default function EvalDashboard({ onToast }) {
  const [runs, setRuns] = useState([]);
  const [latestMetrics, setLatestMetrics] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [testQuestions, setTestQuestions] = useState(DEFAULT_QUESTIONS);
  const [evalError, setEvalError] = useState(null);
  const [expandedRun, setExpandedRun] = useState(null);
  const [latestPerQuestion, setLatestPerQuestion] = useState([]);

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
    setEvalError(null);
    onToast?.({ type: 'info', message: `Running evaluation on ${questions.length} questions…` });

    try {
      const result = await runEvaluation(questions);
      setLatestMetrics(result.metrics);
      setLatestPerQuestion(result.per_question || []);

      // Check if all scores are fallback values (0.5) — indicates LLM judge failure
      const m = result.metrics;
      const isFallback = m.faithfulness === 0.5 && m.answer_relevancy === 0.5 &&
                         m.context_precision === 0.5 && m.context_recall === 0.5;
      if (isFallback) {
        setEvalError('All scores returned 50% (fallback). This usually means Ollama is not running. Start Ollama with "ollama serve" and try again.');
        onToast?.({ type: 'error', message: 'Evaluation returned fallback scores — is Ollama running?' });
      } else {
        onToast?.({ type: 'success', message: 'Evaluation complete!' });
      }
      await loadRuns();
    } catch (e) {
      setEvalError(`Evaluation failed: ${e.message}`);
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

      {/* Warning/Error Banner */}
      {evalError && (
        <div className="flex items-start gap-3 px-5 py-4 rounded-2xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/50 animate-fade-up">
          <span className="material-symbols-outlined text-amber-600 dark:text-amber-400 text-lg mt-0.5">warning</span>
          <div>
            <p className="text-xs font-bold text-amber-800 dark:text-amber-300">Evaluation Warning</p>
            <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5 leading-relaxed">{evalError}</p>
          </div>
          <button
            className="ml-auto text-amber-500 hover:text-amber-700 dark:hover:text-amber-300 transition-colors"
            onClick={() => setEvalError(null)}
          >
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {/* Test Questions Area */}
      <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-bold text-primary dark:text-white">Test Questions Dataset</h3>
          <span className="text-[10px] font-mono text-secondary dark:text-slate-500">
            {testQuestions.trim() ? testQuestions.trim().split('\n').filter(Boolean).length : 0} question{testQuestions.trim().split('\n').filter(Boolean).length !== 1 ? 's' : ''}
          </span>
        </div>
        <p className="text-xs text-secondary dark:text-slate-400 mb-4 leading-relaxed">
          Provide questions to run evaluation. Optionally include ground truths after a pipe character (<code className="bg-surface-container-low dark:bg-slate-800 px-1 rounded">|</code>) to calibrate retrieval recall.
        </p>
        <textarea
          value={testQuestions}
          onChange={(e) => setTestQuestions(e.target.value)}
          placeholder="Enter one question per line…"
          className="w-full min-h-[140px] p-4 bg-surface-container-low dark:bg-slate-950 border border-outline-variant/60 dark:border-slate-800 rounded-xl text-xs focus:ring-1 focus:ring-primary/30 focus:border-primary/30 outline-none transition-all resize-none font-mono leading-relaxed text-primary dark:text-slate-200"
        />
      </div>

      {/* Running Progress Indicator */}
      {isRunning && (
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-6 shadow-sm animate-fade-up">
          <div className="flex items-center gap-3 mb-3">
            <span className="animate-spin text-primary">⏳</span>
            <span className="text-xs font-bold text-primary dark:text-white">Running Evaluation Pipeline…</span>
          </div>
          <p className="text-[11px] text-secondary dark:text-slate-400 mb-3">Each question runs through the full RAG pipeline (retrieve → rerank → generate → LLM judge). This may take 15-60 seconds.</p>
          <div className="w-full h-1.5 bg-primary-container/20 dark:bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full animate-pulse" style={{ width: '70%' }} />
          </div>
        </div>
      )}

      {/* Latest Per-Question Results */}
      {latestPerQuestion.length > 0 && !isRunning && (
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-6 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-primary dark:text-white">Latest Run — Per-Question Breakdown</h3>
            <button
              className="text-[10px] text-primary dark:text-primary-container font-bold hover:underline"
              onClick={() => setLatestPerQuestion([])}
            >
              Hide
            </button>
          </div>
          <div className="space-y-3">
            {latestPerQuestion.map((pq, idx) => (
              <div key={idx} className="bg-surface-container-low dark:bg-slate-950 border border-outline-variant/30 dark:border-slate-800 rounded-xl p-4">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <p className="text-xs font-semibold text-primary dark:text-slate-200 flex-1">
                    <span className="text-secondary dark:text-slate-500 mr-1.5">Q{idx+1}.</span>
                    {pq.question}
                  </p>
                  {pq.error ? (
                    <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/20 px-2 py-0.5 rounded-md shrink-0">Error</span>
                  ) : (
                    <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/20 px-2 py-0.5 rounded-md shrink-0">✓ Scored</span>
                  )}
                </div>
                {pq.answer && (
                  <p className="text-[11px] text-secondary dark:text-slate-400 leading-relaxed line-clamp-3 mb-2">
                    <span className="font-bold text-primary/70 dark:text-slate-300">A: </span>{pq.answer}
                  </p>
                )}
                {pq.error && (
                  <p className="text-[11px] text-rose-600 dark:text-rose-400 font-mono">{pq.error}</p>
                )}
                {pq.scores && Object.keys(pq.scores).length > 0 && (
                  <div className="flex gap-4 mt-2">
                    {Object.entries(pq.scores).map(([key, val]) => (
                      <span key={key} className={`text-[10px] font-bold ${
                        val >= 0.8 ? 'text-emerald-600 dark:text-emerald-400' :
                        val >= 0.5 ? 'text-amber-600 dark:text-amber-400' :
                        'text-rose-600 dark:text-rose-400'
                      }`}>
                        {key.replace('_', ' ')}: {(val * 100).toFixed(0)}%
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History logs table */}
      {runs.length > 0 && (
        <div className="bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800/80 rounded-2xl p-6 shadow-sm overflow-hidden">
          <h3 className="text-sm font-bold text-primary dark:text-white mb-4">Historical Evaluations</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-outline-variant/60 dark:border-slate-800/80 text-secondary dark:text-slate-400 uppercase tracking-wider font-semibold">
                  <th className="pb-3.5 pl-2"></th>
                  <th className="pb-3.5">Run Timestamp</th>
                  <th className="pb-3.5">Faithfulness</th>
                  <th className="pb-3.5">Answer Relevancy</th>
                  <th className="pb-3.5">Context Precision</th>
                  <th className="pb-3.5">Context Recall</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20 dark:divide-slate-800/40">
                {runs.map((run) => {
                  const isExpanded = expandedRun === run.id;
                  return (
                    <tr
                      key={run.id}
                      className="hover:bg-[#f9f9fb]/50 dark:hover:bg-slate-850/50 transition-colors cursor-pointer"
                      onClick={() => setExpandedRun(isExpanded ? null : run.id)}
                    >
                      <td className="py-4 pl-2 w-6">
                        <span className={`material-symbols-outlined text-sm text-secondary dark:text-slate-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
                          chevron_right
                        </span>
                      </td>
                      <td className="py-4 font-semibold text-primary dark:text-slate-200">{formatDate(run.timestamp)}</td>
                      <td className={`py-4 font-bold ${run.metrics.faithfulness >= 0.8 ? 'text-emerald-600 dark:text-emerald-400' : run.metrics.faithfulness >= 0.5 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {formatScore(run.metrics.faithfulness)}%
                      </td>
                      <td className={`py-4 font-bold ${run.metrics.answer_relevancy >= 0.8 ? 'text-emerald-600 dark:text-emerald-400' : run.metrics.answer_relevancy >= 0.5 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {formatScore(run.metrics.answer_relevancy)}%
                      </td>
                      <td className={`py-4 font-bold ${run.metrics.context_precision >= 0.8 ? 'text-emerald-600 dark:text-emerald-400' : run.metrics.context_precision >= 0.5 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {formatScore(run.metrics.context_precision)}%
                      </td>
                      <td className={`py-4 font-bold ${run.metrics.context_recall >= 0.8 ? 'text-emerald-600 dark:text-emerald-400' : run.metrics.context_recall >= 0.5 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {formatScore(run.metrics.context_recall)}%
                      </td>
                    </tr>
                  );
                })}
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
          No evaluation runs recorded. Click <strong>Run Evaluation</strong> above to score your RAG pipeline.
        </div>
      )}
    </div>
  );
}
