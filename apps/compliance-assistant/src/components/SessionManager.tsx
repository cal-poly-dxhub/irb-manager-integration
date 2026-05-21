import { useState } from 'react';
import type { StoredSession } from '../hooks/useSession';

interface SessionManagerProps {
  currentSessionId: string | null;
  sessions: StoredSession[];
  onSwitch: (sessionId: string) => void;
  onCreate: () => void;
  onDelete: (sessionId: string) => void;
  onClose: () => void;
}

export function SessionManager({
  currentSessionId,
  sessions,
  onSwitch,
  onCreate,
  onDelete,
  onClose,
}: SessionManagerProps) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const handleDelete = (id: string) => {
    if (confirmDelete === id) {
      onDelete(id);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(id);
    }
  };

  return (
    <div className="session-manager-backdrop" onClick={onClose}>
      <div className="session-manager" onClick={(e) => e.stopPropagation()}>
        <div className="session-manager-header">
          <h3>Sessions</h3>
          <button className="session-manager-close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="session-manager-body">
          <button className="session-new-btn" onClick={onCreate}>
            + New Session
          </button>

          <div className="session-list">
            {sessions.map((session) => {
              const isCurrent = session.id === currentSessionId;
              const idPrefix = session.id.slice(0, 8);
              const date = new Date(session.updatedAt || session.createdAt).toLocaleDateString();

              return (
                <div key={session.id} className={`session-item ${isCurrent ? 'session-item-current' : ''}`}>
                  <div className="session-item-info">
                    <span className="session-item-id">{idPrefix}</span>
                    <span className="session-item-date">{date}</span>
                    <span className="session-item-count">{session.messageCount} messages</span>
                    {isCurrent && <span className="session-item-badge">current</span>}
                  </div>
                  <div className="session-item-actions">
                    {!isCurrent && (
                      <button className="session-action-btn" onClick={() => onSwitch(session.id)}>
                        Switch
                      </button>
                    )}
                    <button
                      className="session-action-btn session-action-delete"
                      onClick={() => handleDelete(session.id)}
                    >
                      {confirmDelete === session.id ? 'Confirm' : 'Delete'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
