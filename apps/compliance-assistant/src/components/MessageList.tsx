import { useEffect, useRef } from 'react';
import type { ChatMessage as ChatMessageType } from '../types';
import { ChatMessage } from './ChatMessage';

interface MessageListProps {
  messages: ChatMessageType[];
  isLoading: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="message-list">
      {messages.length === 0 && !isLoading && (
        <div className="message-list-empty">
          <div className="empty-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect x="4" y="8" width="40" height="32" rx="4" stroke="currentColor" strokeWidth="2"/>
              <path d="M4 16l20 12 20-12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h3>Compliance Assistant</h3>
          <p>Upload your source documents and I will help you fill out the IRB submission form. You can also ask me questions about any section.</p>
        </div>
      )}
      {messages.map(message => (
        <ChatMessage key={message.id} message={message} />
      ))}
      {isLoading && (
        <div className="chat-message chat-message-assistant">
          <div className="chat-message-header">
            <span className="chat-message-role">Assistant</span>
          </div>
          <div className="chat-message-content">
            <span className="loading-dots">
              <span />
              <span />
              <span />
            </span>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
