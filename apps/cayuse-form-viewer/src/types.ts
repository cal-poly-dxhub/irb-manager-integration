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
