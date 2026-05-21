import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { FormElement, FormValues, Dependency } from './types';

interface FormContextType {
  values: FormValues;
  setValue: (dataId: number, value: string | boolean | string[]) => void;
  setValues: (updates: FormValues) => void;
  replaceValues: (values: FormValues) => void;
  isVisible: (dependencies?: Dependency[]) => boolean;
  isRequired: (element: FormElement) => boolean;
  getSelectedIds: () => Set<number>;
}

const FormContext = createContext<FormContextType | null>(null);

export function useFormContext() {
  const context = useContext(FormContext);
  if (!context) {
    throw new Error('useFormContext must be used within FormProvider');
  }
  return context;
}

interface FormProviderProps {
  children: ReactNode;
  initialValues?: FormValues;
}

export function FormProvider({ children, initialValues }: FormProviderProps) {
  const [values, setValuesState] = useState<FormValues>(initialValues ?? {});

  const setValue = useCallback((dataId: number, value: string | boolean | string[]) => {
    setValuesState(prev => ({
      ...prev,
      [dataId]: value
    }));
  }, []);

  const setValues = useCallback((updates: FormValues) => {
    setValuesState(prev => ({
      ...prev,
      ...updates
    }));
  }, []);

  const replaceValues = useCallback((values: FormValues) => {
    setValuesState(values);
  }, []);

  const getSelectedIds = useCallback((): Set<number> => {
    const selected = new Set<number>();
    Object.entries(values).forEach(([id, value]) => {
      if (value === true || (typeof value === 'string' && value.length > 0)) {
        selected.add(Number(id));
      }
      if (Array.isArray(value) && value.length > 0) {
        selected.add(Number(id));
      }
    });
    return selected;
  }, [values]);

  const isVisible = useCallback((dependencies?: Dependency[]): boolean => {
    if (!dependencies || dependencies.length === 0) {
      return true;
    }

    const displayDeps = dependencies.filter(d => d.type === 'displayed');
    if (displayDeps.length === 0) {
      return true;
    }

    const selectedIds = getSelectedIds();
    return displayDeps.some(dep => selectedIds.has(dep.targetId));
  }, [getSelectedIds]);

  const isRequired = useCallback((element: FormElement): boolean => {
    if (element.required) return true;

    if (!element.dependencies) return false;

    const requiredDeps = element.dependencies.filter(d => d.type === 'required');
    if (requiredDeps.length === 0) return false;

    const selectedIds = getSelectedIds();
    return requiredDeps.some(dep => selectedIds.has(dep.targetId));
  }, [getSelectedIds]);

  const contextValue = useMemo(() => ({
    values,
    setValue,
    setValues,
    replaceValues,
    isVisible,
    isRequired,
    getSelectedIds
  }), [values, setValue, setValues, replaceValues, isVisible, isRequired, getSelectedIds]);

  return (
    <FormContext.Provider value={contextValue}>
      {children}
    </FormContext.Provider>
  );
}
