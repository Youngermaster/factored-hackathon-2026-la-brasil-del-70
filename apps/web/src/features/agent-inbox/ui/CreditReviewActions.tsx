import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { errorMessageKey, hasProblem } from '@/shared/api';
import { Button, Dialog, useToast } from '@/shared/ui';

import {
  useMoveCreditApplication,
  type CreditApplicationView,
  type CreditReviewMove,
} from '../api/handoffs';

/**
 * The agent's two moves on a credit intake, each behind a confirmation: take a submitted intake into human review, then
 * close it. Both are audited by the API. Neither is a lending decision: there is no approve or decline.
 */
export function CreditReviewActions({
  application,
}: {
  readonly application: CreditApplicationView;
}) {
  if (application.status === 'submitted') {
    return <MoveDialog application={application} move="review" />;
  }
  if (application.status === 'under_human_review') {
    return <MoveDialog application={application} move="close" />;
  }
  return null;
}

const COPY = {
  review: {
    trigger: 'applications.actions.review',
    title: 'applications.actions.reviewTitle',
    body: 'applications.actions.reviewBody',
    confirm: 'applications.actions.reviewConfirm',
    done: 'applications.actions.reviewDone',
  },
  close: {
    trigger: 'applications.actions.close',
    title: 'applications.actions.closeTitle',
    body: 'applications.actions.closeBody',
    confirm: 'applications.actions.closeConfirm',
    done: 'applications.actions.closeDone',
  },
} as const;

function MoveDialog({
  application,
  move,
}: {
  readonly application: CreditApplicationView;
  readonly move: CreditReviewMove;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const mutation = useMoveCreditApplication();
  const [open, setOpen] = useState(false);
  const copy = COPY[move];
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant={move === 'review' ? 'primary' : 'secondary'}>{t(copy.trigger)}</Button>
      </Dialog.Trigger>
      <Dialog.Content>
        <Dialog.Header>
          <Dialog.Title>{t(copy.title)}</Dialog.Title>
          <Dialog.Description>{t(copy.body)}</Dialog.Description>
        </Dialog.Header>
        {mutation.isError && (
          <p role="alert" className="text-small font-medium text-risk-text">
            {hasProblem(mutation.error, 'invalid-state-transition', 'conflict')
              ? t('applications.actions.conflict')
              : t(errorMessageKey(mutation.error))}
          </p>
        )}
        <Dialog.Footer>
          <Dialog.Close asChild>
            <Button variant="secondary">{t('common.cancel')}</Button>
          </Dialog.Close>
          <Button
            pending={mutation.isPending}
            onClick={() => {
              mutation.mutate(
                {
                  applicationId: application.application_id,
                  move,
                  expectedVersion: application.version,
                },
                {
                  onSuccess: () => {
                    setOpen(false);
                    notify({ title: t(copy.done), tone: 'decision' });
                  },
                },
              );
            }}
          >
            {t(copy.confirm)}
          </Button>
        </Dialog.Footer>
      </Dialog.Content>
    </Dialog.Root>
  );
}
