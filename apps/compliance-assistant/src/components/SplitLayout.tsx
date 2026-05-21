import type { ReactNode } from 'react';

interface SplitLayoutProps {
  chatPanel: ReactNode;
  formPanel: ReactNode;
}

export function SplitLayout({ chatPanel, formPanel }: SplitLayoutProps) {
  return (
    <div className="split-layout">
      <div className="split-chat">
        {chatPanel}
      </div>
      <div className="split-divider" />
      <div className="split-form">
        {formPanel}
      </div>
    </div>
  );
}
