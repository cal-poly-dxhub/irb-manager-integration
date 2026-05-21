import { useEffect, useRef, useState } from 'react';
import type { ActivityLogEntry } from '../types';

interface ActivityDrawerProps {
  entries: ActivityLogEntry[];
  isOpen: boolean;
  onClose: () => void;
}

const TOOL_LABELS: Record<string, string> = {
  get_visible_sections: 'Get Visible Sections',
  get_fields_in_section: 'Get Fields in Section',
  get_field_guidance: 'Get Field Guidance',
  fill_field: 'Fill Field',
  search_past_submissions: 'Search Past Submissions',
  get_form_progress: 'Get Form Progress',
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '...' : text;
}

function ToolCallEntry({ data }: { data: Record<string, unknown> }) {
  const name = data.name as string;
  const input = data.input as Record<string, unknown>;
  const label = TOOL_LABELS[name] || name;

  const fieldLabel = data.fieldLabel as string | undefined;

  let detail = '';
  if (name === 'get_fields_in_section') {
    detail = `Section: "${input.section_name}"`;
  } else if (name === 'get_field_guidance') {
    detail = fieldLabel ? `"${truncate(fieldLabel, 60)}" (#${input.data_id})` : `Field #${input.data_id}`;
  } else if (name === 'fill_field') {
    const val = String(input.value || '');
    const fieldName = fieldLabel ? `"${truncate(fieldLabel, 50)}"` : `#${input.data_id}`;
    detail = `${fieldName} = "${truncate(val, 80)}"`;
  } else if (name === 'search_past_submissions') {
    const q = String(input.query || '');
    detail = `Query: "${q}"`;
    if (input.data_id) {
      detail += fieldLabel ? ` (${truncate(fieldLabel, 40)})` : ` (field #${input.data_id})`;
    }
  }

  return (
    <div className="activity-entry activity-tool-call">
      <div className="activity-icon activity-icon-tool">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
        </svg>
      </div>
      <div className="activity-content">
        <span className="activity-tool-name">{label}</span>
        {detail && <span className="activity-tool-detail">{detail}</span>}
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ResultSections({ result }: { result: any }) {
  const sections = result.sections as { name: string; fieldCount: number; dataId: number }[];
  return (
    <div className="activity-result-list">
      {sections.map((s, i) => (
        <div key={i} className="activity-result-list-item">
          <span className="activity-result-label">{s.name}</span>
          <span className="activity-result-meta">{s.fieldCount} fields</span>
        </div>
      ))}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ResultFields({ result }: { result: any }) {
  const fields = result.fields as { dataId: number; text: string; type: string; required: boolean; currentValue: unknown }[];
  return (
    <div className="activity-result-list">
      {fields.map((f, i) => (
        <div key={i} className="activity-result-list-item">
          <span className="activity-result-label">
            #{f.dataId} {truncate(f.text, 60)}
          </span>
          <span className="activity-result-meta">
            {f.type}{f.required ? ' *' : ''}
            {f.currentValue != null ? ` = "${truncate(String(f.currentValue), 30)}"` : ''}
          </span>
        </div>
      ))}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ResultSearch({ result }: { result: any }) {
  const results = result.results as { protocol: string; dataId: number; text: string; score: number }[];
  if (!results || results.length === 0) {
    return <span className="activity-result-meta">No results found</span>;
  }
  return (
    <div className="activity-result-list">
      {results.map((r, i) => (
        <div key={i} className="activity-result-search-item">
          <div className="activity-result-search-header">
            <span className="activity-result-label">{r.protocol}</span>
            <span className="activity-result-score">{(r.score * 100).toFixed(1)}%</span>
          </div>
          <span className="activity-result-search-text">{truncate(r.text, 200)}</span>
        </div>
      ))}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ResultGuidance({ result }: { result: any }) {
  return (
    <div className="activity-result-list">
      {result.fieldInfo && (
        <div className="activity-result-list-item">
          <span className="activity-result-label">
            {result.fieldInfo.label || 'Unknown field'}
          </span>
          <span className="activity-result-meta">
            {result.fieldInfo.type}{result.fieldInfo.required ? ' (required)' : ''}
            {result.fieldInfo.section ? ` in ${result.fieldInfo.section}` : ''}
          </span>
        </div>
      )}
      {result.prompt && (
        <div className="activity-result-guidance-block">
          <span className="activity-result-guidance-label">Prompt</span>
          <span className="activity-result-guidance-text">{truncate(result.prompt, 200)}</span>
        </div>
      )}
      {result.commonIssues && result.commonIssues.length > 0 && (
        <div className="activity-result-guidance-block">
          <span className="activity-result-guidance-label">Common issues</span>
          {result.commonIssues.map((issue: string, i: number) => (
            <span key={i} className="activity-result-guidance-text">- {truncate(issue, 100)}</span>
          ))}
        </div>
      )}
      {result.pastExamples && result.pastExamples.length > 0 && (
        <div className="activity-result-guidance-block">
          <span className="activity-result-guidance-label">
            {result.pastExamples.length} past example{result.pastExamples.length > 1 ? 's' : ''}
          </span>
          {result.pastExamples.map((ex: { protocol: string; text: string }, i: number) => (
            <div key={i} className="activity-result-search-item">
              <span className="activity-result-label">{ex.protocol}</span>
              <span className="activity-result-search-text">{truncate(ex.text, 150)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ResultProgress({ result }: { result: any }) {
  const sections = result.sectionProgress as { section: string; totalFields: number; filledFields: number }[];
  return (
    <div className="activity-result-list">
      <div className="activity-result-list-item">
        <span className="activity-result-label">Total filled</span>
        <span className="activity-result-meta">{result.totalFieldsFilled} fields</span>
      </div>
      {sections && sections.map((s, i) => (
        <div key={i} className="activity-result-list-item">
          <span className="activity-result-label">{s.section}</span>
          <span className="activity-result-meta">{s.filledFields}/{s.totalFields}</span>
        </div>
      ))}
    </div>
  );
}

function ToolResultEntry({ data }: { data: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const name = data.name as string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const result = data.result as any;

  if (result.error) {
    return (
      <div className="activity-entry activity-tool-result">
        <div className="activity-icon activity-icon-result-error">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </div>
        <div className="activity-content">
          <span className="activity-result-error">Error: {result.error}</span>
        </div>
      </div>
    );
  }

  // Summary line
  let summary = '';
  if (name === 'fill_field' && result.success) {
    const val = String(result.valueSet || '');
    summary = `Set "${truncate(result.field || '', 50)}" to "${truncate(val, 80)}"`;
  } else if (name === 'get_visible_sections') {
    summary = `${result.totalVisible} section${result.totalVisible !== 1 ? 's' : ''} visible`;
  } else if (name === 'get_fields_in_section') {
    summary = `${result.totalFields} field${result.totalFields !== 1 ? 's' : ''} in "${result.section}"`;
  } else if (name === 'search_past_submissions') {
    summary = `${result.totalResults} result${result.totalResults !== 1 ? 's' : ''} found`;
  } else if (name === 'get_form_progress') {
    summary = `${result.totalFieldsFilled} field${result.totalFieldsFilled !== 1 ? 's' : ''} filled`;
  } else if (name === 'get_field_guidance') {
    summary = result.prompt ? 'Guidance loaded' : 'Basic field info only';
  }

  const hasDetails = name !== 'fill_field';

  return (
    <div className="activity-entry activity-tool-result">
      <div className="activity-icon activity-icon-result">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="9 11 12 14 22 4" />
          <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
        </svg>
      </div>
      <div className="activity-content">
        <div className="activity-result-header">
          <span className="activity-result-summary">{summary}</span>
          {hasDetails && (
            <button className="activity-expand-btn" onClick={() => setExpanded(!expanded)}>
              {expanded ? 'Hide' : 'Details'}
            </button>
          )}
        </div>
        {expanded && (
          <div className="activity-result-expanded">
            {name === 'get_visible_sections' && <ResultSections result={result} />}
            {name === 'get_fields_in_section' && <ResultFields result={result} />}
            {name === 'search_past_submissions' && <ResultSearch result={result} />}
            {name === 'get_field_guidance' && <ResultGuidance result={result} />}
            {name === 'get_form_progress' && <ResultProgress result={result} />}
          </div>
        )}
      </div>
    </div>
  );
}

function ThinkingEntry({ data }: { data: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const text = data.text as string;
  const isLong = text.length > 150;

  return (
    <div className="activity-entry activity-thinking">
      <div className="activity-icon activity-icon-thinking">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" />
        </svg>
      </div>
      <div className="activity-content">
        <span className="activity-thinking-text">
          {expanded || !isLong ? text : truncate(text, 150)}
        </span>
        {isLong && (
          <button className="activity-expand-btn" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Less' : 'More'}
          </button>
        )}
      </div>
    </div>
  );
}

export function ActivityDrawer({ entries, isOpen, onClose }: ActivityDrawerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [entries.length, isOpen]);

  return (
    <>
      {isOpen && <div className="activity-backdrop" onClick={onClose} />}
      <div className={`activity-drawer${isOpen ? ' activity-drawer-open' : ''}`}>
        <div className="activity-drawer-header">
          <h3 className="activity-drawer-title">Agent Activity</h3>
          <span className="activity-drawer-count">{entries.length} events</span>
          <button className="activity-drawer-close" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="activity-drawer-body">
          {entries.length === 0 ? (
            <div className="activity-empty">
              <p>No activity yet. Send a message to see the agent work.</p>
            </div>
          ) : (
            <div className="activity-timeline">
              {entries.map((entry) => (
                <div key={entry.id} className="activity-timeline-item">
                  <span className="activity-time">{formatTime(entry.timestamp)}</span>
                  {entry.type === 'toolCall' && <ToolCallEntry data={entry.data} />}
                  {entry.type === 'toolResult' && <ToolResultEntry data={entry.data} />}
                  {entry.type === 'thinking' && <ThinkingEntry data={entry.data} />}
                  {entry.type === 'fieldUpdate' && (
                    <div className="activity-entry activity-field-update">
                      <div className="activity-icon activity-icon-field">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                      </div>
                      <div className="activity-content">
                        <span className="activity-field-update-text">
                          Updated field #{String(entry.data.dataId)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
