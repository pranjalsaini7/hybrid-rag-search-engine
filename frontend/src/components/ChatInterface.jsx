import { useState, useEffect, useRef, useCallback } from 'react';
import useWebSocket from '../hooks/useWebSocket';
import { compareDocuments } from '../utils/api';

/**
 * ChatInterface — Revamped center pane to match the Google Stitch layout.
 * Supports streaming, comparison selectors, follow-ups, confidence badges,
 * PDF export, and an inline file attachment trigger.
 */
export default function ChatInterface({
  documents = [],
  onSourcesUpdate,
  sessionId,
  onUpload,
  chatResetKey,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [docA, setDocA] = useState('');
  const [docB, setDocB] = useState('');
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const { isConnected, sendMessage, lastMessage } = useWebSocket(sessionId);

  // Handle session reset
  useEffect(() => {
    setMessages([]);
    if (onSourcesUpdate) onSourcesUpdate([]);
  }, [chatResetKey, onSourcesUpdate]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    switch (lastMessage.type) {
      case 'token':
        setStreamingContent((prev) => prev + lastMessage.content);
        break;

      case 'sources':
        if (onSourcesUpdate) onSourcesUpdate(lastMessage.data || []);
        break;

      case 'follow_up':
        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0) {
            const last = updated[updated.length - 1];
            if (last.role === 'assistant') {
              updated[updated.length - 1] = {
                ...last,
                followUps: lastMessage.data || [],
              };
            }
          }
          return updated;
        });
        break;

      case 'guard':
        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0) {
            const last = updated[updated.length - 1];
            if (last.role === 'assistant') {
              updated[updated.length - 1] = {
                ...last,
                guard: lastMessage.data,
              };
            }
          }
          return updated;
        });
        break;

      case 'done':
        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0 && updated[updated.length - 1].role === 'assistant') {
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              isStreaming: false,
            };
          }
          return updated;
        });
        setStreamingContent('');
        setIsLoading(false);
        break;

      case 'error':
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ Error: ${lastMessage.content}`,
            isError: true,
          },
        ]);
        setStreamingContent('');
        setIsLoading(false);
        break;
    }
  }, [lastMessage, onSourcesUpdate]);

  // Update the streaming message in real-time
  useEffect(() => {
    if (streamingContent) {
      setMessages((prev) => {
        const updated = [...prev];
        if (updated.length > 0 && updated[updated.length - 1].isStreaming) {
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: streamingContent,
          };
        }
        return updated;
      });
    }
  }, [streamingContent]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Reset loading state if connection is lost
  useEffect(() => {
    if (!isConnected) {
      setIsLoading(false);
    }
  }, [isConnected]);

  const handleExportPDF = useCallback(() => {
    if (messages.length === 0) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      alert('Please allow popups to export chat as PDF.');
      return;
    }
    const chatHtml = messages
      .map((msg) => {
        const formattedContent = msg.content
          .split('\n')
          .map((line) => `<p>${line || '&nbsp;'}</p>`)
          .join('');
        return `
        <div class="message ${msg.role}">
          <div class="role">${msg.role === 'user' ? 'User Query' : 'Assistant Answer'}</div>
          <div class="content">${formattedContent}</div>
        </div>
      `;
      })
      .join('');

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Chat Export — RAG Assistant</title>
          <style>
            body {
              font-family: 'Inter', system-ui, -apple-system, sans-serif;
              padding: 40px;
              color: #1a1c1d;
              background-color: #ffffff;
              line-height: 1.6;
              max-width: 800px;
              margin: 0 auto;
            }
            header {
              border-bottom: 2px solid #e5e5e7;
              padding-bottom: 20px;
              margin-bottom: 30px;
              display: flex;
              justify-content: space-between;
              align-items: center;
            }
            .brand {
              font-size: 20px;
              font-weight: 800;
              color: #1a1c1d;
            }
            .date {
              font-size: 12px;
              color: #626267;
            }
            .message {
              margin-bottom: 24px;
              padding: 20px;
              border-radius: 8px;
              page-break-inside: avoid;
            }
            .user {
              background: #f3f3f5;
              border-left: 4px solid #4f46e5;
            }
            .assistant {
              background: #f9f9fb;
              border-left: 4px solid #1a1c1d;
            }
            .role {
              font-weight: 700;
              margin-bottom: 8px;
              text-transform: uppercase;
              font-size: 11px;
              letter-spacing: 0.05em;
              color: #626267;
            }
            .content p {
              margin: 0 0 10px 0;
            }
            .content p:last-child {
              margin-bottom: 0;
            }
            footer {
              margin-top: 50px;
              border-top: 1px solid #e5e5e7;
              padding-top: 15px;
              font-size: 11px;
              color: #626267;
              text-align: center;
            }
          </style>
        </head>
        <body>
          <header>
            <div class="brand">📚 Research Paper RAG Assistant</div>
            <div class="date">${new Date().toLocaleString()}</div>
          </header>
          <main>
            ${chatHtml}
          </main>
          <footer>
            Generated locally by RAG Assistant Q&A Session
          </footer>
          <script>
            window.onload = function() {
              setTimeout(() => {
                window.print();
                window.close();
              }, 300);
            }
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  }, [messages]);

  const handleSend = useCallback(() => {
    const query = input.trim();
    if (!query || isLoading) return;

    if (isCompareMode) {
      if (!docA || !docB) {
        alert('Please select both Document A and Document B to compare.');
        return;
      }
      if (docA === docB) {
        alert('Please select two different documents to compare.');
        return;
      }

      const docAName = documents.find((d) => d.id === docA)?.filename || 'Doc A';
      const docBName = documents.find((d) => d.id === docB)?.filename || 'Doc B';

      setMessages((prev) => [
        ...prev,
        {
          role: 'user',
          content: `Compare "${docAName}" vs "${docBName}" regarding: ${query}`,
        },
      ]);

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '', isStreaming: true },
      ]);

      setIsLoading(true);
      setInput('');

      compareDocuments(query, docA, docB)
        .then((res) => {
          setMessages((prev) => {
            const updated = [...prev];
            if (updated.length > 0 && updated[updated.length - 1].role === 'assistant') {
              updated[updated.length - 1] = {
                role: 'assistant',
                content: res.answer,
                isStreaming: false,
                followUps: res.follow_up_questions || [],
              };
            }
            return updated;
          });
          if (onSourcesUpdate) onSourcesUpdate(res.sources || []);
          setIsLoading(false);
        })
        .catch((err) => {
          setMessages((prev) => {
            const updated = [...prev];
            if (updated.length > 0 && updated[updated.length - 1].role === 'assistant') {
              updated[updated.length - 1] = {
                role: 'assistant',
                content: `⚠️ Error: ${err.message}`,
                isStreaming: false,
                isError: true,
              };
            }
            return updated;
          });
          setIsLoading(false);
        });

      return;
    }

    if (!isConnected) return;

    // Add user message
    setMessages((prev) => [...prev, { role: 'user', content: query }]);

    // Add placeholder assistant message
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', isStreaming: true },
    ]);

    setStreamingContent('');
    setIsLoading(true);
    setInput('');

    // Send via WebSocket
    sendMessage({ query, use_guard: true });
  }, [
    input,
    isLoading,
    isConnected,
    sendMessage,
    isCompareMode,
    docA,
    docB,
    documents,
    onSourcesUpdate,
  ]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const askFollowUp = (question) => {
    if (isLoading) return;
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', isStreaming: true },
    ]);
    setStreamingContent('');
    setIsLoading(true);
    sendMessage({ query: question, use_guard: true });
  };

  const handleAttachmentClick = () => {
    fileInputRef.current?.click();
  };

  const handleAttachmentChange = (e) => {
    if (onUpload && e.target.files) {
      onUpload(e.target.files);
    }
  };

  const scrollCitationIntoView = (idx) => {
    const card = document.getElementById(`citation-card-${idx}`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      card.classList.add('bg-primary-container/20', 'border-primary/45', 'shadow-md');
      setTimeout(() => {
        card.classList.remove('bg-primary-container/20', 'border-primary/45', 'shadow-md');
      }, 1500);
    }
  };

  return (
    <section className="flex-1 flex flex-col bg-background dark:bg-slate-950 border-r border-outline-variant/50 dark:border-slate-800 relative overflow-hidden h-full">
      {/* Mini Top Subheader */}
      <div className="h-12 px-6 border-b border-outline-variant/60 dark:border-slate-800/80 flex items-center justify-between bg-background dark:bg-slate-900 shrink-0">
        <div className="flex items-center gap-2 select-none">
          <span className="text-xs font-bold text-secondary dark:text-slate-400 uppercase tracking-widest">
            Auto-Assist Chat
          </span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isConnected ? 'bg-emerald-500' : 'bg-rose-500'
            }`}
          />
          <span className="text-[10px] font-semibold text-secondary dark:text-slate-400">
            {isConnected ? 'Connected' : 'Offline'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold border transition-all ${
              isCompareMode
                ? 'bg-primary-container/15 dark:bg-primary-container/10 text-primary dark:text-primary-container border-primary-container/25'
                : 'bg-background dark:bg-slate-900 border-outline-variant/60 dark:border-slate-800 text-secondary dark:text-slate-400 hover:text-primary dark:hover:text-white hover:bg-surface-container-low dark:hover:bg-slate-800'
            }`}
            onClick={() => setIsCompareMode(!isCompareMode)}
          >
            <span className="material-symbols-outlined text-[14px]">
              compare_arrows
            </span>
            Compare Docs
          </button>

          {messages.length > 0 && (
            <button
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold border bg-background dark:bg-slate-900 border-outline-variant/60 dark:border-slate-800 text-secondary dark:text-slate-400 hover:text-primary dark:hover:text-white hover:bg-surface-container-low dark:hover:bg-slate-800 transition-all"
              onClick={handleExportPDF}
            >
              <span className="material-symbols-outlined text-[14px]">
                download
              </span>
              Export PDF
            </button>
          )}
        </div>
      </div>

      {/* Comparison Selectors */}
      {isCompareMode && (
        <div className="bg-background dark:bg-slate-900 border-b border-outline-variant/60 dark:border-slate-800/80 px-6 py-2.5 flex items-center gap-3 flex-wrap shrink-0 select-none animate-fade-up">
          <span className="text-[10px] font-bold text-secondary dark:text-slate-400 uppercase tracking-wider">
            Compare:
          </span>
          <select
            value={docA}
            onChange={(e) => setDocA(e.target.value)}
            className="text-[11px] bg-surface-container-low dark:bg-slate-950 border border-outline-variant/60 dark:border-slate-800 text-primary dark:text-slate-200 rounded-lg px-2 py-1 outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/30 font-semibold"
          >
            <option value="">-- Document A --</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>
          <span className="text-[10px] text-secondary dark:text-slate-400 font-bold font-mono">VS</span>
          <select
            value={docB}
            onChange={(e) => setDocB(e.target.value)}
            className="text-[11px] bg-surface-container-low dark:bg-slate-950 border border-outline-variant/60 dark:border-slate-800 text-primary dark:text-slate-200 rounded-lg px-2 py-1 outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/30 font-semibold"
          >
            <option value="">-- Document B --</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-10 custom-scrollbar pb-36">
        <div className="max-w-2xl mx-auto space-y-10">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center select-none animate-fade-up">
              <div className="w-12 h-12 rounded-2xl bg-primary-container/20 dark:bg-primary-container/10 text-primary dark:text-primary-container flex items-center justify-center mb-6">
                <span className="material-symbols-outlined text-2xl">
                  forum
                </span>
              </div>
              <h3 className="font-bold text-base text-primary dark:text-white mb-2">
                Ask your research papers
              </h3>
              <p className="text-xs text-secondary dark:text-slate-400 leading-relaxed max-w-sm mb-6">
                Upload PDFs and ask anything. Hybrid vector + keyword search delivers grounded, cited answers.
              </p>
              {/* Quick Suggestion Chips */}
              <div className="flex flex-wrap justify-center gap-3 select-none">
                <button 
                  className="bg-white dark:bg-slate-900 hover:bg-primary-container/10 dark:hover:bg-primary-container/5 text-[11px] font-bold text-primary dark:text-primary-container border border-outline-variant/80 dark:border-slate-800 rounded-full px-4 py-2 shadow-sm transition-all outline-none"
                  onClick={() => {
                    setInput("Summarize the key findings, methodology, and contributions of the uploaded documents.");
                  }}
                >
                  Summarize key points
                </button>
                <button 
                  className="bg-white dark:bg-slate-900 hover:bg-primary-container/10 dark:hover:bg-primary-container/5 text-[11px] font-bold text-primary dark:text-primary-container border border-outline-variant/80 dark:border-slate-800 rounded-full px-4 py-2 shadow-sm transition-all outline-none"
                  onClick={() => {
                    setIsCompareMode(true);
                  }}
                >
                  Compare documents
                </button>
                <button 
                  className="bg-white dark:bg-slate-900 hover:bg-primary-container/10 dark:hover:bg-primary-container/5 text-[11px] font-bold text-primary dark:text-primary-container border border-outline-variant/80 dark:border-slate-800 rounded-full px-4 py-2 shadow-sm transition-all outline-none"
                  onClick={() => {
                    setInput("Define the key technical terms, acronyms, and core concepts mentioned in the documents.");
                  }}
                >
                  Find definitions
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={i}
                  className={`flex items-start gap-4 ${
                    isUser ? 'flex-row-reverse' : 'animate-fade-up'
                  }`}
                >
                  {/* Avatar */}
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border ${
                      isUser
                        ? 'bg-primary-container/20 dark:bg-primary-container/10 border-primary-container/20 dark:border-primary/20 text-primary dark:text-primary-container'
                        : 'bg-primary dark:bg-primary border-primary dark:border-primary text-white'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[18px]">
                      {isUser ? 'person' : 'auto_awesome'}
                    </span>
                  </div>

                  {/* Bubble Container */}
                  <div className={`flex flex-col ${isUser ? 'items-end' : ''}`}>
                    <div
                      className={`p-5 rounded-2xl border shadow-sm leading-relaxed text-[13.5px] max-w-xl ${
                        isUser
                          ? 'bg-white dark:bg-slate-900 border-outline-variant/30 dark:border-slate-800 text-primary dark:text-slate-200 rounded-tr-none'
                          : 'bg-white dark:bg-slate-900 border-outline-variant/30 dark:border-slate-800 text-primary dark:text-slate-200 rounded-tl-none'
                      }`}
                    >
                      {msg.isStreaming && !msg.content ? (
                        <div className="flex items-center gap-1.5 py-1.5">
                          <span className="w-1.5 h-1.5 bg-secondary rounded-full animate-bounce"></span>
                          <span className="w-1.5 h-1.5 bg-secondary rounded-full animate-bounce [animation-delay:0.2s]"></span>
                          <span className="w-1.5 h-1.5 bg-secondary rounded-full animate-bounce [animation-delay:0.4s]"></span>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {msg.content.split('\n').map((line, j) => (
                            <p key={j}>{line || '\u00A0'}</p>
                          ))}
                        </div>
                      )}

                      {/* Confidence indicator badge */}
                      {!isUser && msg.guard && (
                        <div
                          className={`mt-4 inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            msg.guard.confidence === 'high'
                              ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400'
                              : msg.guard.confidence === 'medium'
                              ? 'bg-yellow-50 dark:bg-yellow-950/20 text-yellow-700 dark:text-yellow-400'
                              : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400'
                          }`}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                          {msg.guard.confidence} Confidence
                        </div>
                      )}

                      {/* Bot response citation list */}
                      {!isUser && msg.sources && msg.sources.length > 0 && (
                        <div className="mt-5 pt-3 border-t border-outline-variant/50 dark:border-slate-800 flex items-center gap-2 select-none">
                          <span className="text-[10px] font-bold text-secondary dark:text-slate-400 uppercase tracking-widest">
                            Sources:
                          </span>
                          <div className="flex gap-1.5">
                            {msg.sources.map((s, idx) => (
                              <span
                                key={idx}
                                className="w-5 h-5 flex items-center justify-center bg-primary-container/25 dark:bg-primary-container/15 text-primary dark:text-primary-container hover:bg-primary-container/40 dark:hover:bg-primary-container/25 rounded text-[10px] font-bold cursor-pointer transition-colors"
                                onClick={() => scrollCitationIntoView(idx)}
                                title={s.document_name}
                              >
                                {idx + 1}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Follow-up Question Prompts */}
                    {!isUser && msg.followUps && msg.followUps.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2 max-w-xl select-none">
                        {msg.followUps.map((q, k) => (
                          <button
                            key={k}
                            className="bg-primary-container/10 dark:bg-primary-container/5 hover:bg-primary-container/20 text-primary dark:text-primary-container border border-primary-container/20 dark:border-primary/10 rounded-lg px-3 py-1.5 text-[11px] font-semibold transition-colors outline-none"
                            onClick={() => askFollowUp(q)}
                            disabled={isLoading}
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Floating Bottom Input Bar */}
      <div className="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-background dark:from-slate-950 via-background dark:via-slate-950 to-transparent shrink-0">
        <div className="max-w-2xl mx-auto relative group">
          {/* Subtle Focus Glow Effect */}
          <div className="absolute inset-0 bg-primary/5 blur-xl rounded-2xl opacity-0 group-focus-within:opacity-100 transition-opacity duration-300"></div>

          <div className="relative flex items-center bg-white dark:bg-slate-900 border border-primary/45 focus-within:border-primary dark:border-primary/40 rounded-2xl p-2.5 shadow-xl shadow-black/5 dark:shadow-none transition-all">
            <button
              className="p-2 text-secondary dark:text-slate-400 hover:text-primary dark:hover:text-primary-container transition-colors ml-1"
              onClick={handleAttachmentClick}
              title="Upload PDF or txt"
            >
              <span className="material-symbols-outlined">attach_file</span>
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              multiple
              style={{ display: 'none' }}
              onChange={handleAttachmentChange}
            />

            <input
              className="flex-1 bg-transparent border-none focus:ring-0 text-[13.5px] px-3 py-2.5 placeholder:text-secondary/50 dark:placeholder:text-slate-500 outline-none text-primary dark:text-slate-200"
              placeholder="Ask anything about your documents..."
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={(!isConnected && !isCompareMode) || isLoading}
            />

            <button
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                input.trim() && !isLoading && (isConnected || isCompareMode)
                  ? 'bg-primary text-white hover:bg-primary/95 shadow-sm'
                  : 'bg-surface-container-low text-secondary cursor-not-allowed'
              }`}
              onClick={handleSend}
              disabled={!input.trim() || isLoading || (!isConnected && !isCompareMode)}
            >
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          </div>

          <p className="text-center text-[9px] text-secondary/50 dark:text-slate-500 mt-4 font-bold uppercase tracking-wider select-none">
            AI-generated content may contain errors. Please verify citations.
          </p>
        </div>
      </div>
    </section>
  );
}
