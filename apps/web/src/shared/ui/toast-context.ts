import { createContext, use } from 'react';

/** Tones follow the color meanings: a verified outcome is `decision`, a failure or refusal is `risk`. */
export type ToastTone = 'neutral' | 'decision' | 'risk';

export interface ToastMessage {
  readonly title: string;
  readonly description?: string;
  readonly tone?: ToastTone;
}

export interface ToastContextValue {
  readonly notify: (message: ToastMessage) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

/** Shows a transient notice. Toasts are for transient feedback only; errors that block a task stay inline. */
export function useToast(): ToastContextValue {
  const context = use(ToastContext);
  if (context === null) {
    throw new Error('useToast must be used inside <ToastProvider>');
  }
  return context;
}
