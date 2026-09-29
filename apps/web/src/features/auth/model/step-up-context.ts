import { createContext, use } from 'react';

import type { Challenge } from '../api/session';

export interface StepUpRequest {
  /** Opens the step-up dialog; resolves true once the session is stepped up, false if the person cancels. */
  readonly requestStepUp: () => Promise<boolean>;
}

export const StepUpRequestContext = createContext<StepUpRequest | null>(null);

/** Asks for a fresh one-time code before a write. Usable from any feature under <AuthProvider>. */
export function useStepUp(): StepUpRequest {
  const context = use(StepUpRequestContext);
  if (context === null) {
    throw new Error('useStepUp must be used inside <AuthProvider>');
  }
  return context;
}

/** State shared by the parts of one step-up dialog (<StepUp.Root> and its children). */
export interface StepUpDialogState {
  readonly challenge: Challenge | null;
  readonly startError: unknown;
  readonly starting: boolean;
  readonly verify: (code: string) => void;
  readonly verifying: boolean;
  readonly verifyError: unknown;
  readonly failures: number;
  readonly restart: () => void;
  readonly cancel: () => void;
}

export const StepUpDialogContext = createContext<StepUpDialogState | null>(null);

export function useStepUpDialog(): StepUpDialogState {
  const context = use(StepUpDialogContext);
  if (context === null) {
    throw new Error('StepUp parts must be inside <StepUp.Root>');
  }
  return context;
}
