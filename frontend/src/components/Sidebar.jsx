import { useState, useRef } from 'react';

/**
 * Sidebar — Redesigned as the Knowledge Base Left Sidebar.
 * Displays upload PDF button (with drag-and-drop), search docs input,
 * and list of uploaded documents with hover delete actions and expandable summaries.
 */
export default function Sidebar({
  documents = [],
  isUploading = false,
  uploadProgress = 0,
  onUpload,
  onDeleteDoc,
  docCount = 0,
  isHealthy = false,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [dragover, setDragover] = useState(false);
  const [expandedDocId, setExpandedDocId] = useState(null);
  const fileInputRef = useRef(null);

  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getFileIcon = (fileType) => {
    switch (fileType) {
      case 'xlsx':
      case 'xls':
        return 'table_chart';
      case 'pdf':
      default:
        return 'description';
    }
  };

  const getIconColorClass = (fileType) => {
    switch (fileType) {
      case 'xlsx':
      case 'xls':
        return 'text-green-600/80';
      case 'pdf':
      default:
        return 'text-primary/80';
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragover(true);
  };

  const handleDragLeave = () => {
    setDragover(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragover(false);
    if (onUpload) onUpload(e.dataTransfer.files);
  };

  const handleFileChange = (e) => {
    if (onUpload) onUpload(e.target.files);
  };

  const toggleExpand = (docId) => {
    setExpandedDocId(expandedDocId === docId ? null : docId);
  };

  return (
    <aside className="w-64 border-r border-outline-variant/50 dark:border-slate-800 flex flex-col p-5 bg-sidebar dark:bg-slate-950 shrink-0 h-full relative">
      <h2 className="font-label-caps text-secondary dark:text-slate-400 text-xs uppercase tracking-wider mb-6 select-none font-bold">
        Knowledge Base
      </h2>

      {/* Upload Zone Button */}
      <div
        className={`w-full flex flex-col items-center justify-center gap-1 border-2 border-dashed rounded-xl py-4 transition-all mb-6 cursor-pointer group select-none ${
          dragover
            ? 'border-primary bg-primary-container/15'
            : 'border-outline-variant/60 dark:border-slate-800 hover:bg-surface-container-low/50 hover:border-primary/45'
        }`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-center gap-2 text-primary group-hover:scale-105 transition-transform duration-200">
          <span className="material-symbols-outlined">add_box</span>
          <span className="font-bold text-xs">Upload PDF</span>
        </div>
        <span className="text-[10px] text-secondary dark:text-slate-500">or drag and drop</span>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.xlsx,.xls"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {/* Upload Progress */}
      {isUploading && (
        <div className="mb-6 p-3 bg-primary-container/10 dark:bg-primary-container/5 border border-primary-container/20 dark:border-primary/10 rounded-xl animate-fade-up">
          <div className="flex justify-between text-[10px] text-primary dark:text-primary-container font-bold mb-1.5">
            <span>Processing document...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-primary-container/25 dark:bg-primary-container/10 h-1 rounded-full overflow-hidden">
            <div
              className="bg-primary h-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Search Bar */}
      <div className="relative mb-6">
        <span className="material-symbols-outlined absolute left-3 top-2 text-secondary dark:text-slate-400 text-sm">
          search
        </span>
        <input
          className="w-full bg-surface-container-low dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800 rounded-full pl-9 pr-10 py-1.5 text-xs focus:ring-1 focus:ring-primary/30 focus:border-primary/30 outline-none transition-all dark:text-slate-200"
          placeholder="Search documents..."
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {searchTerm && (
          <button
            className="absolute right-3.5 top-2 text-[10px] text-secondary/60 dark:text-slate-500 hover:text-primary dark:hover:text-white outline-none"
            onClick={() => setSearchTerm('')}
          >
            ✕
          </button>
        )}
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 mb-4 pr-1">
        {filteredDocs.map((doc) => {
          const isExpanded = expandedDocId === doc.id;
          return (
            <div
              key={doc.id}
              className={`flex flex-col p-3 rounded-xl cursor-pointer border group transition-all duration-200 relative ${
                isExpanded
                  ? 'bg-primary-container/10 border-primary/55 dark:border-primary/55 shadow-sm'
                  : 'bg-white dark:bg-slate-900 border-outline-variant/60 dark:border-slate-800/80 hover:bg-surface-container-low/50 hover:border-primary/30'
              }`}
              onClick={() => toggleExpand(doc.id)}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`material-symbols-outlined shrink-0 ${getIconColorClass(
                    doc.file_type
                  )}`}
                >
                  {getFileIcon(doc.file_type)}
                </span>
                <div className="flex-1 min-w-0 pr-6">
                  <p className="truncate text-xs font-semibold text-primary dark:text-slate-200">
                    {doc.filename}
                  </p>
                  <p className="text-[10px] text-secondary dark:text-slate-400">
                    {doc.chunk_count} chunks • {doc.file_type.toUpperCase()}
                  </p>
                </div>

                {/* Delete button (displays on hover) */}
                <button
                  className="absolute right-3 top-3.5 opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 transition-opacity p-0.5 rounded outline-none"
                  onClick={(e) => {
                    e.stopPropagation(); // Avoid expanding card
                    onDeleteDoc(doc.id, doc.filename);
                  }}
                  title="Delete document"
                >
                  <span className="material-symbols-outlined text-[16px]">
                    delete
                  </span>
                </button>
              </div>

              {/* Collapsible Semantic Summary */}
              {isExpanded && (
                <div className="mt-2.5 pt-2 border-t border-primary-container/20 dark:border-primary-container/10 text-[11px] leading-relaxed text-secondary dark:text-slate-400 italic animate-fade-up">
                  {doc.summary || 'Indexing completed. No summary available.'}
                </div>
              )}
            </div>
          );
        })}

        {filteredDocs.length === 0 && (
          <div className="text-center text-[11px] text-secondary dark:text-slate-500 py-10">
            No papers found.
          </div>
        )}
      </div>

      {/* Sidebar Footer Status Indicator */}
      <div className="pt-4 border-t border-outline-variant/60 dark:border-slate-800/80 select-none shrink-0">
        <div className="flex items-center justify-between p-2 hover:bg-surface-container-low/50 dark:hover:bg-slate-900/40 rounded-lg transition-colors cursor-default">
          <div className="flex items-center gap-3">
            <span
              className={`w-2 h-2 rounded-full transition-all duration-300 ${
                isHealthy
                  ? 'bg-emerald-500 shadow-sm shadow-emerald-200'
                  : 'bg-red-500 shadow-sm shadow-red-200 animate-pulse'
              }`}
            />
            <span className="text-[11px] font-semibold text-secondary dark:text-slate-400">
              {isHealthy ? 'System Online' : 'Connecting to local LLM...'}
            </span>
          </div>
          <span className="text-[10px] font-bold text-primary dark:text-primary-container bg-primary-container/20 dark:bg-primary-container/10 px-2.5 py-0.5 rounded-full border border-primary/15">
            {docCount} {docCount === 1 ? 'Paper' : 'Papers'}
          </span>
        </div>
      </div>
    </aside>
  );
}
