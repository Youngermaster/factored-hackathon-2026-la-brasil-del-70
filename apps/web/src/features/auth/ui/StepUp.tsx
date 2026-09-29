import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { errorMessageKey, errorRequestId } from '@/shared/api';
import { Button, Dialog, ErrorState, LockIcon, SkeletonGroup, Skeleton } from '@/shared/ui';

import { useStartStepUp, useVerifyStepUp } from '../api/session';
import { StepUpDialogContext, useStepUpDialog } from '../model/step-up-context';
import { CodeEntry } from './CodeEntry';

/**
 * One step-up dialog, as compound parts: <StepUp.Root> owns the challenge and the verification and renders the
 * dialog; <StepUp.Title>, <StepUp.Description>, and <StepUp.CodeForm> compose its content. A caller that needs
 * different copy composes its own; <StepUpProvider> uses the default composition.
 */
export function Root({
  open,
  onVerified,
  onCancel,
  children,
}: {
  readonly open: boolean;
  readonly onVerified: () => void;
  readonly onCancel: () => void;
  readonly children: ReactNode;
}) {
  const start = useStartStepUp();
  const verify = useVerifyStepUp();
  const [failures, setFailures] = useState(0);
  const { mutate: startChallenge } = start;
  const { reset: resetVerify } = verify;

  const restart = useCallback(() => {
    setFailures(0);
    resetVerify();
    startChallenge();
  }, [resetVerify, startChallenge]);

  // Each opening is a fresh mount (the host keys it), so opening only has to request the challenge.
  useEffect(() => {
    if (open) {
      startChallenge();
    }
  }, [open, startChallenge]);

  const challenge = start.data ?? null;
  const state = useMemo(
    () => ({
      challenge,
      startError: start.error,
      starting: start.isPending,
      verify: (code: string) => {
        if (challenge === null) {
          return;
        }
        verify.mutate(
          { challenge_id: challenge.challenge_id, code },
          {
            onSuccess: onVerified,
            onError: () => {
              setFailures((count) => count + 1);
            },
          },
        );
      },
      verifying: verify.isPending,
      verifyError: verify.error,
      failures,
      restart,
      cancel: onCancel,
    }),
    [challenge, start.error, start.isPending, verify, failures, restart, onCancel, onVerified],
  );

  return (
    <StepUpDialogContext value={state}>
      <Dialog.Root
        open={open}
        onOpenChange={(next) => {
          if (!next) {
            onCancel();
          }
        }}
      >
        <Dialog.Content>{children}</Dialog.Content>
      </Dialog.Root>
    </StepUpDialogContext>
  );
}

export function Title({ children }: { readonly children?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <Dialog.Title className="flex items-center gap-2">
      <LockIcon aria-hidden="true" size={22} />
      {children ?? t('auth.stepUpTitle')}
    </Dialog.Title>
  );
}

export function Description({ children }: { readonly children?: ReactNode }) {
  const { t } = useTranslation();
  return <Dialog.Description>{children ?? t('auth.stepUpBody')}</Dialog.Description>;
}

export function CodeForm() {
  const { t } = useTranslation();
  const dialog = useStepUpDialog();
  if (dialog.startError !== null) {
    return (
      <ErrorState
        title={t('auth.stepUpFailed')}
        description={t(errorMessageKey(dialog.startError))}
        requestId={errorRequestId(dialog.startError)}
        action={
          <Button variant="secondary" onClick={dialog.restart}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  if (dialog.challenge === null) {
    return (
      <SkeletonGroup>
        <Skeleton className="h-14 w-full max-w-sm" />
        <Skeleton className="h-4 w-32" />
      </SkeletonGroup>
    );
  }
  return (
    <CodeEntry
      challenge={dialog.challenge}
      failures={dialog.failures}
      error={dialog.verifyError}
      verifying={dialog.verifying}
      resending={dialog.starting}
      onResend={dialog.restart}
      onVerify={dialog.verify}
    >
      <Button variant="ghost" size="lg" onClick={dialog.cancel}>
        {t('common.cancel')}
      </Button>
    </CodeEntry>
  );
}
