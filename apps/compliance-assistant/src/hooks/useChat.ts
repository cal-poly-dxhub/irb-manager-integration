import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, FieldUpdate, ActivityLogEntry, AppMode, FlaggedIssue, FormValues } from '../types';
import { sendChatMessageStream, readTextFile, parsePdf } from '../api';
import { useFormContext } from '../FormContext';

let messageIdCounter = 0;
function generateId(): string {
  return `msg-${Date.now()}-${++messageIdCounter}`;
}

let logIdCounter = 0;
function generateLogId(): string {
  return `log-${Date.now()}-${++logIdCounter}`;
}

export function useChat(sessionId: string | null, mode: AppMode) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<{ filename: string; content: string }[]>([]);
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>([]);
  const [flaggedIssues, setFlaggedIssues] = useState<FlaggedIssue[]>([]);
  const [valuesSnapshot, setValuesSnapshot] = useState<FormValues | null>(null);
  const { values, setValue } = useFormContext();
  const fieldUpdatesRef = useRef<FieldUpdate[]>([]);
  const valuesRef = useRef(values);
  valuesRef.current = values;

  const addFile = useCallback(async (file: File) => {
    const isPdf = file.name.toLowerCase().endsWith('.pdf');
    const parsed = isPdf ? await parsePdf(file) : await readTextFile(file);
    setPendingFiles(prev => [...prev, parsed]);
  }, []);

  const removeFile = useCallback((filename: string) => {
    setPendingFiles(prev => prev.filter(f => f.filename !== filename));
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() && pendingFiles.length === 0) return;

    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      attachments: pendingFiles.map(f => ({ filename: f.filename, content: f.content })),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const attachments = [...pendingFiles];
    setPendingFiles([]);
    setIsLoading(true);
    fieldUpdatesRef.current = [];
    setFlaggedIssues([]);

    // Create a placeholder assistant message that updates as events stream in
    const assistantId = generateId();
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      fieldUpdates: [],
      timestamp: new Date(),
    }]);

    try {
      // Build conversation history with attachment content baked in
      const conversationHistory = messages.map(m => {
        if (m.attachments && m.attachments.some(a => a.content)) {
          const parts = m.attachments
            .filter(a => a.content)
            .map(a => `[Attached file: ${a.filename}]\n${a.content}`);
          parts.push(m.content);
          return { role: m.role, content: parts.filter(Boolean).join('\n\n') };
        }
        return { role: m.role, content: m.content };
      });

      const formValues: Record<string, string | boolean | string[]> = {};
      for (const [key, val] of Object.entries(values)) {
        formValues[String(key)] = val;
      }

      await sendChatMessageStream(
        {
          sessionId: sessionId ?? undefined,
          message: content,
          conversationHistory,
          attachments: attachments.length > 0 ? attachments : undefined,
          formValues,
          mode,
        },
        {
          onFieldUpdate(update: FieldUpdate) {
            // Apply to form immediately
            setValue(update.dataId, update.value);
            // Track on the assistant message
            fieldUpdatesRef.current = [...fieldUpdatesRef.current, update];
            setMessages(prev => prev.map(m =>
              m.id === assistantId
                ? { ...m, fieldUpdates: fieldUpdatesRef.current }
                : m
            ));
          },
          onMessage(message: string) {
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: message } : m
            ));
          },
          onError(message: string) {
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: message } : m
            ));
          },
          onDone() {
            setIsLoading(false);
            if (mode === 'coauthor') {
              setValuesSnapshot({ ...valuesRef.current });
            }
          },
          onToolCall(data) {
            setActivityLog(prev => [...prev, {
              id: generateLogId(),
              timestamp: new Date(),
              type: 'toolCall',
              data,
            }]);
          },
          onToolResult(data) {
            setActivityLog(prev => [...prev, {
              id: generateLogId(),
              timestamp: new Date(),
              type: 'toolResult',
              data,
            }]);
          },
          onThinking(text) {
            setActivityLog(prev => [...prev, {
              id: generateLogId(),
              timestamp: new Date(),
              type: 'thinking',
              data: { text },
            }]);
          },
          onFlaggedIssue(issue: FlaggedIssue) {
            setFlaggedIssues(prev => [...prev, issue]);
            setActivityLog(prev => [...prev, {
              id: generateLogId(),
              timestamp: new Date(),
              type: 'flaggedIssue',
              data: issue as unknown as Record<string, unknown>,
            }]);
          },
        },
      );
    } catch (error) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId
          ? { ...m, content: `Sorry, something went wrong: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.` }
          : m
      ));
      setIsLoading(false);
    }
  }, [messages, pendingFiles, values, setValue, sessionId, mode]);

  return {
    messages,
    setMessages,
    isLoading,
    pendingFiles,
    activityLog,
    flaggedIssues,
    valuesSnapshot,
    sendMessage,
    addFile,
    removeFile,
  };
}
