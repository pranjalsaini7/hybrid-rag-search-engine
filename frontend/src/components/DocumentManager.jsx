import { useState, useRef, useEffect, useCallback } from 'react';
import { uploadDocument, listDocuments, deleteDocument } from '../utils/api';

/**
 * DocumentManager — Upload, list, and delete documents with summaries
 */
export default function DocumentManager({ onDocCountChange, onToast }) {
  const [documents, setDocuments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragover, setDragover] = useState(false);
  const fileInputRef = useRef(null);

  const loadDocs = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocuments(data.documents || []);
      if (onDocCountChange) onDocCountChange(data.total || 0);
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  }, [onDocCountChange]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;

    for (const file of files) {
      setIsUploading(true);
      setUploadProgress(10);

      try {
        // Simulate progress
        const progressInterval = setInterval(() => {
          setUploadProgress((prev) => Math.min(prev + 15, 85));
        }, 500);

        const result = await uploadDocument(file);

        clearInterval(progressInterval);
        setUploadProgress(100);

        onToast?.({
          type: 'success',
          message: `"${result.filename}" uploaded — ${result.chunk_count} chunks`,
        });

        setTimeout(() => {
          setIsUploading(false);
          setUploadProgress(0);
        }, 500);

        await loadDocs();
      } catch (e) {
        setIsUploading(false);
        setUploadProgress(0);
        onToast?.({ type: 'error', message: e.message });
      }
    }
  };

  const handleDelete = async (docId, filename) => {
    if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;

    try {
      await deleteDocument(docId);
      onToast?.({ type: 'success', message: `Deleted "${filename}"` });
      await loadDocs();
    } catch (e) {
      onToast?.({ type: 'error', message: e.message });
    }
  };

  const getFileIcon = (type) => {
    switch (type) {
      case 'pdf': return '📕';
      case 'docx': return '📘';
      case 'txt': return '📗';
      default: return '📄';
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="doc-manager">
      <div className="doc-manager-header">
        <h2>📄 Documents</h2>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
          {documents.length} document{documents.length !== 1 ? 's' : ''} indexed
        </span>
      </div>

      <div className="doc-manager-content">
        {/* Upload Zone */}
        <div
          className={`upload-zone ${dragover ? 'dragover' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
          onDragLeave={() => setDragover(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragover(false);
            handleUpload(e.dataTransfer.files);
          }}
        >
          <div className="upload-zone-icon">📤</div>
          <h4>Drop files here or click to upload</h4>
          <p>Support for PDF, DOCX, and TXT files (max 50 MB)</p>
          <div className="upload-zone-badge">
            <span className="file-type-badge">PDF</span>
            <span className="file-type-badge">DOCX</span>
            <span className="file-type-badge">TXT</span>
          </div>

          {isUploading && (
            <div className="upload-progress">
              <div className="upload-progress-bar">
                <div
                  className="upload-progress-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <div className="upload-progress-text">
                Uploading and processing… {uploadProgress}%
              </div>
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleUpload(e.target.files)}
        />

        {/* Document Grid */}
        <div className="doc-grid">
          {documents.map((doc) => (
            <div key={doc.id} className="doc-card">
              <div className="doc-card-header">
                <div className={`doc-card-icon ${doc.file_type}`}>
                  {getFileIcon(doc.file_type)}
                </div>
                <div className="doc-card-actions">
                  <button
                    className="doc-action-btn"
                    onClick={() => handleDelete(doc.id, doc.filename)}
                    title="Delete document"
                  >
                    🗑️
                  </button>
                </div>
              </div>

              <div className="doc-card-title">{doc.filename}</div>

              <div className="doc-card-meta">
                <span>📊 {doc.chunk_count} chunks</span>
                <span>📅 {formatDate(doc.upload_date)}</span>
              </div>

              {doc.summary && (
                <div className="doc-card-summary">{doc.summary}</div>
              )}
            </div>
          ))}
        </div>

        {documents.length === 0 && !isUploading && (
          <div style={{
            textAlign: 'center',
            color: 'var(--text-tertiary)',
            padding: 'var(--space-8)',
            fontSize: 'var(--text-sm)',
          }}>
            No documents yet. Upload your research papers to get started.
          </div>
        )}
      </div>
    </div>
  );
}
