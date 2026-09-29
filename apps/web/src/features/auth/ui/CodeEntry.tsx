import { useState, type ReactNode, type SubmitEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { Button, ClockIcon, Field, OneTimeCodeInput } from '@/shared/ui';

import type { Challenge } from '../api/session';
import { describeCodeError } from '../model/code-errors';
import { useSecondsUntil } from '../model/use-countdown';

export interface CodeEntryProps {
  readonly challenge: Challenge;
  readonly onVerify: (code: string) => void;
  readonly verifying: boolean;
  /** The last failed verify, if any. */
  readonly error: unknown;
  /** Failed attempts on this challenge, to count down what is left. */
  readonly failures: number;
  readonly onResend: () => void;
  readonly resending: boolean;
  /** Extra actions next to "get another code", for example "use other details". */
  readonly children?: ReactNode;
}

/**
 * The one-time code step shared by login and step-up: the demo code when demo mode shows it, a single-field code
 * input with paste support, the expiry countdown, and the wrong-code, expired, and lockout messages.
 */
export function CodeEntry({
  challenge,
  onVerify,
  verifying,
  error,
  failures,
  onResend,
  resending,
  children,
}: CodeEntryProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const [code, setCode] = useState('');
  const [incomplete, setIncomplete] = useState(false);
  const seconds = useSecondsUntil(challenge.expires_at);
  const expired = seconds === 0;
  const failure = error === null || error === undefined ? null : describeCodeError(error);
  const attemptsLeft = Math.max(0, challenge.attempts_remaining - failures);
  const blocked = expired || failure?.needsNewCode === true;

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (code.length !== 6) {
      setIncomplete(true);
      return;
    }
    setIncomplete(false);
    onVerify(code);
  };

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-6">
      {challenge.demo_code !== null && challenge.demo_code !== undefined && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface-sunken px-4 py-3">
          <p className="text-small text-fg-secondary">{t('auth.demoCode')}</p>
          <p className="font-mono text-title tracking-[0.3em] text-fg tabular-nums">
            {challenge.demo_code}
          </p>
        </div>
      )}

      <Field.Root invalid={incomplete || failure !== null} hasHint>
        <Field.Label>{t('auth.codeLabel')}</Field.Label>
        <Field.Control>
          <OneTimeCodeInput
            value={code}
            onValueChange={(next) => {
              setCode(next);
              setIncomplete(false);
            }}
            disabled={blocked}
          />
        </Field.Control>
        <Field.Hint>{t('auth.codeHint')}</Field.Hint>
        <Field.Error role="alert">
          {incomplete && t('auth.codeIncomplete')}
          {!incomplete && failure !== null && (
            <>
              {t(failure.key, { minutes: failure.minutes ?? 0 })}
              {failure.key === 'auth.wrongCode' &&
                ` ${t('auth.attemptsRemaining', { count: attemptsLeft })}`}
            </>
          )}
        </Field.Error>
      </Field.Root>

      <p className="inline-flex items-center gap-1.5 text-small text-fg-muted">
        <ClockIcon aria-hidden="true" size={16} />
        {expired ? (
          <span role="status">{t('auth.codeExpired')}</span>
        ) : (
          <span className="font-mono tabular-nums">
            {t('auth.expiresIn', { time: format.countdown(seconds) })}
          </span>
        )}
      </p>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button type="submit" size="lg" pending={verifying} disabled={blocked}>
          {t('auth.verify')}
        </Button>
        <Button variant="ghost" size="lg" pending={resending} onClick={onResend}>
          {t('auth.resend')}
        </Button>
        {children}
      </div>
    </form>
  );
}
