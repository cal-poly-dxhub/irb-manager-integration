export interface Dependency {
  targetId: number;
  type: 'displayed' | 'required';
}

export interface FormElement {
  dataId: number;
  name: string;
  text: string;
  description?: string;
  required?: boolean;
  helpText?: string;
  label?: string;
  type: 'question' | 'label' | 'radio' | 'checkbox' | 'textbox' | 'textarea' | 'sponsorfinder';
  compoundType?: 'radio' | 'checkbox';
  dependencies?: Dependency[];
  children?: FormElement[];
  assignmentType?: string;
  hasMultiple?: boolean;
}

export interface ETemplate {
  templateJson: {
    children: FormElement[];
  };
}

export type FormValues = Record<number, string | boolean | string[]>;

export type AppMode = 'coauthor' | 'review' | 'adapt';

export interface FlaggedIssue {
  dataId: number;
  severity: string;
  message: string;
  suggestion?: string;
}

export interface FieldUpdate {
  dataId: number;
  value: string | boolean | string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  fieldUpdates?: FieldUpdate[];
  attachments?: { filename: string; content?: string }[];
  timestamp: Date;
}

export interface ActivityLogEntry {
  id: string;
  timestamp: Date;
  type: 'thinking' | 'toolCall' | 'toolResult' | 'fieldUpdate' | 'flaggedIssue';
  data: Record<string, unknown>;
}

export interface ChatRequest {
  sessionId?: string;
  message: string;
  conversationHistory: { role: string; content: string }[];
  attachments?: { filename: string; content: string }[];
  formValues?: Record<string, string | boolean | string[]>;
  mode?: AppMode;
}

export interface ChatResponse {
  message: string;
  fieldUpdates?: FieldUpdate[];
}
