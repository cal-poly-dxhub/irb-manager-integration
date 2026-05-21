import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatMessage, FormValues } from '../types';
import { createSession, loadSession, saveFormValues, deleteSession as apiDeleteSession, type SessionData } from '../api';

const STORAGE_KEY = 'compliance-assistant-session-id';
const SESSION_LIST_KEY = 'compliance-assistant-sessions';

export interface StoredSession {
  id: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

function getStoredSessions(): StoredSession[] {
  try {
    const raw = localStorage.getItem(SESSION_LIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveStoredSessions(sessions: StoredSession[]) {
  localStorage.setItem(SESSION_LIST_KEY, JSON.stringify(sessions));
}

function addStoredSession(session: StoredSession) {
  const sessions = getStoredSessions();
  sessions.unshift(session);
  saveStoredSessions(sessions);
}

function removeStoredSession(sessionId: string) {
  const sessions = getStoredSessions().filter(s => s.id !== sessionId);
  saveStoredSessions(sessions);
}

interface UseSessionOptions {
  onSessionLoaded: (data: {
    formValues: FormValues;
    messages: ChatMessage[];
    attachmentFilenames: string[];
  }) => void;
}

export function useSession({ onSessionLoaded }: UseSessionOptions) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionList, setSessionList] = useState<StoredSession[]>([]);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Resolve session on mount
  useEffect(() => {
    setSessionList(getStoredSessions());
    resolveSession();
  }, []);

  async function resolveSession() {
    setIsLoading(true);

    // 1. Check URL param
    const params = new URLSearchParams(window.location.search);
    const urlSessionId = params.get('session');

    // 2. Check localStorage
    const storedSessionId = localStorage.getItem(STORAGE_KEY);

    const candidateId = urlSessionId || storedSessionId;

    if (candidateId) {
      try {
        const data = await loadSession(candidateId);
        if (data) {
          applySession(data);
          setIsLoading(false);
          return;
        }
      } catch {
        // Session not found or load failed -- create new
      }
      // Clear stale ID
      localStorage.removeItem(STORAGE_KEY);
    }

    // 3. Create new session
    try {
      const data = await createSession();
      persistSessionId(data.sessionId);
      setSessionId(data.sessionId);
      const stored: StoredSession = {
        id: data.sessionId,
        createdAt: data.createdAt,
        updatedAt: data.updatedAt,
        messageCount: 0,
      };
      addStoredSession(stored);
      setSessionList(getStoredSessions());
    } catch {
      // Sessions not available (local dev) -- proceed without persistence
    }

    setIsLoading(false);
  }

  function applySession(data: SessionData) {
    persistSessionId(data.sessionId);
    setSessionId(data.sessionId);

    // Convert conversation history to ChatMessage format
    const messages: ChatMessage[] = data.conversationHistory.map((msg, i) => ({
      id: `restored-${i}`,
      role: msg.role as 'user' | 'assistant',
      content: msg.content,
      fieldUpdates: msg.fieldUpdates,
      attachments: msg.attachmentFilenames?.map(f => ({ filename: f })),
      timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(data.createdAt),
    }));

    // Convert string-keyed form values to number-keyed
    const formValues: FormValues = {};
    for (const [key, value] of Object.entries(data.formValues)) {
      formValues[Number(key)] = value;
    }

    onSessionLoaded({
      formValues,
      messages,
      attachmentFilenames: data.attachmentFilenames,
    });
  }

  function persistSessionId(id: string) {
    localStorage.setItem(STORAGE_KEY, id);
    const url = new URL(window.location.href);
    url.searchParams.set('session', id);
    window.history.replaceState({}, '', url.toString());
  }

  // Debounced form save -- call this when form values change
  const debouncedSaveForm = useCallback(
    (formValues: FormValues) => {
      if (!sessionId) return;

      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      // Convert number keys to strings for the API
      const stringKeyed: Record<string, string | boolean | string[]> = {};
      for (const [key, value] of Object.entries(formValues)) {
        stringKeyed[String(key)] = value;
      }

      saveTimerRef.current = setTimeout(() => {
        saveFormValues(sessionId, stringKeyed).catch((err) => {
          console.warn('Failed to save form values:', err);
        });
      }, 2000);
    },
    [sessionId],
  );

  const createNewSession = useCallback(async () => {
    try {
      const data = await createSession();
      persistSessionId(data.sessionId);
      setSessionId(data.sessionId);
      const stored: StoredSession = {
        id: data.sessionId,
        createdAt: data.createdAt,
        updatedAt: data.updatedAt,
        messageCount: 0,
      };
      addStoredSession(stored);
      setSessionList(getStoredSessions());

      onSessionLoaded({
        formValues: {},
        messages: [],
        attachmentFilenames: [],
      });
    } catch (err) {
      console.warn('Failed to create new session:', err);
    }
  }, [onSessionLoaded]);

  const switchSession = useCallback(async (targetId: string) => {
    if (targetId === sessionId) return;
    try {
      const data = await loadSession(targetId);
      if (data) {
        applySession(data);
      }
    } catch (err) {
      console.warn('Failed to switch session:', err);
    }
  }, [sessionId]);

  const deleteSessionFn = useCallback(async (targetId: string) => {
    try {
      await apiDeleteSession(targetId);
    } catch {
      // API might not be available
    }
    removeStoredSession(targetId);
    setSessionList(getStoredSessions());

    // If deleting the current session, create a new one
    if (targetId === sessionId) {
      await createNewSession();
    }
  }, [sessionId, createNewSession]);

  return {
    sessionId,
    isSessionLoading: isLoading,
    sessionList,
    debouncedSaveForm,
    switchSession,
    createNewSession,
    deleteSession: deleteSessionFn,
  };
}
