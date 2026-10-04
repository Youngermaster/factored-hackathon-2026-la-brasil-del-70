import { useTranslation } from 'react-i18next';

import { errorMessageKey, errorRequestId, hasProblem } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  KeyValueList,
  Skeleton,
  SkeletonGroup,
} from '@/shared/ui';

import { useHandoff, type HandoffView } from '../api/handoffs';
import { HandoffContext } from '../model/handoff-context';
import { useNow } from '../model/use-now';
import { HandoffActions } from './HandoffActions';
import { HumanConversation } from './HumanConversation';
import { useInboxLabels } from './labels';
import {
  ActionsTaken,
  CardRequestSection,
  CreditReviewSection,
  OpenQuestions,
  PolicyBasis,
  VerifiedFacts,
} from './sections';
import { SlaText } from './SlaText';

/**
 * One handoff as an agent works it: the request, verified facts with their sources, actions with verification,
 * the policy basis, open questions, and the credit or card sections when present. Never a transcript.
 */
export function HandoffDetail({ handoffId }: { readonly handoffId: string }) {
  const { t } = useTranslation();
  const handoff = useHandoff(handoffId);

  if (handoff.isPending) {
    return (
      <SkeletonGroup label={t('inbox.loading')}>
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-40 w-full" />
      </SkeletonGroup>
    );
  }
  if (handoff.isError) {
    if (hasProblem(handoff.error, 'resource-not-found')) {
      return <EmptyState title={t('inbox.notFoundTitle')} description={t('inbox.notFoundBody')} />;
    }
    return (
      <ErrorState
        title={t('inbox.error')}
        description={t(errorMessageKey(handoff.error))}
        requestId={errorRequestId(handoff.error)}
        action={
          <Button variant="secondary" onClick={() => void handoff.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  return (
    <HandoffContext value={handoff.data}>
      <DetailBody handoff={handoff.data} />
    </HandoffContext>
  );
}

function DetailBody({ handoff }: { readonly handoff: HandoffView }) {
  const { t } = useTranslation();
  const format = useFormat();
  const labels = useInboxLabels();
  const now = useNow();
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
            {labels.code('intent', handoff.request.intent)}
          </h1>
          <p className="max-w-prose text-body text-fg-secondary">{handoff.request.summary}</p>
          <div className="flex flex-wrap items-center gap-2 text-small">
            <Badge tone={handoff.priority === 'critical' ? 'risk' : 'neutral'}>
              {labels.value('priority', handoff.priority)}
            </Badge>
            <Badge>{labels.value('status', handoff.status)}</Badge>
            <Badge tone="risk">{labels.value('reason', handoff.escalation_reason.code)}</Badge>
            <SlaText due={handoff.sla_due} now={now} />
          </div>
        </div>
        <HandoffActions />
      </div>

      <Card.Root aria-labelledby="handoff-request">
        <Card.Header title={<span id="handoff-request">{t('inbox.detail.request')}</span>} />
        <Card.Body>
          <KeyValueList.Root columns={3}>
            <KeyValueList.Item label={t('inbox.detail.workflow')}>
              {labels.workflow(handoff.workflow?.id)}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.intent')}>
              <span className="font-mono">{handoff.request.intent}</span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.state')}>
              <span className="font-mono">{handoff.state_at_escalation}</span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.reasonDetail')}>
              {handoff.escalation_reason.detail}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.language')}>
              {labels.value('language', handoff.language)} / {handoff.jurisdiction}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.sentiment')}>
              {labels.code('sentiment', handoff.customer_sentiment)}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.auth')}>
              {t(`session.authLevels.${handoff.auth.level}`)}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.created')}>
              <time dateTime={handoff.created_at}>{format.dateTime(handoff.created_at)}</time>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.references')}>
              <span className="font-mono text-small break-all">
                {[handoff.handoff_id, handoff.conversation_ref, handoff.case_ref]
                  .filter((ref) => ref !== null)
                  .join(', ')}
              </span>
            </KeyValueList.Item>
          </KeyValueList.Root>
        </Card.Body>
      </Card.Root>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <VerifiedFacts />
        <ActionsTaken />
        <PolicyBasis />
        <OpenQuestions />
      </div>
      <HumanConversation />
      <CreditReviewSection />
      <CardRequestSection />
    </div>
  );
}
