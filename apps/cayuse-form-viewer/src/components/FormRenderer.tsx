import type { FormElement } from '../types';
import { useFormContext } from '../FormContext';
import { motion, AnimatePresence } from 'motion/react';
import DOMPurify from 'dompurify';

interface FormRendererProps {
  elements: FormElement[];
  depth?: number;
}

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['strong', 'em', 'br', 'ul', 'ol', 'li', 'a', 'p', 'div', 'span', 'u'],
    ALLOWED_ATTR: ['href', 'target', 'title', 'class']
  });
}

export function FormRenderer({ elements, depth = 0 }: FormRendererProps) {
  const { isVisible } = useFormContext();

  return (
    <div className="form-renderer">
      <AnimatePresence mode="sync">
        {elements.map(element => {
          if (!isVisible(element.dependencies)) {
            return null;
          }

          return (
            <motion.div
              key={element.dataId}
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{ opacity: 1, height: 'auto', marginBottom: depth === 0 ? 24 : 16 }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
              style={{ overflow: 'hidden' }}
            >
              <ElementRenderer element={element} depth={depth} />
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

interface ElementRendererProps {
  element: FormElement;
  depth: number;
}

function ElementRenderer({ element, depth }: ElementRendererProps) {
  const { values, setValue, isRequired } = useFormContext();

  const renderLabel = () => (
    <div
      className="form-label"
      dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.text) }}
    />
  );

  const renderTextInput = () => {
    const isTextarea = element.type === 'textarea';
    const required = isRequired(element);
    const value = (values[element.dataId] as string) || '';

    return (
      <div className={`form-field ${required ? 'required' : ''}`}>
        <label className="field-label">
          <span dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.text) }} />
          {required && <span className="required-indicator">*</span>}
        </label>
        {element.description && (
          <div
            className="field-description"
            dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.description) }}
          />
        )}
        {isTextarea ? (
          <textarea
            className="text-input textarea"
            value={value}
            onChange={(e) => setValue(element.dataId, e.target.value)}
            rows={4}
          />
        ) : (
          <input
            type="text"
            className="text-input"
            value={value}
            onChange={(e) => setValue(element.dataId, e.target.value)}
          />
        )}
      </div>
    );
  };

  const renderQuestion = () => {
    const required = isRequired(element);
    const hasCompoundType = element.compoundType === 'radio' || element.compoundType === 'checkbox';

    return (
      <div className={`form-question depth-${Math.min(depth, 3)} ${required ? 'required' : ''}`}>
        {element.text && (
          <div className="question-header">
            <span
              className="question-text"
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.text) }}
            />
            {required && <span className="required-indicator">*</span>}
          </div>
        )}
        {element.description && (
          <div
            className="question-description"
            dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.description) }}
          />
        )}
        {hasCompoundType && element.children ? (
          <div className={`option-group ${element.compoundType}`}>
            {element.children.map(child => (
              <OptionRenderer
                key={child.dataId}
                element={child}
                parentId={element.dataId}
                groupType={element.compoundType!}
                groupName={element.name}
                siblingIds={element.children!.map(c => c.dataId)}
              />
            ))}
          </div>
        ) : element.children ? (
          <FormRenderer elements={element.children} depth={depth + 1} />
        ) : null}
      </div>
    );
  };

  const renderSponsorFinder = () => {
    const required = isRequired(element);
    const value = (values[element.dataId] as string) || '';

    return (
      <div className={`form-field sponsor-finder ${required ? 'required' : ''}`}>
        <label className="field-label">
          <span dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.text) }} />
          {required && <span className="required-indicator">*</span>}
        </label>
        {element.description && (
          <div
            className="field-description"
            dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.description) }}
          />
        )}
        <div className="sponsor-finder-input">
          <input
            type="text"
            className="text-input"
            value={value}
            onChange={(e) => setValue(element.dataId, e.target.value)}
            placeholder="Enter sponsor name..."
          />
          <button type="button" className="find-sponsor-btn">
            Find Sponsors
          </button>
        </div>
      </div>
    );
  };

  switch (element.type) {
    case 'label':
      return renderLabel();
    case 'textbox':
    case 'textarea':
      return renderTextInput();
    case 'question':
      return renderQuestion();
    case 'sponsorfinder':
      return renderSponsorFinder();
    case 'radio':
    case 'checkbox':
      return (
        <div className="standalone-option">
          <OptionRenderer
            element={element}
            parentId={element.dataId}
            groupType={element.type}
            groupName={element.name}
            siblingIds={[element.dataId]}
          />
        </div>
      );
    default:
      return null;
  }
}

interface OptionRendererProps {
  element: FormElement;
  parentId: number;
  groupType: 'radio' | 'checkbox';
  groupName: string;
  siblingIds?: number[];
}

function OptionRenderer({ element, groupType, groupName, siblingIds = [] }: OptionRendererProps) {
  const { values, setValue, isVisible } = useFormContext();

  if (!isVisible(element.dependencies)) {
    return null;
  }

  const isChecked = values[element.dataId] === true;

  const handleChange = () => {
    if (groupType === 'checkbox') {
      setValue(element.dataId, !isChecked);
    } else {
      // For radio buttons, clear all siblings first, then set this one
      siblingIds.forEach(id => {
        if (id !== element.dataId) {
          setValue(id, false);
        }
      });
      setValue(element.dataId, true);
    }
  };

  return (
    <motion.div
      className="option-item"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <label className="option-label">
        <input
          type={groupType}
          name={groupType === 'radio' ? groupName : undefined}
          checked={isChecked}
          onChange={handleChange}
          className="option-input"
        />
        <span className="option-indicator" />
        <span
          className="option-text"
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.text) }}
        />
      </label>
      <AnimatePresence>
        {isChecked && element.children && element.children.length > 0 && (
          <motion.div
            className="option-children"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <FormRenderer elements={element.children} depth={1} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
