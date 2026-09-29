import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { CreditApplicationDetail } from '@/features/agent-inbox';
import { RequireSession } from '@/features/auth';
import { BackIcon, Button } from '@/shared/ui';

/** One credit intake, with a way back to the list. */
export function CreditApplicationPage() {
  const { t } = useTranslation();
  const { applicationId = '' } = useParams();
  return (
    <RequireSession roles={['agent']}>
      <div className="flex flex-col gap-4">
        <div>
          <Button asChild variant="ghost" size="sm">
            <Link to="/console/credit-applications">
              <BackIcon aria-hidden="true" size={16} />
              {t('applications.back')}
            </Link>
          </Button>
        </div>
        <CreditApplicationDetail applicationId={applicationId} />
      </div>
    </RequireSession>
  );
}
