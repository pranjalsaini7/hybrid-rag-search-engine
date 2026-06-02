import { useState } from 'react';

/**
 * SourcePanel — Revamped citations pane matching the Google Stitch design.
 * Features identified count badges, page headers, custom relevance rating bars,
 * and expandable excerpt text. Clicking on index badges in chat scrolls here.
 */
export default function SourcePanel({ sources = [], isCollapsed = false, onToggle }) {
  const [expandedIdx, setExpandedIdx] = useState(null);

  if (isCollapsed) {
    return (
      <button
        className="fixed right-6 top-20 w-10 h-10 bg-white dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800 hover:bg-primary-container/10 hover:text-primary rounded-full shadow-md flex items-center justify-center z-40 transition-all outline-none animate-fade-up select-none"
        onClick={onToggle}
        title="Show citations panel"
      >
        <span className="material-symbols-outlined text-secondary dark:text-slate-400">menu_book</span>
      </button>
    );
  }

  const formatRelevanceScore = (score) => {
    return (score * 100).toFixed(0);
  };

  return (
    <aside className="w-80 flex flex-col p-6 bg-sidebar dark:bg-slate-950 border-l border-outline-variant/50 dark:border-slate-800 shrink-0 h-full animate-fade-up select-none">
      {/* Panel Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2 text-secondary dark:text-slate-400">
          <span className="material-symbols-outlined text-lg">temp_preferences_custom</span>
          <h2 className="font-label-caps text-xs uppercase tracking-wider font-bold">
            Citations &amp; Sources
          </h2>
        </div>
        <button
          className="text-secondary/70 dark:text-slate-500 hover:text-primary dark:hover:text-white outline-none transition-colors"
          onClick={onToggle}
          title="Collapse panel"
        >
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      {/* Identified Count Badge */}
      <div className="mb-6">
        <span className="bg-primary-container/15 dark:bg-primary-container/10 text-primary dark:text-primary-container text-[10px] font-bold px-3 py-1.5 rounded-lg uppercase tracking-wider select-none border border-primary-container/10">
          {sources.length} {sources.length === 1 ? 'source' : 'sources'} identified
        </span>
      </div>

      {/* Source Cards List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-5 pr-1">
        {sources.map((src, i) => {
          const isExpanded = expandedIdx === i;
          const content = src.chunk_text || '';
          const needsTruncate = content.length > 200;

          return (
            <div
              key={i}
              id={`citation-card-${i}`}
              className="bg-white dark:bg-slate-900 border border-outline-variant/40 dark:border-slate-800/80 rounded-2xl p-5 hover:shadow-md dark:hover:shadow-none transition-all duration-200 group cursor-default relative"
            >
              {/* Card Header */}
              <div className="flex justify-between items-start mb-3">
                <span className="text-[9px] font-bold text-primary dark:text-primary-container bg-primary-container/15 dark:bg-primary-container/10 border border-primary-container/10 px-2 py-0.5 rounded-md uppercase">
                  Page {src.page_number || 'Unknown'}
                </span>
                
                {/* Score badge */}
                {src.relevance_score && (
                  <span className="text-[9px] font-semibold text-secondary dark:text-slate-400 bg-surface-container-low dark:bg-slate-950 border border-transparent dark:border-slate-800 px-1.5 py-0.5 rounded">
                    Match: {formatRelevanceScore(src.relevance_score)}%
                  </span>
                )}
              </div>

              {/* relevance score visual bar */}
              {src.relevance_score && (
                <div className="w-full bg-surface-container-high dark:bg-slate-800 h-1 rounded-full overflow-hidden mb-3">
                  <div
                    className="bg-primary dark:bg-primary h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(src.relevance_score * 100, 5)}%` }}
                  />
                </div>
              )}

              {/* Excerpt Text */}
              <p
                className={`text-[12px] leading-relaxed text-on-surface dark:text-slate-300 italic mb-4 transition-all duration-200 ${
                  isExpanded ? '' : 'line-clamp-4'
                }`}
              >
                "{content}"
              </p>

              {/* Expand Text Action */}
              {needsTruncate && (
                <button
                  className="text-[10px] text-primary hover:text-primary/80 font-semibold mb-4 outline-none block"
                  onClick={() => setExpandedIdx(isExpanded ? null : i)}
                >
                  {isExpanded ? 'Show Less' : 'Read Full Excerpt'}
                </button>
              )}

              {/* File Info Footer */}
              <div className="flex items-center gap-2 text-[10px] text-secondary dark:text-slate-400 font-bold border-t border-outline-variant/20 dark:border-slate-800 pt-3 select-none">
                <span className="material-symbols-outlined text-[14px] text-red-500/70 dark:text-red-400/80">
                  description
                </span>
                <span className="truncate" title={src.document_name}>
                  {src.document_name}
                </span>
              </div>
            </div>
          );
        })}

        {sources.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center select-none text-secondary dark:text-slate-500">
            <span className="material-symbols-outlined text-2xl opacity-30 mb-2">
              menu_book
            </span>
            <p className="text-[11px] max-w-[180px] leading-relaxed">
              Retrieved context excerpts will appear here once you ask a question.
            </p>
          </div>
        )}
      </div>

      {/* Footer "View all sources" button */}
      {sources.length > 0 && (
        <button
          className="w-full mt-6 py-3 border border-outline-variant/40 dark:border-slate-800 rounded-xl hover:bg-surface-container-low dark:hover:bg-slate-900/40 transition-colors text-[11px] font-bold text-primary dark:text-slate-300 flex items-center justify-center gap-1.5 group outline-none select-none bg-white dark:bg-slate-900"
          onClick={() => alert('All citations are listed above.')}
        >
          <span className="material-symbols-outlined text-base">list</span>
          View all sources
          <span className="material-symbols-outlined text-xs group-hover:translate-x-0.5 transition-transform">
            arrow_forward
          </span>
        </button>
      )}
    </aside>
  );
}
