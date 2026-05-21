import DOMPurify from 'dompurify';
import type { ChatMessage as ChatMessageType } from '../types';

function renderMarkdown(text: string): string {
  let html = text
    // Escape HTML entities
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Bold: **text** or __text__
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

  // Italic: *text* or _text_ (but not inside words with underscores)
  html = html.replace(/(?<!\w)\*(.+?)\*(?!\w)/g, '<em>$1</em>');
  html = html.replace(/(?<!\w)_(.+?)_(?!\w)/g, '<em>$1</em>');

  // Inline code: `text`
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');

  // Numbered lists: lines starting with "1. ", "2. ", etc.
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li>$2</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ol>$1</ol>');

  // Bullet lists: lines starting with "- " or "* "
  html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, (match) => {
    // Only wrap if not already wrapped in <ol>
    if (match.startsWith('<ol>')) return match;
    return `<ul>${match}</ul>`;
  });

  // Headings (just in case): ### text
  html = html.replace(/^###\s+(.+)$/gm, '<strong>$1</strong>');
  html = html.replace(/^##\s+(.+)$/gm, '<strong>$1</strong>');

  // Blockquotes: > text
  html = html.replace(/^&gt;\s+(.+)$/gm, '<blockquote>$1</blockquote>');

  // Paragraphs: double newlines
  html = html.replace(/\n\n/g, '</p><p>');
  // Single newlines within paragraphs
  html = html.replace(/\n/g, '<br/>');

  html = `<p>${html}</p>`;

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '');

  return DOMPurify.sanitize(html);
}

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const fieldUpdateCount = message.fieldUpdates?.length ?? 0;

  return (
    <div className={`chat-message ${isUser ? 'chat-message-user' : 'chat-message-assistant'}`}>
      <div className="chat-message-header">
        <span className="chat-message-role">{isUser ? 'You' : 'Assistant'}</span>
        <span className="chat-message-time">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
      <div
        className="chat-message-content"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
      />
      {message.attachments && message.attachments.length > 0 && (
        <div className="chat-message-attachments">
          {message.attachments.map((att) => (
            <span key={att.filename} className="attachment-badge">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1v8M3.5 5.5L7 9l3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M1.5 10.5v1a1 1 0 001 1h9a1 1 0 001-1v-1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              {att.filename}
            </span>
          ))}
        </div>
      )}
      {fieldUpdateCount > 0 && (
        <div className="chat-message-field-updates">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M11.5 3.5L5.5 9.5L2.5 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Updated {fieldUpdateCount} field{fieldUpdateCount !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
