import { useState, useCallback } from 'react';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { SessionManager } from './SessionManager';
import type { ChatMessage, AppMode, FormValues, FormElement } from '../types';
import type { StoredSession } from '../hooks/useSession';

const MODE_LABELS: Record<AppMode, string> = {
  coauthor: 'Co-Author',
  review: 'Review',
  adapt: 'Adapt',
};

interface ChatPanelProps {
  messages: ChatMessage[];
  isLoading: boolean;
  pendingFiles: { filename: string; content: string }[];
  sendMessage: (content: string) => Promise<void>;
  addFile: (file: File) => Promise<void>;
  removeFile: (filename: string) => void;
  mode: AppMode;
  onModeChange: () => void;
  valuesSnapshot: FormValues | null;
  currentValues: FormValues;
  sections: FormElement[];
  sessionId: string | null;
  sessionList: StoredSession[];
  onSwitchSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
}

function buildLabelMap(sections: FormElement[]): Map<number, string> {
  const map = new Map<number, string>();

  function walk(elements: FormElement[]) {
    for (const el of elements) {
      if (el.text) {
        const tmp = document.createElement('div');
        tmp.innerHTML = el.text;
        const label = tmp.textContent || tmp.innerText || '';
        if (label) {
          map.set(el.dataId, label);
        }
      }
      if (el.children) {
        walk(el.children);
      }
    }
  }

  walk(sections);
  return map;
}

function buildChangesSummary(
  snapshot: FormValues,
  current: FormValues,
  labelMap: Map<number, string>,
): string[] {
  const changes: string[] = [];
  for (const [key, value] of Object.entries(current)) {
    const dataId = Number(key);
    const prev = snapshot[dataId];
    if (prev !== value) {
      const label = labelMap.get(dataId) || `Field ${dataId}`;
      const truncated = typeof value === 'string' && value.length > 80
        ? value.slice(0, 80) + '...'
        : String(value);
      changes.push(`- ${label}: ${truncated}`);
    }
  }
  return changes;
}

export function ChatPanel({
  messages,
  isLoading,
  pendingFiles,
  sendMessage,
  addFile,
  removeFile,
  mode,
  onModeChange,
  valuesSnapshot,
  currentValues,
  sections,
  sessionId,
  sessionList,
  onSwitchSession,
  onNewSession,
  onDeleteSession,
}: ChatPanelProps) {
  const [showSessions, setShowSessions] = useState(false);

  const lastMessage = messages[messages.length - 1];
  const showApprove = mode === 'coauthor' && !isLoading && lastMessage?.role === 'assistant' && lastMessage.content.length > 0;

  const handleApprove = useCallback(() => {
    if (!valuesSnapshot) {
      sendMessage('Approved. Continue to the next section.');
      return;
    }
    const labelMap = buildLabelMap(sections);
    const changes = buildChangesSummary(valuesSnapshot, currentValues, labelMap);
    if (changes.length > 0) {
      sendMessage(`Approved with changes:\n${changes.join('\n')}\n\nContinue to the next section.`);
    } else {
      sendMessage('Approved. Continue to the next section.');
    }
  }, [valuesSnapshot, currentValues, sections, sendMessage]);

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <h2 className="chat-title">Compliance Assistant</h2>
          <p className="chat-subtitle">IRB Submission Helper</p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          <button className="mode-badge" onClick={onModeChange} title="Change mode">
            {MODE_LABELS[mode]}
          </button>
          <button className="session-header-btn" onClick={() => setShowSessions(true)} title="Manage sessions">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
            </svg>
          </button>
        </div>
      </div>
      <MessageList messages={messages} isLoading={isLoading} />
      {showApprove && (
        <div className="approve-section">
          <p className="approve-hint">Review the fields above, edit any you want, then approve to continue.</p>
          <button className="approve-button" onClick={handleApprove}>
            Approve &amp; Continue
          </button>
        </div>
      )}
      <ChatInput
        onSend={sendMessage}
        onFileAdd={addFile}
        onFileRemove={removeFile}
        pendingFiles={pendingFiles}
        disabled={isLoading}
      />
      {showSessions && (
        <SessionManager
          currentSessionId={sessionId}
          sessions={sessionList}
          onSwitch={onSwitchSession}
          onCreate={onNewSession}
          onDelete={onDeleteSession}
          onClose={() => setShowSessions(false)}
        />
      )}
    </div>
  );
}
