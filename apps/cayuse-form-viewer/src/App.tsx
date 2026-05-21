import { useState, useEffect } from 'react';
import { FormProvider, useFormContext } from './FormContext';
import { FormRenderer } from './components/FormRenderer';
import { Sidebar } from './components/Sidebar';
import type { ETemplate, FormElement } from './types';
import { motion, AnimatePresence } from 'motion/react';
import './App.css';

function stripHtml(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

function FormContent({ sections }: { sections: FormElement[] }) {
  const [currentSection, setCurrentSection] = useState(0);
  const { isVisible } = useFormContext();

  const currentSectionData = sections[currentSection];

  const goToNextVisibleSection = () => {
    for (let i = currentSection + 1; i < sections.length; i++) {
      if (isVisible(sections[i].dependencies)) {
        setCurrentSection(i);
        return;
      }
    }
  };

  const goToPrevVisibleSection = () => {
    for (let i = currentSection - 1; i >= 0; i--) {
      if (isVisible(sections[i].dependencies)) {
        setCurrentSection(i);
        return;
      }
    }
  };

  const hasNextSection = () => {
    for (let i = currentSection + 1; i < sections.length; i++) {
      if (isVisible(sections[i].dependencies)) return true;
    }
    return false;
  };

  const hasPrevSection = () => {
    for (let i = currentSection - 1; i >= 0; i--) {
      if (isVisible(sections[i].dependencies)) return true;
    }
    return false;
  };

  return (
    <div className="app-layout">
      <Sidebar
        sections={sections}
        currentSection={currentSection}
        onSectionChange={setCurrentSection}
      />

      <main className="main-content">
        <div className="content-header">
          <div className="breadcrumb">
            <span className="breadcrumb-item">IRB Submission</span>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current">{stripHtml(currentSectionData?.text || '')}</span>
          </div>
          <button className="save-button">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M14.25 15.75H3.75C3.35218 15.75 2.97064 15.592 2.68934 15.3107C2.40804 15.0294 2.25 14.6478 2.25 14.25V3.75C2.25 3.35218 2.40804 2.97064 2.68934 2.68934C2.97064 2.40804 3.35218 2.25 3.75 2.25H12L15.75 6V14.25C15.75 14.6478 15.592 15.0294 15.3107 15.3107C15.0294 15.592 14.6478 15.75 14.25 15.75Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M12.75 15.75V9.75H5.25V15.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M5.25 2.25V6H11.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Save Progress
          </button>
        </div>

        <div className="content-body">
          <AnimatePresence mode="wait">
            {currentSectionData && (
              <motion.div
                key={currentSectionData.dataId}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="section-content"
              >
                <h2 className="section-title">{stripHtml(currentSectionData.text)}</h2>
                {currentSectionData.children && (
                  <FormRenderer elements={currentSectionData.children} />
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="content-footer">
          <button
            className="nav-button prev"
            onClick={goToPrevVisibleSection}
            disabled={!hasPrevSection()}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12.5 15L7.5 10L12.5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Previous
          </button>
          <button
            className="nav-button next"
            onClick={goToNextVisibleSection}
            disabled={!hasNextSection()}
          >
            Next
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M7.5 15L12.5 10L7.5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </main>
    </div>
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
      <FormContent sections={template.templateJson.children} />
    </FormProvider>
  );
}

export default App;
