import { useState } from 'react';
import { useFormContext } from '../FormContext';
import { FormRenderer } from './FormRenderer';
import { Sidebar } from './Sidebar';
import type { FormElement, FlaggedIssue } from '../types';
import { motion, AnimatePresence } from 'motion/react';

function stripHtml(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

interface FormPanelProps {
  sections: FormElement[];
  isLocked?: boolean;
  flaggedIssues?: FlaggedIssue[];
}

export function FormPanel({ sections, isLocked = false, flaggedIssues = [] }: FormPanelProps) {
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
    <div className={`form-layout${isLocked ? ' form-locked' : ''}`}>
      {isLocked && (
        <div className="form-lock-overlay">
          <div className="form-lock-banner">
            <div className="form-lock-spinner" />
            <span>AI is filling out the form...</span>
          </div>
        </div>
      )}
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
                  <FormRenderer elements={currentSectionData.children} flaggedIssues={flaggedIssues} />
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
