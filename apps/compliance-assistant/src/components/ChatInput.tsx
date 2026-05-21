import { useState, useRef, type KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  onFileAdd: (file: File) => void;
  onFileRemove: (filename: string) => void;
  pendingFiles: { filename: string }[];
  disabled: boolean;
}

export function ChatInput({ onSend, onFileAdd, onFileRemove, pendingFiles, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (input.trim() || pendingFiles.length > 0) {
      onSend(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      for (const file of Array.from(files)) {
        onFileAdd(file);
      }
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="chat-input-area">
      {pendingFiles.length > 0 && (
        <div className="pending-files">
          {pendingFiles.map((f) => (
            <span key={f.filename} className="pending-file-badge">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M8 1H3.5a1 1 0 00-1 1v10a1 1 0 001 1h7a1 1 0 001-1V4.5L8 1z" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M8 1v3.5h3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              {f.filename}
              <button
                className="pending-file-remove"
                onClick={() => onFileRemove(f.filename)}
                type="button"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M9 3L3 9M3 3l6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="chat-input-row">
        <button
          className="attach-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          type="button"
          title="Attach file (TXT, PDF)"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M17.5 9.31l-7.78 7.78a4.125 4.125 0 01-5.83-5.83l7.78-7.78a2.75 2.75 0 013.89 3.89l-7.79 7.77a1.375 1.375 0 01-1.94-1.94l7.19-7.19" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <textarea
          className="chat-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your research or ask a question..."
          rows={1}
          disabled={disabled}
        />
        <button
          className="send-button"
          onClick={handleSend}
          disabled={disabled || (!input.trim() && pendingFiles.length === 0)}
          type="button"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M17.5 2.5l-7.5 15-2.5-6.25L1.25 8.75l16.25-6.25z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M17.5 2.5l-10 8.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.text,.md,.csv,.pdf"
        multiple
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
    </div>
  );
}
