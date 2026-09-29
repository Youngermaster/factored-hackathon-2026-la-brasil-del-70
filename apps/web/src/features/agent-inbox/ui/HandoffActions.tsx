import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { Schema } from '@/shared/api';
import { errorMessageKey, hasProblem } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import { Button, Dialog, Field, Select, Textarea, useToast } from '@/shared/ui';

import { useClaimHandoff, useResolveHandoff } from '../api/handoffs';
import { useHandoffView } from '../model/handoff-context';
import { useInboxLabels } from './labels';

const OUTCOMES: readonly Schema<'HandoffOutcomeCode'>[] = [
  'resolved_by_agent',
  'case_updated',
  'referred_to_specialist',
  'no_action_needed',
  'customer_unreachable',
  'other',
];
const NOTE_LIMIT = 500;

/** Claim an open handoff or resolve a claimed one, each behind a confirmation. Both are audited by the API. */
export function HandoffActions() {
  const handoff = useHandoffView();
  if (handoff.status === 'open') {
    return <ClaimDialog />;
  }
  if (handoff.status === 'claimed') {
    return <ResolveDialog />;
  }
  return <Resolution />;
}

/** A claim or resolution that lost a race says so; anything else gets the plain error message. */
function FailureText({ error }: { readonly error: unknown }) {
  const { t } = useTranslation();
  return (
    <p role="alert" className="text-small font-medium text-risk-text">
      {hasProblem(error, 'invalid-state-transition', 'conflict')
        ? t('inbox.actions.conflict')
        : t(errorMessageKey(error))}
    </p>
  );
}

function ClaimDialog() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const handoff = useHandoffView();
  const claim = useClaimHandoff();
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button>{t('inbox.actions.claim')}</Button>
      </Dialog.Trigger>
      <Dialog.Content>
        <Dialog.Header>
          <Dialog.Title>{t('inbox.actions.claimTitle')}</Dialog.Title>
          <Dialog.Description>{t('inbox.actions.claimBody')}</Dialog.Description>
        </Dialog.Header>
        {claim.isError && <FailureText error={claim.error} />}
        <Dialog.Footer>
          <Dialog.Close asChild>
            <Button variant="secondary">{t('common.cancel')}</Button>
          </Dialog.Close>
          <Button
            pending={claim.isPending}
            onClick={() => {
              claim.mutate(handoff.handoff_id, {
                onSuccess: () => {
                  setOpen(false);
                  notify({ title: t('inbox.actions.claimed'), tone: 'decision' });
                },
              });
            }}
          >
            {t('inbox.actions.claimConfirm')}
          </Button>
        </Dialog.Footer>
      </Dialog.Content>
    </Dialog.Root>
  );
}

function ResolveDialog() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const labels = useInboxLabels();
  const handoff = useHandoffView();
  const resolve = useResolveHandoff();
  const [open, setOpen] = useState(false);
  const [outcome, setOutcome] = useState<Schema<'HandoffOutcomeCode'>>('resolved_by_agent');
  const [note, setNote] = useState('');
  return (
    <div className="flex flex-col items-end gap-1">
      {handoff.claimed_by !== null && (
        <p className="text-caption text-fg-muted">
          {t('inbox.actions.claimedBy', { agent: handoff.claimed_by })}
        </p>
      )}
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Trigger asChild>
          <Button>{t('inbox.actions.resolve')}</Button>
        </Dialog.Trigger>
        <Dialog.Content>
          <Dialog.Header>
            <Dialog.Title>{t('inbox.actions.resolveTitle')}</Dialog.Title>
            <Dialog.Description>{t('inbox.actions.resolveBody')}</Dialog.Description>
          </Dialog.Header>
          <Field.Root required>
            <Field.Label>{t('inbox.actions.outcome')}</Field.Label>
            <Field.Control>
              <Select
                value={outcome}
                onChange={(event) => {
                  setOutcome(event.target.value as Schema<'HandoffOutcomeCode'>);
                }}
              >
                {OUTCOMES.map((code) => (
                  <option key={code} value={code}>
                    {labels.code('outcome', code)}
                  </option>
                ))}
              </Select>
            </Field.Control>
          </Field.Root>
          <Field.Root hasHint>
            <Field.Label>{t('inbox.actions.note')}</Field.Label>
            <Field.Control>
              <Textarea
                value={note}
                maxLength={NOTE_LIMIT}
                onChange={(event) => {
                  setNote(event.target.value);
                }}
              />
            </Field.Control>
            <Field.Hint>
              {t('inbox.actions.noteHint', { count: note.length, max: NOTE_LIMIT })}
            </Field.Hint>
          </Field.Root>
          {resolve.isError && <FailureText error={resolve.error} />}
          <Dialog.Footer>
            <Dialog.Close asChild>
              <Button variant="secondary">{t('common.cancel')}</Button>
            </Dialog.Close>
            <Button
              pending={resolve.isPending}
              onClick={() => {
                resolve.mutate(
                  { handoffId: handoff.handoff_id, outcome, note: note.trim() },
                  {
                    onSuccess: () => {
                      setOpen(false);
                      notify({ title: t('inbox.actions.resolved'), tone: 'decision' });
                    },
                  },
                );
              }}
            >
              {t('inbox.actions.resolveConfirm')}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Root>
    </div>
  );
}

function Resolution() {
  const { t } = useTranslation();
  const format = useFormat();
  const labels = useInboxLabels();
  const { resolution } = useHandoffView();
  if (resolution === null) {
    return null;
  }
  return (
    <div className="flex max-w-sm flex-col gap-1 rounded-card border border-border bg-surface p-4 text-small">
      <p className="font-semibold text-fg">{labels.code('outcome', resolution.outcome)}</p>
      {resolution.note !== '' && <p className="text-fg-secondary">{resolution.note}</p>}
      <p className="text-caption text-fg-muted">
        {t('inbox.actions.resolvedBy', {
          agent: resolution.resolved_by,
          time: format.dateTime(resolution.resolved_at),
        })}
      </p>
    </div>
  );
}
