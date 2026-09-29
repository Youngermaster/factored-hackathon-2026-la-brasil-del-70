import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router';

import { queryKeys } from '@/shared/api';
import { useToast } from '@/shared/ui';

import type { SessionView } from '../api/session';
import { replaceSession } from '../model/cache';
import { expiredLoginPath } from '../model/paths';
import type { SessionLossChannel } from '../model/session-loss';
import { StepUpRequestContext } from '../model/step-up-context';
import * as StepUp from './StepUp';

/**
 * Session lifecycle for everything under the router: it turns a lost session reported by the API client into a
 * re-authentication that returns to the same place, and hosts the step-up dialog behind `useStepUp()`.
 */
export function AuthProvider({
  channel,
  children,
}: {
  readonly channel: SessionLossChannel;
  readonly children: ReactNode;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const { notify } = useToast();
  const where = useRef(location);
  useEffect(() => {
    where.current = location;
  }, [location]);

  // The step-up request in flight: its resolver, and whether the dialog shows. `attempt` remounts the dialog so
  // each request starts clean.
  const resolver = useRef<((verified: boolean) => void) | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(
    () =>
      channel.subscribe(() => {
        const cached = queryClient.getQueryData<SessionView | null>(queryKeys.auth.session());
        if (cached === null || cached === undefined) {
          // Nobody was signed in: the route guard sends the visitor to sign-in without an expiry notice.
          return;
        }
        // A pending step-up cannot finish without a session.
        resolver.current?.(false);
        resolver.current = null;
        setStepUpOpen(false);
        const { pathname, search } = where.current;
        if (pathname === '/login') {
          replaceSession(queryClient, null);
          return;
        }
        // Leave the guarded page first (committed synchronously, not as a transition) and clear the session after:
        // a guard that saw the cleared session would redirect on its own, without the expiry notice and the way back.
        void Promise.resolve(
          navigate(expiredLoginPath(pathname, search), { replace: true, flushSync: true }),
        ).then(() => {
          replaceSession(queryClient, null);
        });
      }),
    [channel, navigate, queryClient],
  );

  const requestStepUp = useCallback(
    () =>
      new Promise<boolean>((resolve) => {
        resolver.current?.(false);
        resolver.current = resolve;
        setAttempt((count) => count + 1);
        setStepUpOpen(true);
      }),
    [],
  );

  const settle = useCallback(
    (verified: boolean) => {
      resolver.current?.(verified);
      resolver.current = null;
      setStepUpOpen(false);
      if (verified) {
        notify({ title: t('auth.stepUpDone'), tone: 'decision' });
      }
    },
    [notify, t],
  );

  const value = useMemo(() => ({ requestStepUp }), [requestStepUp]);

  return (
    <StepUpRequestContext value={value}>
      {children}
      <StepUp.Root
        key={attempt}
        open={stepUpOpen}
        onVerified={() => {
          settle(true);
        }}
        onCancel={() => {
          settle(false);
        }}
      >
        <StepUp.Title />
        <StepUp.Description />
        <StepUp.CodeForm />
      </StepUp.Root>
    </StepUpRequestContext>
  );
}
