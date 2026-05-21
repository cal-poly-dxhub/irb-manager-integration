import type { AppMode } from '../types';

interface ModeSelectorProps {
  onSelect: (mode: AppMode) => void;
}

export function ModeSelector({ onSelect }: ModeSelectorProps) {
  return (
    <div className="mode-selector">
      <h1 className="mode-selector-title">How would you like to work today?</h1>
      <div className="mode-cards">
        <button className="mode-card" onClick={() => onSelect('coauthor')}>
          <div className="mode-card-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </div>
          <h3 className="mode-card-title">Co-Author</h3>
          <p className="mode-card-description">
            Work through the form together, section by section. The AI fills fields based on your research description and waits for your approval before moving on.
          </p>
        </button>

        <button className="mode-card" onClick={() => onSelect('review')}>
          <div className="mode-card-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </div>
          <h3 className="mode-card-title">Review</h3>
          <p className="mode-card-description">
            Get a compliance review of your completed form. The AI reads your submission and flags issues with severity ratings and suggestions.
          </p>
        </button>

        <button className="mode-card" onClick={() => onSelect('adapt')}>
          <div className="mode-card-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="17 1 21 5 17 9" />
              <path d="M3 11V9a4 4 0 0 1 4-4h14" />
              <polyline points="7 23 3 19 7 15" />
              <path d="M21 13v2a4 4 0 0 1-4 4H3" />
            </svg>
          </div>
          <h3 className="mode-card-title">Adapt</h3>
          <p className="mode-card-description">
            Reuse a previous submission for a new study. The AI identifies what needs updating and helps you make targeted changes.
          </p>
        </button>
      </div>
    </div>
  );
}
