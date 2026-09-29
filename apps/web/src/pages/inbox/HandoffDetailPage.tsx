import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { HandoffDetail } from '@/features/agent-inbox';
import { RequireSession } from '@/features/auth';
import { BackIcon, Button } from '@/shared/ui';

/** One handoff, with a way back to the inbox. */
export function HandoffDetailPage() {
  const { t } = useTranslation();
  const { handoffId = '' } = useParams();
  return (
    <RequireSession roles={['agent']}>
      <div className="flex flex-col gap-4">
        <div>
          <Button asChild variant="ghost" size="sm">
            <Link to="/console/inbox">
              <BackIcon aria-hidden="true" size={16} />
              {t('inbox.back')}
            </Link>
          </Button>
        </div>
        <HandoffDetail handoffId={handoffId} />
      </div>
    </RequireSession>
  );
}
