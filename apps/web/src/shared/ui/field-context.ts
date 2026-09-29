import { createContext, use } from 'react';

export interface FieldContextValue {
  readonly controlId: string;
  readonly hintId: string;
  readonly errorId: string;
  readonly invalid: boolean;
  readonly required: boolean;
  readonly describedBy: string | undefined;
}

export const FieldContext = createContext<FieldContextValue | null>(null);

/** The ids and state of the enclosing <Field.Root>, or null outside a field. */
export function useField(): FieldContextValue | null {
  return use(FieldContext);
}
