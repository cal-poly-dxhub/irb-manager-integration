import type { FormElement } from '../types';
import { useFormContext } from '../FormContext';
import { motion } from 'motion/react';

interface SidebarProps {
  sections: FormElement[];
  currentSection: number;
  onSectionChange: (index: number) => void;
}

function stripHtml(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

export function Sidebar({ sections, currentSection, onSectionChange }: SidebarProps) {
  const { isVisible, values } = useFormContext();

  const isSectionComplete = (section: FormElement): boolean => {
    let hasVisibleRequired = false;
    let allRequiredAnswered = true;

    const checkRequired = (elements: FormElement[]): void => {
      for (const el of elements) {
        if (!isVisible(el.dependencies)) continue;

        if (el.required) {
          hasVisibleRequired = true;

          // For question groups with radio/checkbox, check if any child is selected
          if (el.type === 'question' && (el.compoundType === 'radio' || el.compoundType === 'checkbox')) {
            const hasSelectedChild = el.children?.some(child => values[child.dataId] === true);
            if (!hasSelectedChild) {
              allRequiredAnswered = false;
            }
          } else {
            // For text inputs and other types, check the value directly
            const value = values[el.dataId];
            if (!value || (typeof value === 'string' && value.trim() === '')) {
              allRequiredAnswered = false;
            }
          }
        }

        if (el.children) {
          checkRequired(el.children);
        }
      }
    };

    if (section.children) {
      checkRequired(section.children);
    }

    // Only mark complete if there ARE required fields and they're all answered
    return hasVisibleRequired && allRequiredAnswered;
  };

  const visibleSections = sections.filter(section => isVisible(section.dependencies));

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="currentColor" />
            <path d="M8 16h16M16 8v16" stroke="white" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>
        <h1 className="sidebar-title">IRB Submission</h1>
      </div>

      <nav className="section-nav">
        <div className="nav-label">Sections</div>
        <ul className="section-list">
          {visibleSections.map((section, index) => {
            const originalIndex = sections.indexOf(section);
            const isActive = originalIndex === currentSection;
            const isComplete = isSectionComplete(section);
            const sectionTitle = stripHtml(section.text);

            return (
              <motion.li
                key={section.dataId}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.03, duration: 0.3 }}
              >
                <button
                  className={`section-item ${isActive ? 'active' : ''} ${isComplete ? 'complete' : ''}`}
                  onClick={() => onSectionChange(originalIndex)}
                >
                  <span className="section-status">
                    {isComplete ? (
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M13.5 4.5L6 12L2.5 8.5"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : (
                      <span className="status-dot" />
                    )}
                  </span>
                  <span className="section-name">{sectionTitle}</span>
                </button>
              </motion.li>
            );
          })}
        </ul>
      </nav>

      <div className="sidebar-footer">
        <div className="progress-info">
          <span className="progress-label">Progress</span>
          <span className="progress-count">
            {visibleSections.filter(s => isSectionComplete(s)).length} / {visibleSections.length}
          </span>
        </div>
        <div className="progress-bar">
          <motion.div
            className="progress-fill"
            initial={{ width: 0 }}
            animate={{
              width: `${(visibleSections.filter(s => isSectionComplete(s)).length / visibleSections.length) * 100}%`
            }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      </div>
    </aside>
  );
}
