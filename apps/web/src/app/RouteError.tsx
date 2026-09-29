import { useTranslation } from 'react-i18next';
import { Link, useRouteError } from 'react-router';

import { errorRequestId } from '@/shared/api';
import { Button, ErrorState } from '@/shared/ui';

/** The route error boundary: a render or loader failure shows a way forward instead of a blank page. */
export function RouteError() {
  const { t } = useTranslation();
  const error = useRouteError();
  return (
    <main
      id="main"
      className="mx-auto flex min-h-dvh w-full max-w-xl flex-col justify-center gap-6 px-4 py-12"
    >
      <ErrorState
        title={t('errors.routeErrorTitle')}
        description={t('errors.routeErrorBody')}
        requestId={errorRequestId(error)}
        action={
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => {
                window.location.reload();
              }}
            >
              {t('common.reload')}
            </Button>
            <Button asChild variant="secondary">
              <Link to="/">{t('common.goHome')}</Link>
            </Button>
          </div>
        }
      />
    </main>
  );
}
