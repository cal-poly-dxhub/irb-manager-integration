import type { ChatRequest, FieldUpdate, FlaggedIssue } from './types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export interface StreamCallbacks {
  onFieldUpdate: (update: FieldUpdate) => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
  onDone: () => void;
  onToolCall?: (data: { name: string; input: Record<string, unknown> }) => void;
  onToolResult?: (data: { name: string; result: Record<string, unknown> }) => void;
  onThinking?: (text: string) => void;
  onFlaggedIssue?: (issue: FlaggedIssue) => void;
}

export async function sendChatMessageStream(
  req: ChatRequest,
  callbacks: StreamCallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(error.message || `Chat API error: ${res.statusText}`);
  }

  // Check if it's SSE stream or regular JSON (mock mode returns JSON)
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('text/event-stream')) {
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6);
        try {
          const event = JSON.parse(jsonStr);
          if (event.type === 'fieldUpdate') {
            callbacks.onFieldUpdate(event.data);
          } else if (event.type === 'message') {
            callbacks.onMessage(event.data.message);
          } else if (event.type === 'error') {
            callbacks.onError(event.data.message);
          } else if (event.type === 'done') {
            callbacks.onDone();
          } else if (event.type === 'toolCall') {
            callbacks.onToolCall?.(event.data);
          } else if (event.type === 'toolResult') {
            callbacks.onToolResult?.(event.data);
          } else if (event.type === 'thinking') {
            callbacks.onThinking?.(event.data.text);
          } else if (event.type === 'flaggedIssue') {
            callbacks.onFlaggedIssue?.(event.data);
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  } else {
    // Mock mode: regular JSON response
    const data = await res.json();
    if (data.fieldUpdates) {
      for (const update of data.fieldUpdates) {
        callbacks.onFieldUpdate(update);
      }
    }
    if (data.message) {
      callbacks.onMessage(data.message);
    }
    callbacks.onDone();
  }
}

// -------------------------------------------------------
// Session API
// -------------------------------------------------------

export interface SessionData {
  sessionId: string;
  status: string;
  formValues: Record<string, string | boolean | string[]>;
  conversationHistory: {
    role: string;
    content: string;
    fieldUpdates?: { dataId: number; value: string }[];
    attachmentFilenames?: string[];
    timestamp?: string;
  }[];
  attachmentFilenames: string[];
  createdAt: string;
  updatedAt: string;
}

export async function createSession(): Promise<SessionData> {
  const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
  if (!res.ok) {
    throw new Error('Failed to create session');
  }
  return res.json();
}

export async function loadSession(sessionId: string): Promise<SessionData | null> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error('Failed to load session');
  }
  return res.json();
}

export async function saveFormValues(
  sessionId: string,
  formValues: Record<string, string | boolean | string[]>,
): Promise<void> {
  await fetch(`${API_BASE}/sessions/${sessionId}/form`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ formValues }),
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error('Failed to delete session');
  }
}

// -------------------------------------------------------
// File helpers
// -------------------------------------------------------

export async function readTextFile(file: File): Promise<{ filename: string; content: string }> {
  const content = await file.text();
  return { filename: file.name, content };
}

export async function parsePdf(file: File): Promise<{ filename: string; content: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/parse-pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(error.message || 'Failed to parse PDF');
  }

  const data = await res.json();
  return { filename: file.name, content: data.text };
}
