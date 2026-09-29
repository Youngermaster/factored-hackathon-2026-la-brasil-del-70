import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { Badge, Button, Card, KeyValueList, ShieldIcon } from '@/shared/ui';

import { useSession } from '../api/session';
import { useStepUp } from '../model/step-up-context';

/** The session's role, verification level, expiry instants, and step-up window, with a way to step up now. */
export function SessionStatus() {
  const { t } = useTranslation();
  const format = useFormat();
  const session = useSession();
  const { requestStepUp } = useStepUp();
  if (session.data === null || session.data === undefined) {
    return null;
  }
  const view = session.data;
  return (
    <Card.Root aria-labelledby="session-status-title">
      <Card.Header
        title={<span id="session-status-title">{t('session.title')}</span>}
        action={<Badge>{t(`session.roles.${view.role}`)}</Badge>}
      />
      <Card.Body>
        <KeyValueList.Root columns={2}>
          <KeyValueList.Item label={t('session.authLevel')}>
            {t(`session.authLevels.${view.auth_level}`)}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('session.stepUp')}>
            {view.step_up_valid && view.step_up_expires_at !== null
              ? t('session.stepUpActive', { time: format.time(view.step_up_expires_at) })
              : t('session.stepUpInactive')}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('session.idleExpires')}>
            <time dateTime={view.idle_expires_at}>{format.relative(view.idle_expires_at)}</time>
          </KeyValueList.Item>
          <KeyValueList.Item label={t('session.absoluteExpires')}>
            <time dateTime={view.absolute_expires_at}>{format.time(view.absolute_expires_at)}</time>
          </KeyValueList.Item>
        </KeyValueList.Root>
      </Card.Body>
      {!view.step_up_valid && (
        <Card.Footer>
          <Button
            variant="secondary"
            onClick={() => {
              void requestStepUp();
            }}
          >
            <ShieldIcon aria-hidden="true" size={18} />
            {t('auth.stepUpStart')}
          </Button>
        </Card.Footer>
      )}
    </Card.Root>
  );
}
