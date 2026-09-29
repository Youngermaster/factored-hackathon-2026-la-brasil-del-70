import { useEffect, useReducer, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { errorMessageKey, errorRequestId } from '@/shared/api';
import { isDemoMode } from '@/shared/config';
import { useLocale } from '@/shared/i18n';
import { Button, ErrorState, Tabs } from '@/shared/ui';

import {
  useStartLogin,
  useVerifyLogin,
  type Challenge,
  type LoginIdentification,
  type SessionView,
} from '../api/session';
import { CodeEntry } from './CodeEntry';
import { DocumentForm } from './DocumentForm';
import { PersonaPicker } from './PersonaPicker';

type State =
  | { readonly step: 'identify'; readonly pendingPersona: string | null }
  | {
      readonly step: 'code';
      readonly challenge: Challenge;
      readonly identification: LoginIdentification;
      readonly failures: number;
    };

type Action =
  | { readonly type: 'persona-chosen'; readonly personaId: string }
  | {
      readonly type: 'challenge-opened';
      readonly challenge: Challenge;
      readonly identification: LoginIdentification;
    }
  | { readonly type: 'start-failed' }
  | { readonly type: 'code-rejected' }
  | { readonly type: 'restart' };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'persona-chosen':
      return { step: 'identify', pendingPersona: action.personaId };
    case 'challenge-opened':
      return {
        step: 'code',
        challenge: action.challenge,
        identification: action.identification,
        failures: 0,
      };
    case 'start-failed':
      return { step: 'identify', pendingPersona: null };
    case 'code-rejected':
      return state.step === 'code' ? { ...state, failures: state.failures + 1 } : state;
    case 'restart':
      return { step: 'identify', pendingPersona: null };
  }
}

/**
 * Sign-in: identify (a demo persona in demo mode, or a document with the last four phone digits), then the
 * one-time code. Identification alone never signs anyone in.
 */
export function LoginFlow({ onSignedIn }: { readonly onSignedIn: (session: SessionView) => void }) {
  const { t } = useTranslation();
  const { language } = useLocale();
  const [state, dispatch] = useReducer(reducer, { step: 'identify', pendingPersona: null });
  const start = useStartLogin();
  const verify = useVerifyLogin();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const demo = isDemoMode();

  useEffect(() => {
    // Move focus to the new step so screen reader and keyboard users land on it.
    if (state.step === 'code') {
      headingRef.current?.focus();
    }
  }, [state.step]);

  const open = (identification: LoginIdentification) => {
    verify.reset();
    start.mutate(identification, {
      onSuccess: (challenge) => {
        dispatch({ type: 'challenge-opened', challenge, identification });
      },
      onError: () => {
        dispatch({ type: 'start-failed' });
      },
    });
  };

  if (state.step === 'code') {
    return (
      <section aria-labelledby="login-code-heading" className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h2
            id="login-code-heading"
            ref={headingRef}
            tabIndex={-1}
            className="text-heading font-semibold text-fg outline-none"
          >
            {t('auth.codeHeading')}
          </h2>
          <p className="text-body text-fg-secondary">{t('auth.codeIntro')}</p>
        </div>
        <CodeEntry
          challenge={state.challenge}
          failures={state.failures}
          error={verify.error}
          verifying={verify.isPending}
          resending={start.isPending}
          onResend={() => {
            open(state.identification);
          }}
          onVerify={(code) => {
            verify.mutate(
              { challenge_id: state.challenge.challenge_id, code, language },
              {
                onSuccess: ({ session }) => {
                  onSignedIn(session);
                },
                onError: () => {
                  dispatch({ type: 'code-rejected' });
                },
              },
            );
          }}
        >
          <Button
            variant="ghost"
            size="lg"
            onClick={() => {
              verify.reset();
              dispatch({ type: 'restart' });
            }}
          >
            {t('auth.changeIdentity')}
          </Button>
        </CodeEntry>
      </section>
    );
  }

  const startError =
    start.error === null ? null : (
      <ErrorState title={t(errorMessageKey(start.error))} requestId={errorRequestId(start.error)} />
    );

  const documentForm = <DocumentForm pending={start.isPending} onSubmit={open} />;

  if (!demo) {
    return (
      <div className="flex flex-col gap-6">
        {startError}
        {documentForm}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {startError}
      <Tabs.Root defaultValue="persona">
        <Tabs.List aria-label={t('auth.methodLabel')}>
          <Tabs.Trigger value="persona">{t('auth.methodPersona')}</Tabs.Trigger>
          <Tabs.Trigger value="document">{t('auth.methodDocument')}</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Panel value="persona">
          <PersonaPicker
            pendingId={state.pendingPersona}
            onSelect={(persona) => {
              dispatch({ type: 'persona-chosen', personaId: persona.id });
              open({ kind: 'persona', persona_id: persona.id });
            }}
          />
        </Tabs.Panel>
        <Tabs.Panel value="document">{documentForm}</Tabs.Panel>
      </Tabs.Root>
    </div>
  );
}
