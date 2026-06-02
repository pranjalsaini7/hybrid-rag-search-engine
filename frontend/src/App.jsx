import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import SourcePanel from './components/SourcePanel';
import EvalDashboard from './components/EvalDashboard';
import { fetchHealth, uploadDocument, listDocuments, deleteDocument } from './utils/api';

function App() {
  const [activePage, setActivePage] = useState('chat');
  const [sources, setSources] = useState([]);
  const [isSourceCollapsed, setIsSourceCollapsed] = useState(false);
  const [docCount, setDocCount] = useState(0);
  const [isHealthy, setIsHealthy] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [sessionId] = useState(() => `session-${Date.now()}`);

  // Shared Documents State
  const [documents, setDocuments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Top Header Functional State
  const [isDarkMode, setIsDarkMode] = useState(() => {
    return localStorage.getItem('theme') === 'dark';
  });
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [chatResetKey, setChatResetKey] = useState(0);
  const [notifications, setNotifications] = useState([
    { id: 1, text: 'System initialized and online.', time: 'Just now', type: 'info' },
    { id: 2, text: 'Connected to local Ollama LLaMA 3 model.', time: 'Just now', type: 'info' }
  ]);

  // Add notification event
  const addNotification = useCallback((text, type = 'info') => {
    setNotifications((prev) => [
      { id: Date.now(), text, time: 'Just now', type },
      ...prev,
    ]);
  }, []);

  // Sync Dark Mode state to HTML document
  useEffect(() => {
    const root = document.documentElement;
    if (isDarkMode) {
      root.classList.add('dark');
      root.classList.remove('light');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDarkMode]);

  const refreshDocuments = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocuments(data.documents || []);
      setDocCount(data.total || 0);
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  }, []);

  // Health check
  useEffect(() => {
    const check = async () => {
      try {
        const data = await fetchHealth();
        setIsHealthy(data.status === 'healthy');
      } catch {
        setIsHealthy(false);
      }
    };
    check();
    refreshDocuments();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, [refreshDocuments]);

  // Toast notifications
  const addToast = useCallback((toast) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { ...toast, id }]);
    addNotification(toast.message, toast.type === 'success' ? 'success' : 'error');
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, [addNotification]);

  const handleUpload = useCallback(async (files) => {
    if (!files || files.length === 0) return;

    for (const file of files) {
      setIsUploading(true);
      setUploadProgress(10);
      addNotification(`Uploading file "${file.name}"...`, 'info');

      try {
        // Simulate progress
        const progressInterval = setInterval(() => {
          setUploadProgress((prev) => Math.min(prev + 15, 85));
        }, 300);

        const result = await uploadDocument(file);

        clearInterval(progressInterval);
        setUploadProgress(100);

        addToast({
          type: 'success',
          message: `"${result.filename}" uploaded — ${result.chunk_count} chunks`,
        });

        setTimeout(() => {
          setIsUploading(false);
          setUploadProgress(0);
        }, 500);

        await refreshDocuments();
      } catch (e) {
        setIsUploading(false);
        setUploadProgress(0);
        addToast({ type: 'error', message: e.message });
      }
    }
  }, [addToast, refreshDocuments, addNotification]);

  const handleDeleteDoc = useCallback(async (docId, filename) => {
    if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;

    try {
      await deleteDocument(docId);
      addToast({ type: 'success', message: `Deleted "${filename}"` });
      await refreshDocuments();
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    }
  }, [addToast, refreshDocuments]);

  const handleSourcesUpdate = useCallback((newSources) => {
    setSources(newSources);
  }, []);

  return (
    <div className="flex flex-col w-screen h-screen overflow-hidden bg-background dark:bg-slate-950 text-on-surface dark:text-slate-200">
      {/* Top Header */}
      <header className="h-16 border-b border-outline-variant/60 dark:border-slate-800/80 flex items-center justify-between px-6 sticky top-0 z-50 bg-background/85 dark:bg-slate-900/85 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-8 h-full">
          <div className="flex items-center gap-2 select-none">
            <div className="w-8 h-8 flex items-center justify-center bg-primary rounded-xl border border-primary/20 shadow-sm shadow-primary/10">
              <span className="material-symbols-outlined text-white text-lg">auto_awesome</span>
            </div>
            <span className="font-bold text-sm tracking-tight text-on-surface dark:text-white uppercase tracking-wider">RAG Assistant</span>
          </div>
          
          <nav className="hidden md:flex gap-3 items-center">
            <button
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all outline-none border ${
                activePage === 'chat'
                  ? 'border-primary/50 text-primary bg-primary-container/15 dark:border-primary/50 dark:text-primary-container'
                  : 'border-transparent text-secondary dark:text-slate-400 hover:text-primary hover:bg-surface-container-low/50'
              }`}
              onClick={() => setActivePage('chat')}
            >
              Chat
            </button>
            <button
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all outline-none border ${
                activePage === 'evaluation'
                  ? 'border-primary/50 text-primary bg-primary-container/15 dark:border-primary/50 dark:text-primary-container'
                  : 'border-transparent text-secondary dark:text-slate-400 hover:text-primary hover:bg-surface-container-low/50'
              }`}
              onClick={() => setActivePage('evaluation')}
            >
              Evaluation
            </button>
          </nav>
        </div>

        <div className="flex items-center gap-4 relative">
          <div className="relative hidden md:flex items-center">
            <span className="material-symbols-outlined absolute left-3.5 text-secondary dark:text-slate-400 text-[18px]">search</span>
            <input
              className="bg-surface-container-low dark:bg-slate-900 border border-outline-variant/60 dark:border-slate-800 rounded-full pl-10 pr-12 py-2 text-xs w-64 focus:ring-1 focus:ring-primary/30 focus:border-primary/30 outline-none transition-all dark:text-slate-200"
              placeholder="Search insights..."
              type="text"
            />
            <span className="absolute right-3.5 text-[9px] text-secondary/60 dark:text-slate-500 border border-outline-variant/65 dark:border-slate-800 px-1.5 py-0.5 rounded select-none font-mono">⌘K</span>
          </div>

          {/* Theme Mode Toggle Button */}
          <button 
            className="w-8 h-8 flex items-center justify-center text-primary border border-outline-variant rounded-full hover:bg-surface-container-low dark:hover:bg-slate-800 transition-colors outline-none"
            onClick={() => setIsDarkMode(!isDarkMode)}
            title={isDarkMode ? 'Toggle Light Mode' : 'Toggle Dark Mode'}
          >
            <span className="material-symbols-outlined text-[18px]">
              {isDarkMode ? 'light_mode' : 'dark_mode'}
            </span>
          </button>

          {/* Notifications Button */}
          <button 
            className={`w-8 h-8 flex items-center justify-center rounded-full border transition-all outline-none relative ${
              isNotificationsOpen 
                ? 'bg-primary-container/20 border-primary text-primary' 
                : 'text-primary border-outline-variant hover:bg-surface-container-low dark:hover:bg-slate-800'
            }`}
            onClick={() => {
              setIsNotificationsOpen(!isNotificationsOpen);
              setIsProfileOpen(false);
            }}
            title="System events"
          >
            <span className="material-symbols-outlined text-[18px]">notifications</span>
            {notifications.length > 0 && (
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full"></span>
            )}
          </button>

          {/* Profile Button */}
          <button 
            className={`w-8 h-8 rounded-full font-bold text-xs flex items-center justify-center transition-all select-none outline-none ${
              isProfileOpen 
                ? 'bg-primary border-primary text-white shadow-sm ring-2 ring-primary-container/30 dark:ring-primary/20'
                : 'bg-primary text-white border border-primary shadow-sm hover:opacity-90'
            }`}
            onClick={() => {
              setIsProfileOpen(!isProfileOpen);
              setIsNotificationsOpen(false);
            }}
            title="Profile & Settings"
          >
            RA
          </button>

          {/* Notifications Dropdown menu */}
          {isNotificationsOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsNotificationsOpen(false)} />
              <div className="absolute top-12 right-10 w-80 bg-white dark:bg-slate-900 border border-outline-variant/50 dark:border-slate-800 rounded-2xl shadow-xl p-4 z-50 animate-fade-up select-none">
                <div className="flex justify-between items-center border-b border-outline-variant/35 dark:border-slate-800 pb-2 mb-3">
                  <span className="text-[10px] font-bold text-primary dark:text-white uppercase tracking-wider">System Events</span>
                  <button 
                    className="text-[9px] text-primary dark:text-primary-container font-bold hover:underline"
                    onClick={() => setNotifications([])}
                  >
                    Clear all
                  </button>
                </div>
                <div className="max-h-60 overflow-y-auto custom-scrollbar space-y-2.5 pr-0.5">
                  {notifications.length === 0 ? (
                    <div className="text-center py-8 text-xs text-secondary/60 dark:text-slate-500">No recent events.</div>
                  ) : (
                    notifications.map((n) => (
                      <div key={n.id} className="text-[11px] leading-relaxed text-secondary dark:text-slate-400 border-b border-outline-variant/20 dark:border-slate-800 pb-2 last:border-none">
                        <p className="text-primary dark:text-slate-200 font-medium">{n.text}</p>
                        <span className="text-[9px] text-secondary/50 dark:text-slate-500 font-bold">{n.time}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}

          {/* Profile Dropdown menu */}
          {isProfileOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsProfileOpen(false)} />
              <div className="absolute top-12 right-0 w-80 bg-white dark:bg-slate-900 border border-outline-variant/50 dark:border-slate-800 rounded-2xl shadow-xl p-5 z-50 animate-fade-up select-none">
                {/* User Block */}
                <div className="flex items-center gap-3 border-b border-outline-variant/30 dark:border-slate-800 pb-3.5 mb-4">
                  <div className="w-10 h-10 bg-primary-container/20 dark:bg-primary-container/10 text-primary dark:text-primary-container rounded-full font-bold text-sm flex items-center justify-center border border-primary-container/20 dark:border-primary/20">
                    RA
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-primary dark:text-white">RAG Administrator</h4>
                    <p className="text-[10px] text-secondary dark:text-slate-400">System operator</p>
                  </div>
                </div>

                {/* Info items */}
                <div className="space-y-4 mb-5">
                  <div>
                    <span className="text-[9px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider block mb-1">Session ID</span>
                    <div className="flex items-center justify-between bg-surface-container-low dark:bg-slate-950 px-2.5 py-1.5 rounded-lg border border-outline-variant/30 dark:border-slate-800">
                      <span className="text-[10px] font-mono truncate text-primary dark:text-slate-300 w-44">{sessionId}</span>
                      <button 
                        className="text-primary dark:text-primary-container hover:text-primary/80 p-0.5 rounded transition-colors outline-none"
                        onClick={() => {
                          navigator.clipboard.writeText(sessionId);
                          addToast({ type: 'info', message: 'Session ID copied to clipboard!' });
                        }}
                        title="Copy Session ID"
                      >
                        <span className="material-symbols-outlined text-[14px]">content_copy</span>
                      </button>
                    </div>
                  </div>

                  <div>
                    <span className="text-[9px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider block mb-1.5">System Specs</span>
                    <div className="space-y-1 bg-surface-container-low dark:bg-slate-950 p-2.5 rounded-lg border border-outline-variant/30 dark:border-slate-800 text-[10px] font-semibold text-secondary dark:text-slate-400">
                      <div className="flex justify-between"><span>Ollama model:</span> <span className="text-primary dark:text-slate-200">llama3 (8B)</span></div>
                      <div className="flex justify-between"><span>API server:</span> <span className="text-primary dark:text-slate-200">localhost:8000</span></div>
                      <div className="flex justify-between"><span>WebSocket:</span> <span className={isHealthy ? 'text-emerald-600' : 'text-rose-600'}>{isHealthy ? 'Connected' : 'Offline'}</span></div>
                    </div>
                  </div>
                </div>

                {/* Reset button */}
                <button 
                  className="w-full py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-600 dark:bg-rose-950/20 dark:hover:bg-rose-950/40 dark:text-rose-400 rounded-xl text-xs font-bold transition-colors border border-rose-100 dark:border-rose-900/30 flex items-center justify-center gap-1.5 outline-none"
                  onClick={() => {
                    if (confirm('Reset chat session and clear conversation history?')) {
                      setChatResetKey((prev) => prev + 1);
                      addToast({ type: 'info', message: 'Conversation history reset.' });
                      setIsProfileOpen(false);
                    }
                  }}
                >
                  <span className="material-symbols-outlined text-sm">restart_alt</span>
                  Clear Chat Memory
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex flex-1 h-[calc(100vh-64px)] overflow-hidden bg-background dark:bg-slate-950">
        {/* Persistent Left Sidebar for Knowledge Base */}
        <Sidebar
          documents={documents}
          isUploading={isUploading}
          uploadProgress={uploadProgress}
          onUpload={handleUpload}
          onDeleteDoc={handleDeleteDoc}
          docCount={docCount}
          isHealthy={isHealthy}
        />

        {/* Dynamic Center Pane */}
        <div className="flex-1 flex overflow-hidden">
          {activePage === 'chat' ? (
            <>
              <ChatInterface
                documents={documents}
                onSourcesUpdate={handleSourcesUpdate}
                sessionId={sessionId}
                onUpload={handleUpload}
                chatResetKey={chatResetKey}
              />
              <SourcePanel
                sources={sources}
                isCollapsed={isSourceCollapsed}
                onToggle={() => setIsSourceCollapsed(!isSourceCollapsed)}
              />
            </>
          ) : (
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              <EvalDashboard onToast={addToast} />
            </div>
          )}
        </div>
      </main>

      {/* Toast Notifications */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg border-premium animate-fade-up bg-white dark:bg-slate-800 text-xs font-semibold ${
              toast.type === 'success' ? 'text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50 bg-green-50/50 dark:bg-green-950/20' : 
              toast.type === 'error' ? 'text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20' : 
              'text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900/50 bg-indigo-50/50 dark:bg-indigo-950/20'
            }`}
          >
            <span className="text-base select-none">
              {toast.type === 'success' ? '✅' : toast.type === 'error' ? '❌' : 'ℹ️'}
            </span>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
