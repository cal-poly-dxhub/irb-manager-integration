import { useState, useEffect, useRef } from 'react';
import { FormProvider, useFormContext } from './FormContext';
import { SplitLayout } from './components/SplitLayout';
import { ChatPanel } from './components/ChatPanel';
import { FormPanel } from './components/FormPanel';
import { ActivityDrawer } from './components/ActivityDrawer';
import { ModeSelector } from './components/ModeSelector';
import { useChat } from './hooks/useChat';
import { useSession } from './hooks/useSession';
import type { ETemplate, FormElement, FormValues, ChatMessage, AppMode } from './types';
import './App.css';

function AppContent({ sections }: { sections: FormElement[] }) {
  const [mode, setMode] = useState<AppMode | null>(null);
  const { sessionId, isSessionLoading, sessionList, debouncedSaveForm, switchSession, createNewSession, deleteSession } = useSession({
    onSessionLoaded: handleSessionLoaded,
  });
  const { activityLog, setMessages, flaggedIssues, valuesSnapshot, ...chatProps } = useChat(sessionId, mode || 'coauthor');
  const { values, replaceValues } = useFormContext();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const prevValuesRef = useRef(values);

  // Track refs for the session loaded callback
  const replaceValuesRef = useRef(replaceValues);
  const setMessagesRef = useRef(setMessages);
  replaceValuesRef.current = replaceValues;
  setMessagesRef.current = setMessages;

  function handleSessionLoaded(data: {
    formValues: FormValues;
    messages: ChatMessage[];
  }) {
    replaceValuesRef.current(data.formValues);
    setMessagesRef.current(data.messages);
  }

  // Debounced save on form value changes
  useEffect(() => {
    if (prevValuesRef.current !== values) {
      prevValuesRef.current = values;
      debouncedSaveForm(values);
    }
  }, [values, debouncedSaveForm]);

  if (isSessionLoading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner">
          <div className="spinner" />
        </div>
        <p className="loading-text">Loading session...</p>
      </div>
    );
  }

  if (!mode) {
    return <ModeSelector onSelect={setMode} />;
  }

  return (
    <>
      <SplitLayout
        chatPanel={
          <ChatPanel
            {...chatProps}
            mode={mode}
            onModeChange={() => setMode(null)}
            valuesSnapshot={valuesSnapshot}
            currentValues={values}
            sections={sections}
            sessionId={sessionId}
            sessionList={sessionList}
            onSwitchSession={switchSession}
            onNewSession={createNewSession}
            onDeleteSession={deleteSession}
          />
        }
        formPanel={<FormPanel sections={sections} isLocked={chatProps.isLoading} flaggedIssues={flaggedIssues} />}
      />
      <button
        className="activity-toggle-btn"
        onClick={() => setDrawerOpen(prev => !prev)}
        title="Toggle agent activity log"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        {activityLog.length > 0 && (
          <span className="activity-toggle-badge">{activityLog.length}</span>
        )}
      </button>
      <ActivityDrawer
        entries={activityLog}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </>
  );
}

function App() {
  const [template, setTemplate] = useState<ETemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTemplate() {
      try {
        const response = await fetch('/Initial Submission_Revision9.etemplate');
        if (!response.ok) {
          throw new Error(`Failed to load template: ${response.statusText}`);
        }
        const data = await response.json();
        setTemplate(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load template');
      } finally {
        setLoading(false);
      }
    }

    loadTemplate();
  }, []);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner">
          <div className="spinner" />
        </div>
        <p className="loading-text">Loading form...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-screen">
        <div className="error-icon">!</div>
        <h2>Unable to load form</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!template) {
    return null;
  }

  return (
    <FormProvider>
      <AppContent sections={template.templateJson.children} />
    </FormProvider>
  );
}

export default App;
