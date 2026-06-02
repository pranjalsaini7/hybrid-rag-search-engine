/**
 * API Client — REST endpoints for the RAG backend
 */

const getApiUrl = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/$/, ''); // strip trailing slash
  }
  return 'http://localhost:8000';
};

const BASE_URL = getApiUrl();

export async function fetchHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

// ── Documents ────────────────────────────────────────────────────────

export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function listDocuments() {
  const res = await fetch(`${BASE_URL}/api/documents/`);
  return res.json();
}

export async function deleteDocument(docId) {
  const res = await fetch(`${BASE_URL}/api/documents/${docId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
  return res.json();
}

// ── Chat ──────────────────────────────────────────────────────────────

export async function chatQuery(query, sessionId = 'default') {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Chat failed: ${res.status}`);
  }
  return res.json();
}

export async function compareDocuments(query, docAId, docBId) {
  const res = await fetch(`${BASE_URL}/api/chat/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, doc_a_id: docAId, doc_b_id: docBId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Comparison failed: ${res.status}`);
  }
  return res.json();
}

export function createWebSocket(sessionId) {
  const wsProtocol = BASE_URL.startsWith('https') ? 'wss' : 'ws';
  const cleanUrl = BASE_URL.replace(/^https?:\/\//, '');
  return new WebSocket(`${wsProtocol}://${cleanUrl}/ws/chat/${sessionId}`);
}

// ── Evaluation ────────────────────────────────────────────────────────

export async function runEvaluation(questions) {
  const res = await fetch(`${BASE_URL}/api/eval/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'default', questions }),
  });
  if (!res.ok) throw new Error(`Eval failed: ${res.status}`);
  return res.json();
}

export async function listEvalRuns() {
  const res = await fetch(`${BASE_URL}/api/eval/results`);
  return res.json();
}

export async function getEvalRun(runId) {
  const res = await fetch(`${BASE_URL}/api/eval/results/${runId}`);
  return res.json();
}
